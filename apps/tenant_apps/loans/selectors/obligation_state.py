from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from django.db.models import F, Prefetch, prefetch_related_objects, Case, When, Value, BooleanField

from apps.tenant_apps.loans.models import (
    ObligationAllocation,
    RepaymentObligation,
    RepaymentScheduleChange,
    current_tenant_workspace_id,
    RepaymentScheduleChangeKind,
    RepaymentScheduleVersion,
)


ZERO = Decimal("0")


def _native_monthly_marker():
    return Case(When(loan__state="ACTIVE", loan__policy_snapshot__policy_version=2,
        loan__policy_snapshot__interest_method="SIMPLE", loan__policy_snapshot__partial_month_method="FULL_MONTH",
        loan__product_version__repayment_structure__in=("SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT"),
        schedule_version__source_event__event_kind__in=("DISBURSAL", "RENEWAL_OPENING", "MIGRATION_OPENING"), then=Value(True)),
        default=Value(False), output_field=BooleanField())


@dataclass(frozen=True)
class ObligationAmount:
    principal: Decimal
    interest: Decimal
    fees: Decimal = ZERO

    @property
    def total(self):
        return self.principal + self.interest + self.fees


@dataclass(frozen=True)
class UnpaidObligationState:
    obligation_id: int
    due_date: date
    principal: Decimal
    interest: Decimal

    @property
    def total(self):
        return self.principal + self.interest


@dataclass(frozen=True)
class PawnLoanObligationState:
    schedule_id: int | None
    schedule_fingerprint: str
    maturity_date: date | None
    obligations: tuple[UnpaidObligationState, ...]
    due_now: ObligationAmount
    overdue: ObligationAmount
    remaining: ObligationAmount
    integrity_findings: tuple[str, ...]


def get_active_repayment_schedule_as_of(loan, as_of_date):
    schedules = RepaymentScheduleVersion.objects.filter(
        loan=loan,
        source_event__effective_date__lte=as_of_date,
    ).select_related("loan__policy_snapshot").order_by("-version", "-pk")
    for schedule in schedules:
        terminations = schedule.changes.filter(
            kind=RepaymentScheduleChangeKind.TERMINATE,
            effective_date__lte=as_of_date,
        ).select_related("reversal")
        if not _is_terminated(terminations, as_of_date):
            return schedule
    return None


def _is_terminated(terminations, as_of_date):
    return any(
        not hasattr(change, "reversal")
        or change.reversal.effective_date > as_of_date
        for change in terminations
    )


def get_obligation_states_for_loans(*, workspace, loan_ids, as_of_date):
    """Batch current evidence reads; return date-specific states, never cached models."""
    if current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Obligation states require the matching Workspace context.")
    loan_ids = tuple(set(loan_ids))
    if not loan_ids:
        return {}
    schedules = RepaymentScheduleVersion.objects.filter(
        workspace=workspace, loan_id__in=loan_ids,
        source_event__effective_date__lte=as_of_date,
    ).select_related("loan__policy_snapshot").order_by("loan_id", "-version", "-pk").prefetch_related(Prefetch(
        "changes",
        queryset=RepaymentScheduleChange.objects.filter(
            workspace=workspace, kind=RepaymentScheduleChangeKind.TERMINATE,
            effective_date__lte=as_of_date,
        ).select_related("reversal"),
        to_attr="dashboard_terminations",
    ))
    selected = {}
    for schedule in schedules:
        if schedule.loan_id not in selected and not _is_terminated(schedule.dashboard_terminations, as_of_date):
            selected[schedule.loan_id] = schedule
    prefetch_related_objects(list(selected.values()), Prefetch(
        "obligations",
        queryset=RepaymentObligation.objects.filter(workspace=workspace).annotate(
            recorded_profile=F("schedule_version__source_event__payload__recording__collection_profile"),
            monthly_native=_native_monthly_marker(),
        ).order_by("due_date", "sequence").prefetch_related(Prefetch(
            "allocations",
            queryset=ObligationAllocation.objects.filter(
                workspace=workspace, source_event__effective_date__lte=as_of_date,
            ),
            to_attr="dashboard_allocations",
        )),
        to_attr="dashboard_obligations",
    ))
    states = {loan_id: calculate_obligation_state_as_of(None, as_of_date) for loan_id in loan_ids}
    for loan_id, schedule in selected.items():
        states[loan_id] = _fold_obligation_state(
            schedule, as_of_date, schedule.dashboard_obligations,
            lambda obligation: obligation.dashboard_allocations,
        )
    return states


def calculate_obligation_state_as_of(schedule, as_of_date, *, adjust_recorded=True):
    return _fold_obligation_state(
        schedule, as_of_date,
        schedule.obligations.annotate(
            recorded_profile=F("schedule_version__source_event__payload__recording__collection_profile"),
            monthly_native=_native_monthly_marker(),
        ).order_by("due_date", "sequence").prefetch_related(Prefetch(
            "allocations",
            queryset=ObligationAllocation.objects.filter(source_event__effective_date__lte=as_of_date),
            to_attr="as_of_allocations",
        )) if schedule else (),
        lambda obligation: obligation.as_of_allocations,
        adjust_recorded=adjust_recorded,
    )


def _fold_obligation_state(schedule, as_of_date, obligations, allocations_for, *, adjust_recorded=True):
    zero = ObligationAmount(ZERO, ZERO)
    if schedule is None:
        return PawnLoanObligationState(None, "", None, (), zero, zero, zero, ())

    due_principal = due_interest = overdue_principal = overdue_interest = ZERO
    remaining_principal = remaining_interest = ZERO
    rows = []
    findings = []
    recorded_profile = None
    monthly_native = False
    for obligation in obligations:
        recorded_profile = getattr(obligation, "recorded_profile", None)
        monthly_native = getattr(obligation, "monthly_native", False)
        allocated = {"PRINCIPAL": ZERO, "INTEREST": ZERO}
        for allocation in allocations_for(obligation):
            allocated[allocation.component] += allocation.amount
        principal = obligation.principal_due - allocated["PRINCIPAL"]
        interest = obligation.interest_due - allocated["INTEREST"]
        rows.append(
            UnpaidObligationState(
                obligation_id=obligation.pk,
                due_date=obligation.due_date,
                principal=principal,
                interest=interest,
            )
        )
        if principal < ZERO or interest < ZERO:
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
    result = PawnLoanObligationState(
        schedule_id=schedule.pk,
        schedule_fingerprint=schedule.fingerprint,
        maturity_date=schedule.maturity_date,
        obligations=tuple(rows),
        due_now=ObligationAmount(due_principal, due_interest),
        overdue=ObligationAmount(overdue_principal, overdue_interest),
        remaining=ObligationAmount(remaining_principal, remaining_interest),
        integrity_findings=tuple(findings),
    )
    if adjust_recorded and (recorded_profile in ("recorded-anniversary/1", "recorded-anniversary/2", "recorded-anniversary/3")
            or monthly_native):
        return _monthly_obligation_state(schedule, as_of_date, result)
    return result


def _monthly_obligation_state(schedule, day, raw):
    """Read the agreed variable-principal bullet debt without rewriting its schedule.

    The ordinary immutable schedule retains the original maturity and allocation
    capacity. Its original fixed interest projection is not a debt after receipts.
    Future projections may use only transactions known at the requested date.
    """
    from .continuation import resolve_loan_continuation, RECORDED_PROFILES
    loan = schedule.loan
    horizon = max(day, schedule.maturity_date)
    position = resolve_loan_continuation(loan, as_of_date=day, forecast_through=horizon)
    if position.contract.profile not in RECORDED_PROFILES:
        from apps.tenant_apps.loans.services.pawn_interest import started_month_charge_allowed
        if (schedule.source_event.event_kind not in ("DISBURSAL", "RENEWAL_OPENING", "MIGRATION_OPENING")
                or loan.state != "ACTIVE" or not started_month_charge_allowed(loan.policy_snapshot)
                or loan.policy_snapshot.basis == "RECORDED_CONTRACT" or loan.product_version.repayment_structure not in (
                "SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT")):
            return raw
    balance = position.recorded_balance
    extra = position.recognition.additional_interest
    remaining = ObligationAmount(balance.principal_outstanding, balance.interest_outstanding + extra)
    zero = ObligationAmount(ZERO, ZERO)
    row = UnpaidObligationState(raw.obligations[0].obligation_id, schedule.maturity_date,
                               remaining.principal, remaining.interest)
    return replace(raw, obligations=(row,), remaining=remaining,
        due_now=remaining if schedule.maturity_date <= day else zero,
        overdue=remaining if schedule.maturity_date < day else zero)
