"""Workspace workflow choice and atomic owner review/disbursal."""
import hashlib
import json
from dataclasses import asdict

from django.core import signing
from django.db import transaction

from apps.configuration.models import PreferenceAuditLog
from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from .pawn_lifecycle import approve_pawn_loan, _validate_collateral_economics, approval_quote_evidence
from .pawn_disbursal import disburse_pawn_loan

SALT = "loans.owner-review.v1"


def _owner(workspace, actor):
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    access.require("workspace.transfer")
    access.require("loan.approve")
    access.require("loan.disburse")


@transaction.atomic
def set_loan_workflow(*, actor, mode):
    workspace = Company.objects.select_for_update().get(pk=current_tenant_workspace_id())
    _owner(workspace, actor)
    if mode not in {"SIMPLE", "EXTENDED"}:
        raise ValueError("Select a valid loan workflow.")
    previous = workspace.loan_workflow
    if previous != mode:
        workspace.loan_workflow = mode
        workspace.save(update_fields=["loan_workflow"])
        PreferenceAuditLog.objects.create(
            scope="workspace", key="loan.workflow", workspace=workspace,
            changed_by=actor, old_value=previous, new_value=mode,
        )
    return workspace


def review_values(loan, *, historical_context=None):
    """Fingerprint persisted input and newly resolved economics; no writes."""
    items = tuple(loan.collateral_items.order_by("pk"))
    resolved = _validate_collateral_economics(loan, items, historical_context=historical_context)
    economics = resolved.economics if resolved else None
    quotes = approval_quote_evidence(loan, items, resolved)
    payload = {
        "loan": PawnLoan.objects.filter(pk=loan.pk).values().get(),
        "borrower": str(loan.borrower.display_name),
        "collateral": list(loan.collateral_items.order_by("pk").values()),
        "photos": [list(item.photos.order_by("pk").values()) for item in items],
        "economics": asdict(economics) if economics else None,
        "valuation_quotes": quotes["quotes"],
        "quote_age_rule": {"rule": quotes["rule"],
            "maximum_quote_age_days": quotes.get("maximum_quote_age_days")},
        "policy_ids": ([resolved.economic_policy.pk, [p.pk for p in resolved.rate_policies],
                        [p.pk for p in resolved.fee_policies]] if resolved else None),
        "basis_approval_id": (historical_context["approval"].pk
            if historical_context and historical_context["approval"] else None),
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
    return economics, digest, quotes["quotes"]


def make_review(loan):
    economics, digest, _ = review_values(loan)
    return economics, signing.dumps({"workspace": loan.workspace_id, "loan": loan.pk, "digest": digest}, salt=SALT)


@transaction.atomic
def review_and_disburse(loan_id, *, actor, effective_date, token):
    workspace = Company.objects.select_for_update().get(pk=current_tenant_workspace_id())
    _owner(workspace, actor)
    if workspace.loan_workflow != "SIMPLE":
        raise ValueError("This Workspace uses separate approval and disbursal. Reload the loan.")
    try:
        reviewed = signing.loads(token, salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("The review has expired or is invalid. Review the loan again.") from exc
    loan = PawnLoan.objects.select_for_update().select_related("borrower", "license", "series").get(
        pk=loan_id, workspace=workspace,
    )
    if reviewed.get("loan") != loan.pk or reviewed.get("workspace") != workspace.pk:
        raise ValueError("This review belongs to another loan.")
    if loan.state == "ACTIVE":
        return disburse_pawn_loan(loan.pk, actor=actor, effective_date=effective_date)
    if loan.state != "DRAFT":
        raise ValueError("Only a draft can use combined review and disbursal.")
    economics, digest, reviewed_quotes = review_values(loan)
    if reviewed.get("digest") != digest:
        raise ValueError("Loan details or rates changed. Review the updated summary before confirming.")
    approval = approve_pawn_loan(loan.pk, actor=actor)
    if approval.payload["origination_rates"]["quotes"] != reviewed_quotes:
        raise ValueError("Market quotes changed during confirmation. Review the loan again.")
    if economics:
        frozen = approval.payload.get("collateral_economics", {})
        for name in ("net_disbursed", "advance_interest", "deducted_fees", "monthly_interest"):
            if frozen.get(name) != str(getattr(economics, name)):
                raise ValueError("Loan economics changed during confirmation. Review the loan again.")
    return disburse_pawn_loan(loan.pk, actor=actor, effective_date=effective_date)


EARLIER_SALT = "loans.earlier-payout-review.v1"


def make_earlier_payout_review(loan, *, actor):
    from .historical_origination import authorize, historical_basis
    authorize(loan, actor)
    context = historical_basis(loan)
    economics, digest, quotes = review_values(loan, historical_context=context)
    token = signing.dumps({"workspace": loan.workspace_id, "loan": loan.pk,
        "actor": actor.pk, "date": loan.loan_date.isoformat(), "digest": digest}, salt=EARLIER_SALT)
    return economics, token, quotes, context["approval"]


@transaction.atomic
def record_earlier_payout(loan_id, *, actor, token, reason, confirmed=False):
    from .historical_origination import authorize, historical_basis
    workspace = Company.objects.select_for_update().get(pk=current_tenant_workspace_id())
    loan = PawnLoan.objects.select_for_update().select_related("borrower", "license", "series").get(
        pk=loan_id, workspace=workspace)
    authorize(loan, actor)
    if confirmed is not True:
        raise ValueError("Confirm that the money was actually paid on the recorded loan date.")
    try:
        reviewed = signing.loads(token, salt=EARLIER_SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("The earlier-payout review expired. Refresh and review it again.") from exc
    if (reviewed.get("workspace") != workspace.pk or reviewed.get("loan") != loan.pk
            or reviewed.get("actor") != actor.pk or reviewed.get("date") != loan.loan_date.isoformat()):
        raise ValueError("This review belongs to another loan, date or signed-in user.")
    if loan.state == "ACTIVE":
        event = loan.loan_events.filter(event_kind="DISBURSAL", reversed_by_event__isnull=True).first()
        recording = event.payload.get("earlier_payout", {}) if event else {}
        if recording.get("review_digest") != reviewed["digest"] or recording.get("recorded_by_id") != actor.pk:
            raise ValueError("Another payout has already been recorded. Reload the loan.")
        return disburse_pawn_loan(loan.pk, actor=actor, effective_date=loan.loan_date)
    context = historical_basis(loan)
    economics, digest, quotes = review_values(loan, historical_context=context)
    if reviewed.get("digest") != digest:
        raise ValueError("Loan details or historical evidence changed. Refresh the review before confirming.")
    approval = approve_pawn_loan(loan.pk, actor=actor, earlier_payout_reason=reason,
        earlier_review_digest=digest)
    if approval.payload["origination_rates"]["quotes"] != quotes:
        raise ValueError("Historical quotes changed during recording. Review again.")
    for name in ("net_disbursed", "advance_interest", "deducted_fees", "monthly_interest"):
        if approval.payload["collateral_economics"].get(name) != str(getattr(economics, name)):
            raise ValueError("Historical economics changed during recording. Review again.")
    return disburse_pawn_loan(loan.pk, actor=actor, effective_date=loan.loan_date,
        earlier_payout_reason=reason)
