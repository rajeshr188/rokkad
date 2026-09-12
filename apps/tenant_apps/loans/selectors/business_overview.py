"""Workspace business metrics from canonical records, without risk recalculation."""
from decimal import Decimal, InvalidOperation

from django.db.models import Count, Exists, OuterRef, Prefetch, Q
from django.utils import timezone

from apps.tenant_apps.party.facade import party_detail_queryset
from apps.tenant_apps.loans.models import PawnLoan, PawnLoanEvent, current_tenant_workspace_id
from .balances import (
    PawnLoanBalanceSelectorError, calculate_pawn_loan_balance,
    _optional_policy_snapshot,
)


ZERO = Decimal("0")
BALANCE_BATCH_SIZE = 250


def get_business_overview(*, workspace, activity_start=None, activity_end=None):
    if current_tenant_workspace_id() != workspace.pk:
        raise ValueError("Business overview requires the matching Workspace context.")
    today = timezone.localdate()
    if activity_start is not None or activity_end is not None:
        if not activity_start or not activity_end or not activity_start <= activity_end <= today:
            raise ValueError("Invalid activity dates.")
        if (activity_end - activity_start).days >= 366:
            raise ValueError("Activity is limited to 366 days.")

    loans = PawnLoan.objects.filter(workspace_id=workspace.pk)
    active = loans.filter(state="ACTIVE")
    # Count customer-role profiles and actual borrowers, including archived history.
    # A supplier without a customer role or loan is not a customer.
    customers = party_detail_queryset().filter(workspace_id=workspace.pk).filter(
        Q(roles__role_type__key="CUSTOMER", roles__status="ACTIVE")
        | Q(pk__in=loans.values("borrower_id"))
    ).values("pk").distinct().count()
    counts = active.aggregate(active_loans=Count("pk"), active_borrowers=Count("borrower_id", distinct=True))

    principal = interest = ZERO
    unavailable = 0
    events = PawnLoanEvent.objects.filter(workspace_id=workspace.pk, effective_date__lte=today)
    # Share the repayment/reversal fold, batch database reads, and bound retained
    # models to one batch. No schedule, appraisal, price or health calculation.
    rows = active.select_related("policy_snapshot").prefetch_related(Prefetch(
        "loan_events", queryset=events.only("pk", "loan_id", "event_kind", "effective_date", "payload"),
        to_attr="dashboard_events",
    )).order_by("pk")
    for loan in rows.iterator(chunk_size=BALANCE_BATCH_SIZE):
        try:
            for event in loan.dashboard_events:
                if not isinstance(event.payload, dict) or not isinstance(event.payload.get("values", {}), dict):
                    raise PawnLoanBalanceSelectorError("Malformed event evidence.")
                if event.event_kind == "REVERSAL" and not isinstance(event.payload.get("reversal"), dict):
                    raise PawnLoanBalanceSelectorError("Malformed reversal evidence.")
            balance = calculate_pawn_loan_balance(loan, events=loan.dashboard_events,
                collateral_items=(), policy_snapshot=_optional_policy_snapshot(loan),
                as_of_date=today, pending_delivery_blocks=False)
            if balance.principal_disbursed + balance.principal_capitalized <= ZERO:
                raise PawnLoanBalanceSelectorError("Active loan has no opening balance.")
            if not balance.principal_outstanding.is_finite() or not balance.interest_outstanding.is_finite():
                raise PawnLoanBalanceSelectorError("Non-finite recorded balance.")
            principal += balance.principal_outstanding
            interest += balance.interest_outstanding
        except (PawnLoanBalanceSelectorError, ValueError, InvalidOperation, TypeError):
            unavailable += 1

    result = dict(as_of_date=today, total_customers=customers, **counts,
        principal_outstanding=principal if not unavailable else None,
        interest_outstanding=interest if not unavailable else None,
        unavailable_balance_count=unavailable, activity=None)
    if activity_start is not None:
        result["activity"] = _activity(workspace.pk, activity_start, activity_end, today)
    return result


def _activity(workspace_id, start, end, today):
    # Reversed issues are excluded using today's knowledge even when the reversal
    # falls outside the selected issue period. Closed loans remain historical issues.
    reversals = PawnLoanEvent.objects.filter(workspace_id=workspace_id,
        reversal_of_id=OuterRef("pk"), effective_date__lte=today)
    openings = PawnLoanEvent.objects.filter(workspace_id=workspace_id,
        effective_date__range=(start, end), event_kind__in=("DISBURSAL", "RENEWAL_OPENING"),
    ).filter(~Exists(reversals))
    counts = openings.aggregate(
        new_loans=Count("pk", filter=Q(event_kind="DISBURSAL")),
        renewals=Count("pk", filter=Q(event_kind="RENEWAL_OPENING")),
    )
    cash = ZERO
    unavailable = 0
    for payload in openings.filter(event_kind="DISBURSAL").values_list("payload", flat=True).iterator(chunk_size=1000):
        try:
            values = payload["values"]
            if not isinstance(values, dict):
                raise ValueError("Malformed disbursal cash evidence.")
            # Legacy principal-only disbursals have no deductions in their contract.
            amount = Decimal(str(values.get("net_cash", values["principal"])))
            principal = Decimal(str(values["principal"]))
            if not amount.is_finite() or not principal.is_finite() or not ZERO < amount <= principal:
                raise ValueError("Invalid disbursal cash evidence.")
            cash += amount
        except (KeyError, TypeError, ValueError, InvalidOperation):
            unavailable += 1
    days = (end - start).days + 1
    return dict(start=start, end=end, calendar_days=days, **counts,
        average_per_day=Decimal(counts["new_loans"]) / Decimal(days),
        new_loan_cash=cash if not unavailable else None,
        unavailable_cash_count=unavailable)
