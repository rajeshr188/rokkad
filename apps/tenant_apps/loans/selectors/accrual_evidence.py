"""Request-local source reads for canonical monthly interest calculations."""
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Prefetch, prefetch_related_objects

from apps.tenant_apps.loans.models import (
    PawnLoanEvent, PawnCollateralItem, PawnLoanDisbursalSnapshot,
    PawnLoanInterestAccrual, PawnLoanInterestAccrualLine,
    PawnLoanPrincipalOpeningLine, PawnLoanRepaymentAllocationLine,
    PawnLoanPrincipalClosingLine, current_tenant_workspace_id,
)
from .balances import calculate_pawn_loan_balance, _optional_policy_snapshot


@dataclass(frozen=True)
class PawnAccrualEvidence:
    loan: object
    events: tuple
    collateral: tuple
    disbursals: tuple
    accruals: tuple
    accrual_lines: tuple
    opening_lines: tuple
    repayment_lines: tuple
    closing_lines: tuple

    def require_loan(self, loan):
        if (current_tenant_workspace_id() is None
                or loan.workspace_id != current_tenant_workspace_id()
                or self.loan is not loan):
            raise ValueError("Accrual evidence requires its matching loan and Workspace.")

    def balance(self, day):
        self.require_loan(self.loan)
        return calculate_pawn_loan_balance(self.loan, events=self.events,
            collateral_items=self.collateral, policy_snapshot=_optional_policy_snapshot(self.loan),
            as_of_date=day, pending_delivery_blocks=False)

    def reversal_dates(self):
        return {event.reversal_of_id: event.effective_date for event in self.events
                if event.reversal_of_id}

    def active_event(self, event, day):
        reversed_on = self.reversal_dates().get(event.pk)
        return ((day is None or event.effective_date <= day)
                and (reversed_on is None or (day is not None and reversed_on > day)))

    def disbursal_at(self, day):
        return next((row for row in self.disbursals if self.active_event(row.loan_event, day)), None)

    def active_lines(self, lines, day):
        return tuple(row for row in lines if self.active_event(row.loan_event, day))

    def advance_consumed(self, day):
        from apps.tenant_apps.loans.services.agreement_corrections import agreement_revision
        revision = agreement_revision(self.loan)
        result = defaultdict(lambda: Decimal("0"))
        reversed_ids = self.reversal_dates()
        for row in self.accrual_lines:
            accrual = row.accrual
            if accrual.agreement_revision != revision:
                continue
            # Keep the existing all-date reversal exclusion, independently of
            # the policy/2 period-end cutoff. Do not reinterpret posted coverage.
            if accrual.loan_event_id in reversed_ids:
                continue
            if self.loan.policy_snapshot.policy_version == 2 and accrual.period_end > day:
                continue
            result[row.collateral_item_id] += row.advance_interest_applied
        return result


def load_pawn_accrual_evidence(loans):
    """Load once per call, with explicit Workspace ownership in every query."""
    loans = tuple(loans)
    if not loans:
        return {}
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None or any(loan.workspace_id != workspace_id for loan in loans):
        raise ValueError("Accrual evidence requires the loans' matching Workspace.")
    ids = [loan.pk for loan in loans]
    prefetch_related_objects(loans, Prefetch("loan_events",
        queryset=PawnLoanEvent.objects.filter(workspace_id=workspace_id)))
    models = (
        ("collateral", PawnCollateralItem.objects.filter(loan_id__in=ids)),
        ("disbursals", PawnLoanDisbursalSnapshot.objects.filter(loan_id__in=ids)
            .select_related("loan_event", "policy_snapshot")
            .order_by("-loan_event__effective_date", "-loan_event_id")),
        ("accruals", PawnLoanInterestAccrual.objects.filter(loan_id__in=ids)
            .select_related("release_catch_up__reversal").order_by("-period_number")),
        ("accrual_lines", PawnLoanInterestAccrualLine.objects.filter(accrual__loan_id__in=ids)
            .select_related("accrual")),
        ("opening_lines", PawnLoanPrincipalOpeningLine.objects.filter(loan_event__loan_id__in=ids)
            .select_related("loan_event").order_by("allocation_order")),
        ("repayment_lines", PawnLoanRepaymentAllocationLine.objects.filter(loan_event__loan_id__in=ids)
            .select_related("loan_event")
            .order_by("loan_event__effective_date", "loan_event_id", "allocation_order")),
        ("closing_lines", PawnLoanPrincipalClosingLine.objects.filter(loan_event__loan_id__in=ids)
            .select_related("loan_event")),
    )
    grouped = {}
    for name, queryset in models:
        rows = defaultdict(list)
        for row in queryset.filter(workspace_id=workspace_id):
            loan_id = row.accrual.loan_id if name == "accrual_lines" else (
                row.loan_event.loan_id if name.endswith("_lines") else row.loan_id)
            rows[loan_id].append(row)
        grouped[name] = rows
    return {loan.pk: PawnAccrualEvidence(loan=loan, events=tuple(loan.loan_events.all()),
        **{name: tuple(rows[loan.pk]) for name, rows in grouped.items()}) for loan in loans}
