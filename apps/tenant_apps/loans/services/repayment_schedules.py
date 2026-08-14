import calendar
import hashlib
import json
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.tenant_apps.loans.domain import (
    LoanAmortisationMethod,
    LoanRepaymentStructure,
    RepaymentSchedule,
    RepaymentScheduleInput,
    ScheduledRepayment,
)
from apps.tenant_apps.loans.domain.interest import calculate_period_interest


class RepaymentScheduleError(ValueError):
    pass


def generate_repayment_schedule(value: RepaymentScheduleInput) -> RepaymentSchedule:
    principal = Decimal(value.principal)
    rate = Decimal(value.monthly_interest_rate) / Decimal("100")
    quantum = Decimal(value.currency_quantum)
    tenure = int(value.tenure_months)
    if principal <= 0 or tenure <= 0 or rate < 0 or quantum <= 0:
        raise RepaymentScheduleError("Principal, tenure, rate, and currency quantum are invalid.")
    if value.rate_tranches:
        tranche_total = sum((Decimal(item.principal) for item in value.rate_tranches), Decimal("0"))
        if tranche_total != principal:
            raise RepaymentScheduleError("Rate tranches must reconcile exactly to principal.")

    structure = LoanRepaymentStructure(value.repayment_structure)
    if structure in {
        LoanRepaymentStructure.SINGLE_PAYMENT_BULLET,
        LoanRepaymentStructure.FLEXIBLE_PARTIAL_PAYMENT,
    }:
        rows, raw_total = _maturity_bullet(value, quantum)
    elif structure == LoanRepaymentStructure.PERIODIC_INTEREST_BULLET:
        rows, raw_total = _periodic_interest_bullet(value, quantum)
    elif structure == LoanRepaymentStructure.INSTALLMENT:
        method = LoanAmortisationMethod(value.amortisation_method)
        if method == LoanAmortisationMethod.EMI:
            rows, raw_total = _emi(value, rate, quantum)
        elif method == LoanAmortisationMethod.EQUAL_PRINCIPAL:
            rows, raw_total = _equal_principal(value, rate, quantum)
        else:
            raise RepaymentScheduleError("Installment schedule requires a supported amortisation method.")
    else:
        raise RepaymentScheduleError("Legacy/unspecified contracts cannot generate a new schedule.")

    contractual_interest = sum((row.interest_due for row in rows), Decimal("0"))
    rounded_raw_total = _money(raw_total, quantum)
    rounding_adjustment = contractual_interest - rounded_raw_total
    maturity = rows[-1].due_date
    payload = {
        "contract_version": value.contract_version,
        "disbursed_on": value.disbursed_on.isoformat(),
        "maturity_date": maturity.isoformat(),
        "principal": str(principal),
        "contractual_interest": str(contractual_interest),
        "rounding_adjustment": str(rounding_adjustment),
        "repayments": [
            {
                "sequence": row.sequence,
                "due_date": row.due_date.isoformat(),
                "principal_due": str(row.principal_due),
                "interest_due": str(row.interest_due),
                "opening_principal": str(row.opening_principal),
                "closing_principal": str(row.closing_principal),
            }
            for row in rows
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return RepaymentSchedule(
        contract_version=value.contract_version,
        disbursed_on=value.disbursed_on,
        maturity_date=maturity,
        principal=principal,
        contractual_interest=contractual_interest,
        repayments=tuple(rows),
        rounding_adjustment=rounding_adjustment,
        fingerprint=fingerprint,
    )


def generate_shortened_installment_schedule(
    value: RepaymentScheduleInput,
    *,
    emi_payment: Decimal | None = None,
    equal_principal_component: Decimal | None = None,
):
    if LoanRepaymentStructure(value.repayment_structure) != LoanRepaymentStructure.INSTALLMENT:
        raise RepaymentScheduleError("Only installment schedules may be shortened.")
    principal = Decimal(value.principal)
    rate_percent = Decimal(value.monthly_interest_rate)
    quantum = Decimal(value.currency_quantum)
    method = LoanAmortisationMethod(value.amortisation_method)
    rows = []
    balance = principal
    raw_interest_total = Decimal("0")
    for sequence in range(1, int(value.tenure_months) + 1):
        raw_interest, interest = calculate_period_interest(
            calculation_base=balance,
            monthly_interest_rate=rate_percent,
            period_fraction=Decimal("1"),
            currency_quantum=quantum,
        )
        raw_interest_total += raw_interest
        if method == LoanAmortisationMethod.EMI:
            payment = Decimal(emi_payment or 0)
            if payment <= interest:
                raise RepaymentScheduleError("Fixed EMI must exceed periodic interest.")
            principal_due = min(balance, _money(payment - interest, quantum))
        elif method == LoanAmortisationMethod.EQUAL_PRINCIPAL:
            component = Decimal(equal_principal_component or 0)
            if component <= 0:
                raise RepaymentScheduleError("Equal-principal component must be positive.")
            principal_due = min(balance, _money(component, quantum))
        else:
            raise RepaymentScheduleError("Unsupported installment amortisation method.")
        closing = balance - principal_due
        rows.append(ScheduledRepayment(
            sequence=sequence,
            due_date=_anniversary(value.disbursed_on, sequence),
            principal_due=principal_due,
            interest_due=interest,
            opening_principal=balance,
            closing_principal=closing,
        ))
        balance = closing
        if balance == 0:
            break
    if balance != 0:
        raise RepaymentScheduleError("Fixed installment does not repay principal within tenor limit.")
    return _schedule_from_rows(value, rows, raw_interest_total)


def _schedule_from_rows(value, rows, raw_interest_total):
    principal = Decimal(value.principal)
    contractual_interest = sum((row.interest_due for row in rows), Decimal("0"))
    rounding_adjustment = contractual_interest - _money(raw_interest_total, value.currency_quantum)
    payload = {
        "contract_version": value.contract_version,
        "disbursed_on": value.disbursed_on.isoformat(),
        "maturity_date": rows[-1].due_date.isoformat(),
        "principal": str(principal),
        "contractual_interest": str(contractual_interest),
        "rounding_adjustment": str(rounding_adjustment),
        "repayments": [
            [row.sequence, row.due_date.isoformat(), str(row.principal_due),
             str(row.interest_due), str(row.opening_principal), str(row.closing_principal)]
            for row in rows
        ],
    }
    fingerprint = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return RepaymentSchedule(
        contract_version=value.contract_version,
        disbursed_on=value.disbursed_on,
        maturity_date=rows[-1].due_date,
        principal=principal,
        contractual_interest=contractual_interest,
        repayments=tuple(rows),
        rounding_adjustment=rounding_adjustment,
        fingerprint=fingerprint,
    )


def _maturity_bullet(value, quantum):
    raw_monthly = _raw_monthly_interest(value)
    raw_total = raw_monthly * value.tenure_months
    interest = _money(raw_total, quantum)
    return [ScheduledRepayment(
        sequence=1,
        due_date=_anniversary(value.disbursed_on, value.tenure_months),
        principal_due=Decimal(value.principal),
        interest_due=interest,
        opening_principal=Decimal(value.principal),
        closing_principal=Decimal("0"),
    )], raw_total


def _periodic_interest_bullet(value, quantum):
    raw_monthly = _raw_monthly_interest(value)
    interest = _money(raw_monthly, quantum)
    principal = Decimal(value.principal)
    rows = []
    for sequence in range(1, value.tenure_months + 1):
        final = sequence == value.tenure_months
        rows.append(ScheduledRepayment(
            sequence=sequence,
            due_date=_anniversary(value.disbursed_on, sequence),
            principal_due=principal if final else Decimal("0"),
            interest_due=interest,
            opening_principal=principal,
            closing_principal=Decimal("0") if final else principal,
        ))
    return rows, raw_monthly * value.tenure_months


def _emi(value, rate, quantum):
    principal = Decimal(value.principal)
    tenure = value.tenure_months
    raw_payment = principal / tenure if rate == 0 else (
        principal * rate * (Decimal("1") + rate) ** tenure
        / ((Decimal("1") + rate) ** tenure - Decimal("1"))
    )
    payment = _money(raw_payment, quantum)
    balance = principal
    rows = []
    raw_interest_total = Decimal("0")
    for sequence in range(1, tenure + 1):
        raw_interest, interest = calculate_period_interest(
            calculation_base=balance,
            monthly_interest_rate=Decimal(value.monthly_interest_rate),
            period_fraction=Decimal("1"),
            currency_quantum=quantum,
        )
        raw_interest_total += raw_interest
        principal_due = balance if sequence == tenure else min(balance, payment - interest)
        principal_due = _money(principal_due, quantum)
        closing = balance - principal_due
        rows.append(ScheduledRepayment(sequence, _anniversary(value.disbursed_on, sequence), principal_due, interest, balance, closing))
        balance = closing
    return rows, raw_interest_total


def _equal_principal(value, rate, quantum):
    principal = Decimal(value.principal)
    regular_principal = _money(principal / value.tenure_months, quantum)
    balance = principal
    rows = []
    raw_interest_total = Decimal("0")
    for sequence in range(1, value.tenure_months + 1):
        raw_interest, interest = calculate_period_interest(
            calculation_base=balance,
            monthly_interest_rate=Decimal(value.monthly_interest_rate),
            period_fraction=Decimal("1"),
            currency_quantum=quantum,
        )
        raw_interest_total += raw_interest
        principal_due = balance if sequence == value.tenure_months else min(balance, regular_principal)
        closing = balance - principal_due
        rows.append(ScheduledRepayment(sequence, _anniversary(value.disbursed_on, sequence), principal_due, interest, balance, closing))
        balance = closing
    return rows, raw_interest_total


def _raw_monthly_interest(value):
    if value.rate_tranches:
        return sum(
            calculate_period_interest(
                calculation_base=item.principal,
                monthly_interest_rate=item.monthly_interest_rate,
                period_fraction=Decimal("1"),
                currency_quantum=value.currency_quantum,
            )[0]
            for item in value.rate_tranches
        )
    return calculate_period_interest(
        calculation_base=value.principal,
        monthly_interest_rate=value.monthly_interest_rate,
        period_fraction=Decimal("1"),
        currency_quantum=value.currency_quantum,
    )[0]


def _anniversary(anchor: date, months: int):
    month_index = anchor.month - 1 + months
    year = anchor.year + month_index // 12
    month = month_index % 12 + 1
    day = min(anchor.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _money(value, quantum):
    return Decimal(value).quantize(quantum, rounding=ROUND_HALF_UP)
