from dataclasses import dataclass
import calendar
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    LoanRepaymentStructure,
    PawnLoanState,
)
from apps.tenant_apps.loans.models import (
    PawnLoan,
    RepaymentScheduleChangeKind,
    RepaymentScheduleVersion,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.domain.interest import calculate_period_interest
from apps.tenant_apps.loans.services.pawn_tranches import (
    get_pawn_principal_tranche_balances,
)


class PawnLoanExposureError(ValueError):
    pass


@dataclass(frozen=True)
class ExposureComponent:
    principal: Decimal
    interest: Decimal
    fees: Decimal

    @property
    def total(self):
        return self.principal + self.interest + self.fees


@dataclass(frozen=True)
class PawnLoanExposure:
    loan_id: int
    as_of_date: date
    original_principal: Decimal
    principal_repaid: Decimal
    principal_outstanding: Decimal
    recorded_interest: Decimal
    projected_interest: Decimal
    fees_and_penalties: Decimal
    due_now: ExposureComponent
    overdue: ExposureComponent
    recorded_total_due: Decimal
    total_economic_exposure: Decimal
    accounting_receivable: Decimal
    maturity_payoff: Decimal
    ltv_exposure_basis: Decimal
    projection_periods: tuple[tuple[date, date, Decimal], ...]
    provenance: tuple[str, ...]
    integrity_findings: tuple[str, ...]


def get_pawn_loan_exposure(loan_id: int, *, as_of_date: date) -> PawnLoanExposure:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanExposureError("PawnLoan exposure requires an active tenant schema.")
    try:
        loan = PawnLoan.objects.select_related(
            "product_version__product", "policy_snapshot"
        ).get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise PawnLoanExposureError("PawnLoan was not found in the active workspace.") from exc

    balance = get_pawn_loan_balance(loan, as_of_date=as_of_date)
    previews = ()
    if loan.state == PawnLoanState.ACTIVE.value and as_of_date >= loan.loan_date:
        previews = _project_interest_periods(loan, as_of_date)
    projected_interest = sum(
        (row[2] for row in previews), Decimal("0")
    )
    active_schedule = _active_schedule_as_of(loan, as_of_date)
    due_now, overdue, scheduled_remaining, findings = _obligation_components_as_of(
        active_schedule, as_of_date
    )
    recognition = getattr(loan.policy_snapshot, "accounting_recognition", None)
    accounting_interest = (
        balance.interest_outstanding
        if recognition == AccountingRecognition.ACCRUAL.value
        else Decimal("0")
    )
    accounting_receivable = (
        balance.principal_outstanding + accounting_interest + balance.fees_outstanding
    )
    recorded_total = balance.total_due
    total_economic = recorded_total + projected_interest
    maturity_payoff = scheduled_remaining.total + balance.fees_outstanding
    is_bullet = loan.product_version.repayment_structure in {
        LoanRepaymentStructure.SINGLE_PAYMENT_BULLET.value,
        LoanRepaymentStructure.PERIODIC_INTEREST_BULLET.value,
        LoanRepaymentStructure.FLEXIBLE_PARTIAL_PAYMENT.value,
    }
    ltv_basis = maturity_payoff if is_bullet else total_economic
    provenance = (
        "recorded:event-fold-v1",
        "projection:actual-outstanding-daily-v1",
        f"contract:{loan.product_version.calculation_contract_version}",
        "due:active-obligation-fold-v1",
        f"schedule:{active_schedule.fingerprint if active_schedule else 'none'}",
    )
    return PawnLoanExposure(
        loan_id=loan.pk,
        as_of_date=as_of_date,
        original_principal=balance.principal_disbursed,
        principal_repaid=balance.principal_paid,
        principal_outstanding=balance.principal_outstanding,
        recorded_interest=balance.interest_outstanding,
        projected_interest=projected_interest,
        fees_and_penalties=balance.fees_outstanding,
        due_now=due_now,
        overdue=overdue,
        recorded_total_due=recorded_total,
        total_economic_exposure=total_economic,
        accounting_receivable=accounting_receivable,
        maturity_payoff=maturity_payoff,
        ltv_exposure_basis=ltv_basis,
        projection_periods=previews,
        provenance=provenance,
        integrity_findings=findings,
    )


def _project_interest_periods(loan, as_of_date):
    last = loan.interest_accruals.exclude(
        release_catch_up__reversal__isnull=False
    ).order_by("-period_number").first()
    period_start = last.period_end + timedelta(days=1) if last else loan.loan_date
    quantum = loan.policy_snapshot.currency_quantum
    periods = []
    while period_start <= as_of_date:
        full_end = _add_months(period_start, 1) - timedelta(days=1)
        period_end = min(full_end, as_of_date)
        full_days = Decimal((full_end - period_start).days + 1)
        event_dates = tuple(
            loan.accounting_events.filter(
                effective_date__gt=period_start,
                effective_date__lte=period_end,
            ).values_list("effective_date", flat=True).distinct().order_by("effective_date")
        )
        boundaries = (period_start, *event_dates, period_end + timedelta(days=1))
        raw_period = Decimal("0")
        for segment_start, next_start in zip(boundaries, boundaries[1:]):
            segment_days = Decimal((next_start - segment_start).days)
            if segment_days <= 0:
                continue
            tranches = get_pawn_principal_tranche_balances(
                loan, as_of_date=segment_start
            )
            if tranches:
                for tranche in tranches:
                    raw, _ = calculate_period_interest(
                        calculation_base=tranche.principal_outstanding,
                        monthly_interest_rate=tranche.monthly_interest_rate,
                        period_fraction=segment_days / full_days,
                        currency_quantum=quantum,
                    )
                    raw_period += raw
            else:
                balance = get_pawn_loan_balance(loan, as_of_date=segment_start)
                raw, _ = calculate_period_interest(
                    calculation_base=balance.principal_outstanding,
                    monthly_interest_rate=loan.monthly_interest_rate,
                    period_fraction=segment_days / full_days,
                    currency_quantum=quantum,
                )
                raw_period += raw
        projected = raw_period.quantize(
            Decimal(str(quantum)), rounding=ROUND_HALF_UP
        )
        periods.append((period_start, period_end, projected))
        period_start = full_end + timedelta(days=1)
    return tuple(periods)


def _add_months(value, months):
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _active_schedule_as_of(loan, as_of_date):
    schedules = RepaymentScheduleVersion.objects.filter(
        loan=loan,
        source_event__effective_date__lte=as_of_date,
    ).order_by("-version", "-pk")
    for schedule in schedules:
        terminations = schedule.changes.filter(
            kind=RepaymentScheduleChangeKind.TERMINATE,
            effective_date__lte=as_of_date,
        ).select_related("reversal")
        terminated = any(
            not hasattr(change, "reversal")
            or change.reversal.effective_date > as_of_date
            for change in terminations
        )
        if not terminated:
            return schedule
    return None


def _obligation_components_as_of(schedule, as_of_date):
    zero = ExposureComponent(Decimal("0"), Decimal("0"), Decimal("0"))
    if schedule is None:
        return zero, zero, zero, ()
    due_principal = due_interest = overdue_principal = overdue_interest = Decimal("0")
    remaining_principal = remaining_interest = Decimal("0")
    findings = []
    for obligation in schedule.obligations.order_by("due_date", "sequence"):
        principal_allocated = sum(
            (
                row.amount
                for row in obligation.allocations.filter(
                    component="PRINCIPAL",
                    source_event__effective_date__lte=as_of_date,
                )
            ), Decimal("0")
        )
        interest_allocated = sum(
            (
                row.amount
                for row in obligation.allocations.filter(
                    component="INTEREST",
                    source_event__effective_date__lte=as_of_date,
                )
            ), Decimal("0")
        )
        principal = obligation.principal_due - principal_allocated
        interest = obligation.interest_due - interest_allocated
        if principal < 0 or interest < 0:
            findings.append(f"Obligation {obligation.pk} is over-allocated.")
            continue
        remaining_principal += principal
        remaining_interest += interest
        if obligation.due_date <= as_of_date:
            due_principal += principal
            due_interest += interest
        if obligation.due_date < as_of_date:
            overdue_principal += principal
            overdue_interest += interest
    return (
        ExposureComponent(due_principal, due_interest, Decimal("0")),
        ExposureComponent(overdue_principal, overdue_interest, Decimal("0")),
        ExposureComponent(remaining_principal, remaining_interest, Decimal("0")),
        tuple(findings),
    )
