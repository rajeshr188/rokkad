from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans.models import (
    RepaymentScheduleChangeKind,
    RepaymentScheduleVersion,
)


ZERO = Decimal("0")


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


def calculate_obligation_state_as_of(schedule, as_of_date):
    zero = ObligationAmount(ZERO, ZERO)
    if schedule is None:
        return PawnLoanObligationState(None, "", None, (), zero, zero, zero, ())

    due_principal = due_interest = overdue_principal = overdue_interest = ZERO
    remaining_principal = remaining_interest = ZERO
    rows = []
    findings = []
    for obligation in schedule.obligations.order_by("due_date", "sequence"):
        allocated = {"PRINCIPAL": ZERO, "INTEREST": ZERO}
        for allocation in obligation.allocations.filter(
            source_event__effective_date__lte=as_of_date
        ):
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
    return PawnLoanObligationState(
        schedule_id=schedule.pk,
        schedule_fingerprint=schedule.fingerprint,
        maturity_date=schedule.maturity_date,
        obligations=tuple(rows),
        due_now=ObligationAmount(due_principal, due_interest),
        overdue=ObligationAmount(overdue_principal, overdue_interest),
        remaining=ObligationAmount(remaining_principal, remaining_interest),
        integrity_findings=tuple(findings),
    )

