"""Monthly PawnLoan interest preview, finalization, and capitalization."""

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    InterestMethod,
    PartialMonthMethod,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations import accrual_payload, capitalization_payload
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanInterestAccrual,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.loans.services.accounting_outbox import (
    DeliveryHandler,
    record_loan_accounting_event,
)
from apps.tenant_apps.loans.services.accounting_readiness import (
    require_pawn_loan_accounting_readiness,
)
from apps.tenant_apps.loans.services.pawn_disbursal import (
    assert_pawn_loan_financial_actions_allowed,
)


class PawnInterestError(ValueError):
    pass


@dataclass(frozen=True)
class AccrualPeriodPreview:
    period_number: int
    period_start: date
    period_end: date
    period_fraction: Decimal
    calculation_base: Decimal
    unrounded_interest: Decimal
    recognized_interest: Decimal
    is_partial: bool


@dataclass(frozen=True)
class AccrualFinalizationResult:
    accrual: PawnLoanInterestAccrual
    accounting_event: PawnLoanAccountingEvent | None
    outbox: object | None
    already_finalized: bool = False


@dataclass(frozen=True)
class CapitalizationResult:
    accounting_event: PawnLoanAccountingEvent
    outbox: object
    amount: Decimal
    already_recorded: bool = False


def preview_pawn_loan_accruals(
    loan_id: int,
    *,
    as_of_date: date,
    include_partial: bool = True,
) -> tuple[AccrualPeriodPreview, ...]:
    loan = _tenant_loan(loan_id)
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnInterestError("Only an active PawnLoan can accrue interest.")
    policy = loan.policy_snapshot
    finalized = set(loan.interest_accruals.values_list("period_number", flat=True))
    capitalized_boundaries = _capitalized_boundaries(loan)
    previews = []
    period_number = 1
    while True:
        period_start = _add_months(loan.loan_date, period_number - 1)
        exclusive_end = _add_months(loan.loan_date, period_number)
        completed_end = exclusive_end - timedelta(days=1)
        if completed_end <= as_of_date:
            period_end = completed_end
            fraction = Decimal("1")
            is_partial = False
        elif include_partial and period_start <= as_of_date:
            period_end = as_of_date
            fraction = _partial_fraction(policy, period_start, period_end)
            is_partial = True
        else:
            break

        if period_number not in finalized:
            balance = get_pawn_loan_balance(loan.pk, as_of_date=period_start)
            base = balance.principal_outstanding
            unrounded, recognized = calculate_accrual_interest(
                calculation_base=base,
                monthly_interest_rate=loan.monthly_interest_rate,
                period_fraction=fraction,
                currency_quantum=policy.currency_quantum,
            )
            previews.append(
                AccrualPeriodPreview(
                    period_number=period_number,
                    period_start=period_start,
                    period_end=period_end,
                    period_fraction=fraction,
                    calculation_base=base,
                    unrounded_interest=unrounded,
                    recognized_interest=recognized,
                    is_partial=is_partial,
                )
            )

        if is_partial:
            break
        if (
            policy.interest_method == InterestMethod.COMPOUND.value
            and period_number % policy.capitalization_interval_periods == 0
            and period_number not in capitalized_boundaries
        ):
            break
        period_number += 1
    return tuple(previews)


def calculate_accrual_interest(
    *,
    calculation_base,
    monthly_interest_rate,
    period_fraction,
    currency_quantum,
):
    """Retain calculation precision and round only the finalized period amount."""
    base = Decimal(str(calculation_base))
    rate = Decimal(str(monthly_interest_rate))
    fraction = Decimal(str(period_fraction))
    quantum = Decimal(str(currency_quantum))
    if base < 0 or rate < 0 or not Decimal("0") < fraction <= Decimal("1"):
        raise PawnInterestError("Accrual calculation inputs are outside policy bounds.")
    unrounded = base * rate / Decimal("100") * fraction
    return unrounded, unrounded.quantize(quantum, rounding=ROUND_HALF_UP)


@transaction.atomic
def finalize_pawn_loan_accrual(
    loan_id: int,
    *,
    period_number: int,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> AccrualFinalizationResult:
    loan = _locked_loan(loan_id)
    existing = loan.interest_accruals.filter(period_number=period_number).first()
    if existing:
        event = existing.accounting_event
        return AccrualFinalizationResult(
            existing,
            event,
            event.outbox if event else None,
            True,
        )
    if period_number < 1:
        raise PawnInterestError("Accrual period number must be positive.")
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnInterestError("Only an active PawnLoan can accrue interest.")

    try:
        assert_pawn_loan_financial_actions_allowed(loan.pk)
        candidates = preview_pawn_loan_accruals(
            loan.pk,
            as_of_date=timezone.localdate(),
            include_partial=False,
        )
        preview = candidates[0] if candidates else None
        if preview is None or preview.period_number != period_number:
            raise PawnInterestError(
                "The requested period is not the next eligible completed period."
            )
        policy = loan.policy_snapshot
        if (
            preview.recognized_interest > 0
            and policy.accounting_recognition == AccountingRecognition.ACCRUAL.value
        ):
            require_pawn_loan_accounting_readiness(
                loan,
                effective_date=preview.period_end,
                requires_interest_receivable=True,
            )
    except PawnInterestError:
        raise
    except Exception as exc:
        raise PawnInterestError(str(exc)) from exc

    event = None
    outbox = None
    if preview.recognized_interest > 0:
        payload = accrual_payload(
            loan,
            effective_date=preview.period_end,
            interest_amount=preview.recognized_interest,
        ).to_dict()
        payload["accrual"] = _preview_payload(preview, loan.policy_snapshot)
        event, outbox = record_loan_accounting_event(
            loan.pk,
            event_kind=TransactionKind.INTEREST_ACCRUAL,
            effective_date=preview.period_end,
            payload=payload,
            actor=actor,
            delivery_handler=delivery_handler,
        )
    accrual = PawnLoanInterestAccrual.objects.create(
        loan=loan,
        period_number=preview.period_number,
        period_start=preview.period_start,
        period_end=preview.period_end,
        period_fraction=preview.period_fraction,
        calculation_base=preview.calculation_base,
        unrounded_interest=preview.unrounded_interest,
        recognized_interest=preview.recognized_interest,
        accounting_event=event,
        finalized_by=actor,
    )
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.ACCRUAL_FINALIZED.value,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "period_number": preview.period_number,
            "period_start": preview.period_start.isoformat(),
            "period_end": preview.period_end.isoformat(),
            "period_fraction": _decimal_string(preview.period_fraction),
            "calculation_base": _decimal_string(preview.calculation_base),
            "unrounded_interest": _decimal_string(preview.unrounded_interest),
            "recognized_interest": _decimal_string(preview.recognized_interest),
            "accounting_event_id": event.pk if event else None,
            "outbox_id": outbox.pk if outbox else None,
        },
    )
    return AccrualFinalizationResult(accrual, event, outbox)


@transaction.atomic
def capitalize_pawn_loan_interest(
    loan_id: int,
    *,
    through_period_number: int,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
) -> CapitalizationResult:
    loan = _locked_loan(loan_id)
    existing = loan.accounting_events.filter(
        event_kind=TransactionKind.INTEREST_CAPITALIZATION.value,
        payload__capitalization__through_period_number=through_period_number,
    ).first()
    if existing:
        return CapitalizationResult(
            existing,
            existing.outbox,
            Decimal(existing.payload["values"]["interest"]),
            True,
        )
    policy = loan.policy_snapshot
    if policy.interest_method != InterestMethod.COMPOUND.value:
        raise PawnInterestError("Only a compound PawnLoan can capitalize interest.")
    if through_period_number % policy.capitalization_interval_periods:
        raise PawnInterestError("Capitalization is not due at this accrual period.")
    try:
        assert_pawn_loan_financial_actions_allowed(loan.pk)
        boundary = loan.interest_accruals.get(period_number=through_period_number)
        balance = get_pawn_loan_balance(loan.pk, as_of_date=boundary.period_end)
        amount = balance.interest_outstanding
        if amount <= 0:
            raise PawnInterestError("There is no unpaid interest to capitalize.")
        if policy.accounting_recognition == AccountingRecognition.ACCRUAL.value:
            require_pawn_loan_accounting_readiness(
                loan,
                effective_date=boundary.period_end,
                requires_interest_receivable=True,
            )
    except PawnLoanInterestAccrual.DoesNotExist as exc:
        raise PawnInterestError(
            "The capitalization boundary accrual has not been finalized."
        ) from exc
    except PawnInterestError:
        raise
    except Exception as exc:
        raise PawnInterestError(str(exc)) from exc

    payload = capitalization_payload(
        loan,
        effective_date=boundary.period_end,
        interest_amount=amount,
    ).to_dict()
    payload["capitalization"] = {
        "through_period_number": through_period_number,
        "capitalization_interval_periods": policy.capitalization_interval_periods,
        "accounting_recognition": policy.accounting_recognition,
    }
    event, outbox = record_loan_accounting_event(
        loan.pk,
        event_kind=TransactionKind.INTEREST_CAPITALIZATION,
        effective_date=boundary.period_end,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.INTEREST_CAPITALIZED.value,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.ACTIVE.value,
        actor=actor,
        metadata={
            "through_period_number": through_period_number,
            "amount": _decimal_string(amount),
            "accounting_event_id": event.pk,
            "outbox_id": outbox.pk,
        },
    )
    return CapitalizationResult(event, outbox, amount)


def _tenant_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnInterestError("PawnLoan interest requires an active tenant schema.")
    try:
        return PawnLoan.objects.select_related("policy_snapshot").get(
            pk=loan_id,
            workspace_id=workspace_id,
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnInterestError("PawnLoan was not found in the active workspace.") from exc


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnInterestError("PawnLoan interest requires an active tenant schema.")
    try:
        return PawnLoan.objects.select_for_update().get(
            pk=loan_id,
            workspace_id=workspace_id,
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnInterestError("PawnLoan was not found in the active workspace.") from exc


def _partial_fraction(policy, period_start, period_end):
    if policy.partial_month_method == PartialMonthMethod.FULL_MONTH.value:
        return Decimal("1")
    elapsed_days = (period_end - period_start).days + 1
    if elapsed_days <= policy.partial_month_cutoff_days:
        return Decimal(str(policy.partial_month_lower_fraction))
    return Decimal("1")


def _capitalized_boundaries(loan):
    return {
        int(event.payload["capitalization"]["through_period_number"])
        for event in loan.accounting_events.filter(
            event_kind=TransactionKind.INTEREST_CAPITALIZATION.value
        )
        if event.payload.get("capitalization")
    }


def _preview_payload(preview, policy):
    return {
        "period_number": preview.period_number,
        "period_start": preview.period_start.isoformat(),
        "period_end": preview.period_end.isoformat(),
        "period_fraction": _decimal_string(preview.period_fraction),
        "calculation_base": _decimal_string(preview.calculation_base),
        "unrounded_interest": _decimal_string(preview.unrounded_interest),
        "recognized_interest": _decimal_string(preview.recognized_interest),
        "is_partial": preview.is_partial,
        "accounting_recognition": policy.accounting_recognition,
    }


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _decimal_string(value):
    return format(Decimal(value).normalize(), "f")
