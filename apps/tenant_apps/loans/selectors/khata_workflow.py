"""Advisory next steps from source facts; commands remain the final authority."""
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.domain.khata import anniversary, calculate_interest, Terms
from .khata_items import collateral_items


def activation_approvals(account, actor=None):
    if current_workspace_id() != account.workspace_id:
        raise ValueError("Khata workflow requires the matching Workspace context.")
    qs = account.operations.filter(kind="TERMS_OK")
    if account.state != "ACTIVE":
        return qs.none()
    proposal = account.agreement_revisions.order_by("-number").first()
    last = account.operations.order_by("-sequence").first()
    if not proposal or not last:
        return qs.none()
    qs = qs.filter(pk=last.pk, agreement=proposal, business_date=timezone.localdate(), withdrawals__isnull=True)
    approval = qs.select_related("agreement").first()
    if approval and actor is not None:
        # Reuse the command's exact stale-evidence comparison, without posting or locking.
        from apps.tenant_apps.loans.services.khata_revisions import _activation_review
        try:
            _activation_review(account, approval, timezone.localdate(), account.workspace, actor)
        except (ValueError, ValidationError, ObjectDoesNotExist):
            return qs.none()
    return qs


def workflow_state(account, *, summary=None, actor=None):
    if current_workspace_id() != account.workspace_id:
        raise ValueError("Khata workflow requires the matching Workspace context.")
    today = timezone.localdate()
    proposal = account.agreement_revisions.order_by("-number").first()
    activated = account.operations.filter(kind__in=("WITHDRAW", "REVISE")).select_related("agreement").order_by("-sequence").first()
    current = activated.agreement if activated else None
    approval = account.operations.filter(kind="TERMS_OK" if account.opened_on else "APPROVE").order_by("-sequence").first()
    pending = bool(proposal and (current is None or proposal.number > current.number))
    held = collateral_items(account, mode="held").exists()
    eligible = collateral_items(account, mode="outgoing").exists()
    returns = collateral_items(account, mode="pending").exists()
    valid_approval = activation_approvals(account, actor).first() if account.opened_on else None
    opening_approved = bool(approval and proposal and approval.agreement_id == proposal.pk and approval.business_date == today)
    status = "Closed" if account.state == "CLOSED" else "Cancelled" if account.state == "CANCELLED" else "Financially settled; actual returns remain" if account.settled_on else "Current agreement active" if current else "Opening proposal saved"
    if pending and account.state in ("DRAFT", "APPROVED", "ACTIVE"):
        status = "Proposal needs today's review" if proposal.intended_on != today else "Approved change awaiting activation" if valid_approval else "Opening approved; first withdrawal pending" if opening_approved and not account.opened_on else "Proposal awaiting approval"
    ready = dict(photo=held, handover=returns, **{"return-unopened": held, "cancel": not held,
        "approve": bool(account.series.is_active and eligible and proposal and proposal.intended_on == today),
        "approve-change": bool(pending and proposal.intended_on == today and not valid_approval
            and (account.series.is_active or current and proposal.agreed_limit <= current.agreed_limit)),
        "activate-change": bool(valid_approval)})
    ready["exchange"] = len(list(collateral_items(account, mode="outgoing").values_list("pk", flat=True)[:2])) >= 2 and collateral_items(account, mode="incoming").exists()
    if summary is not None and not summary.get("unavailable"):
        ready.update(interest=summary["due_interest"] > 0,
            finalize=any(p["complete"] and p["period_id"] is None for p in summary["schedule"]),
            withdraw=account.series.is_active and eligible and (summary["unused"] > 0 if account.opened_on else opening_approved))
    elif summary is not None:
        ready.update(interest=False, finalize=False, withdraw=False)
    steps = (["handover"] if account.settled_on else ["deposit"] if not eligible else
        ["proposal"] if pending and proposal.intended_on != today else
        ["activate-change"] if valid_approval else ["approve-change"] if pending and account.opened_on else
        ["approve"] if not account.opened_on and not opening_approved else ["interest", "handover", "withdraw", "proposal"])
    next_due = None
    if account.state == "ACTIVE" and summary is not None and not summary.get("unavailable"):
        from .khata_collections import collection_row
        next_due = collection_row(summary)["next_due"]
    return dict(status=status, proposal=proposal, current=current, active_source=activated, approval=approval,
        valid_approval=valid_approval, pending=pending, ready=ready, suggested=steps, held=held,
        opening_approved=opening_approved, next_due=next_due)


def opening_illustration(*, agreed_limit, monthly_rate, frequency, day=None):
    """Assume first payout on day, unchanged terms, and no receipts; no source writes."""
    day = day or timezone.localdate()
    due = anniversary(day, 12 if frequency == "ANNUAL" else 1)
    periods = calculate_interest(opened_on=day, through=due,
        terms=(Terms(day, agreed_limit, monthly_rate, 1),), frequency=frequency)
    return dict(opened_on=day, due_on=due, frequency=frequency,
        monthly_charge=periods[0].charge,
        first_bill=sum((p.charge for p in periods if p.due_on == due), Decimal(0)))
