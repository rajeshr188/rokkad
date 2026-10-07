"""Workspace workflow choice and atomic owner review/disbursal."""
import hashlib
import json
from dataclasses import asdict

from django.core import signing
from django.db import transaction
from django.utils import timezone

from apps.configuration.models import PreferenceAuditLog
from apps.orgs.access import resolve_workspace_access
from apps.orgs.models import Company
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from .pawn_lifecycle import approve_pawn_loan, _validate_collateral_economics, approval_quote_evidence, _approval_payload
from .pawn_disbursal import disburse_pawn_loan
from .origination_settings import collateral_photos_required

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


def _review_values(loan, *, historical_context=None):
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
    contract = _approval_payload(loan, items, resolved).get("collateral_economics")
    return economics, digest, quotes["quotes"], contract


def review_values(loan, *, historical_context=None):
    # Keep the v1 fingerprint and public result intact for issued reviews.
    return _review_values(loan, historical_context=historical_context)[:3]


def _contract_digest(contract):
    return hashlib.sha256(json.dumps(contract, sort_keys=True, default=str).encode()).hexdigest()


def make_review(loan, *, actor=None, effective_date=None):
    economics, digest, _, contract = _review_values(loan)
    values = {"workspace": loan.workspace_id, "loan": loan.pk, "digest": digest}
    if actor is not None:
        effective_date = effective_date or timezone.localdate()
        values.update(version=2, actor=actor.pk, date=effective_date.isoformat(),
            contract=_contract_digest(contract), photos_required=collateral_photos_required(loan.workspace_id))
    return economics, signing.dumps(values, salt=SALT)


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
    if not isinstance(reviewed, dict) or reviewed.get("version") not in (None, 2):
        raise ValueError("The review is invalid. Review the loan again.")
    loan = PawnLoan.objects.select_for_update().select_related("borrower", "license", "series").get(
        pk=loan_id, workspace=workspace,
    )
    if reviewed.get("loan") != loan.pk or reviewed.get("workspace") != workspace.pk:
        raise ValueError("This review belongs to another loan.")
    proof = None
    if reviewed.get("version") == 2:
        if reviewed.get("actor") != actor.pk or reviewed.get("date") != effective_date.isoformat():
            raise ValueError("This review belongs to another payout date or signed-in user. Review again.")
        proof = {key: reviewed[key] for key in ("digest", "actor", "date", "contract", "photos_required")}
    if loan.state == "ACTIVE":
        if proof is not None:
            event = loan.loan_events.filter(event_kind="DISBURSAL", reversed_by_event__isnull=True).first()
            approval = loan.approval_snapshots.filter(pk=event.payload.get("disbursal", {}).get("approval_snapshot_id")).first() if event else None
            if approval is None or approval.payload.get("combined_review") != proof:
                raise ValueError("Another payout has already been recorded. Reload the loan.")
        return disburse_pawn_loan(loan.pk, actor=actor, effective_date=effective_date)
    if loan.state != "DRAFT":
        raise ValueError("Only a draft can use combined review and disbursal.")
    economics, digest, reviewed_quotes, contract = _review_values(loan)
    if reviewed.get("digest") != digest:
        raise ValueError("Loan details or rates changed. Review the updated summary before confirming.")
    if proof is not None and (proof["contract"] != _contract_digest(contract)
            or proof["photos_required"] != collateral_photos_required(workspace.pk)):
        raise ValueError("Loan policies changed. Review the updated summary before confirming.")
    approval = approve_pawn_loan(loan.pk, actor=actor, combined_review=proof)
    if approval.payload["origination_rates"]["quotes"] != reviewed_quotes:
        raise ValueError("Market quotes changed during confirmation. Review the loan again.")
    if approval.payload.get("collateral_economics") != contract:
        raise ValueError("Loan economics changed during confirmation. Review the loan again.")
    if proof is not None and approval.payload["collateral_photo_policy"]["required"] != proof["photos_required"]:
        raise ValueError("Loan policies changed during confirmation. Review the loan again.")
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
