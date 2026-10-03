"""Canonical khata balances and read-only interest illustrations."""
from decimal import Decimal

from django.db.models import Sum
from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.domain.khata import DrawPosition, Terms, calculate_interest, revise_limit
from apps.tenant_apps.loans.models import KhataAccount, KhataInterestAllocation, KhataCollateralSelection
from apps.tenant_apps.loans.services.action_access import require_workspace_action


def activated_agreements(account):
    if hasattr(account, "summary_operations"):
        first = next((op for op in account.summary_operations if op.kind == "WITHDRAW"), None)
        return () if first is None else (first, *(op for op in account.summary_operations if op.kind == "REVISE"))
    first = account.operations.filter(kind="WITHDRAW").select_related("agreement").order_by("sequence").first()
    if first is None:
        return ()
    return (first, *account.operations.filter(kind="REVISE").select_related("agreement").order_by("sequence"))


def effective_agreement(account):
    changes = activated_agreements(account)
    if hasattr(account, "summary_agreements"):
        return changes[-1].agreement if changes else next(iter(account.summary_agreements), None)
    return changes[-1].agreement if changes else account.agreement_revisions.order_by("-number").first()


def calculated_interest_periods(account, through):
    """Only financially activated terms count, never unapproved proposals."""
    changes = activated_agreements(account)
    if not changes:
        return ()
    first = changes[0]
    if account.settled_on:
        through = min(through, account.settled_on)
    return calculate_interest(opened_on=first.business_date, through=through,
        terms=tuple(Terms(op.business_date, op.agreement.agreed_limit, op.agreement.monthly_rate,
            op.agreement.number) for op in changes), frequency=first.agreement.frequency)


def interest_schedule(account, through):
    """Saved charges are authoritative; unfinalized periods remain calculations."""
    saved = {p.index: p for p in account.interest_periods.all()}
    if hasattr(account, "summary_allocations"):
        paid = {}
        for allocation in account.summary_allocations:
            paid[allocation.period_id] = paid.get(allocation.period_id, Decimal(0)) + allocation.amount
    else:
        paid = {r["period_id"]: r["total"] for r in KhataInterestAllocation.objects
            .filter(period__account=account, operation__corrected_by__isnull=True).values("period_id").annotate(total=Sum("amount"))}
    rows = []
    for period in calculated_interest_periods(account, through):
        frozen = saved.get(period.index)
        charge = frozen.charge if frozen else period.charge
        received = (paid.get(frozen.pk) or Decimal(0)) if frozen else Decimal(0)
        rows.append(dict(index=period.index, period_id=frozen.pk if frozen else None,
            start_on=frozen.start_on if frozen else period.start,
            end_on=frozen.end_on if frozen else period.end,
            due_on=frozen.due_on if frozen else period.due_on,
            charge=charge, paid=received, outstanding=charge - received,
            complete=period.charged_through == period.end))
    return rows


def held_items(account):
    """Custody is derived from receipt and actual return sources, never a form flag."""
    return account.collateral.exclude(operations__kind__in=("RETURN", "HANDOVER")).order_by("pk")


def eligible_items(account):
    reserved = KhataCollateralSelection.objects.filter(role="OUT", operation__account=account,
        operation__corrected_by__isnull=True).values("item_id")
    return held_items(account).exclude(pk__in=reserved)


def account_position(account):
    position = None
    operations = account.summary_operations if hasattr(account, "summary_operations") else list(account.operations.select_related("agreement").order_by("sequence"))
    for op in operations:
        if op.kind not in ("WITHDRAW", "REVISE"):
            continue
        if op.kind == "REVISE":
            position = revise_limit(position, new_limit=op.agreement.agreed_limit, principal_repayment=op.amount)
        else:
            if position is None:
                position = DrawPosition(op.agreement.agreed_limit, Decimal(0), op.agreement.agreed_limit)
            position = DrawPosition(position.limit, position.principal + op.amount, position.unused - op.amount)
    if position and any(op.kind == "SETTLE" for op in operations):
        position = DrawPosition(position.limit, Decimal(0), Decimal(0))
    return position


def account_balances(*, workspace, actor, account_id, as_of=None):
    """Receipts reduce dues, but never principal or unused borrowing entitlement."""
    from django.utils import timezone
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.view")
        account = KhataAccount.objects.get(workspace=workspace, pk=account_id)
        day = as_of or timezone.localdate()
        # Historical/future balance reconstruction is not implied by today's source sum.
        if day != timezone.localdate():
            raise ValueError("Khata balances currently support today's business date only.")
        position = account_position(account)
        periods = interest_schedule(account, day) if position else ()
        return dict(principal=position.principal if position else Decimal(0),
            unused=position.unused if position else Decimal(0), opened=position is not None,
            calculated_interest=sum((p["charge"] for p in periods), Decimal(0)),
            paid_interest=sum((p["paid"] for p in periods), Decimal(0)),
            outstanding_interest=sum((p["outstanding"] for p in periods), Decimal(0)),
            due_interest=sum((p["outstanding"] for p in periods if p["due_on"] <= day), Decimal(0)),
            overdue_interest=sum((p["outstanding"] for p in periods if p["due_on"] < day), Decimal(0)))


def preview_draft_interest(*, workspace, actor, account_id, through):
    with workspace_context(workspace.pk):
        require_workspace_action(workspace, actor, "data.view")
        account = KhataAccount.objects.get(workspace=workspace, pk=account_id, state="DRAFT")
        revision = account.agreement_revisions.order_by("-number").first()
        if revision is None:
            raise ValueError("No agreement proposal exists for this draft.")
        # Earlier draft proposals never became effective financial revisions.
        return calculate_interest(opened_on=revision.intended_on, through=through,
            terms=(Terms(revision.intended_on, revision.agreed_limit, revision.monthly_rate, revision.number),),
            frequency=revision.frequency)
