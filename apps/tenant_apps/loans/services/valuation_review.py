"""Review and replace an unpaid loan's approval without recording a payout."""
import hashlib
import json
from dataclasses import asdict
from decimal import Decimal

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.selectors.origination_rates import (
    assert_approved_quotes_current, get_origination_quote_rows, requires_quotes,
)
from .action_access import require_loan_action
from .pawn_drafts import CollateralDraftInput, UpdatePawnDraftCommand, update_pawn_draft
from .pawn_economics import resolve_pawn_draft_economics
from .pawn_lifecycle import approve_pawn_loan, reopen_pawn_loan

SALT = "loans.updated-valuation-review.v1"


def valuation_refresh_reason(loan, approval=None):
    if loan.state != "APPROVED":
        return None
    approval = approval or loan.approval_snapshots.order_by("-version").first()
    if (not approval or approval.payload.get("earlier_payout")
            or not approval.payload.get("collateral_economics") or loan.loan_events.exists()):
        return None
    evidence = approval.payload.get("origination_rates", {})
    method = evidence.get("valuation_method")
    if not method or not requires_quotes(method):
        return None
    try:
        assert_approved_quotes_current(workspace_id=loan.workspace_id, method=method,
            evidence=evidence, effective_date=timezone.localdate())
    except ValueError:
        return "The approved price records are no longer current. Review today's prices and terms before paying the borrower."
    return None


def _scoped(loan):
    if current_workspace_id() != loan.workspace_id:
        raise PermissionDenied("Valuation review requires the active workspace.")


def _eligible(loan):
    _scoped(loan)
    if loan.state != "APPROVED" or loan.loan_events.exists():
        raise ValueError("Use updated valuation for an approved native loan with no recorded payout or other financial events.")
    approval = loan.approval_snapshots.order_by("-version").first()
    if not approval or not approval.payload.get("collateral_economics") or approval.payload.get("earlier_payout"):
        raise ValueError("This loan does not have an ordinary itemized approval. Use its existing correction or earlier-payout workflow.")
    return approval


def _inputs(items):
    return tuple(CollateralDraftInput(collateral_item_id=item.pk, **{
        name: getattr(item, name) for name in ("description", "metal", "gross_weight", "net_weight",
            "purity_percentage", "latest_appraised_value", "allocated_principal", "quantity",
            "interest_rate_override", "interest_override_reason")}) for item in items)


def _policy_values(row):
    return {field.attname: getattr(row, field.attname) for field in row._meta.concrete_fields}


def preview_updated_valuation(loan, *, actor):
    _scoped(loan)
    require_loan_action(loan, actor, "data.view")
    approval = _eligible(loan)
    today = timezone.localdate()
    items = tuple(loan.collateral_items.order_by("pk"))
    old_quotes = approval.payload.get("origination_rates", {}).get("quotes", {})
    rows = get_origination_quote_rows(workspace_id=loan.workspace_id, loan_date=today,
        metals=tuple(item.metal for item in items))
    quotes = [{"metal": row["metal"], "old": old_quotes.get(row["metal"]),
        "current": row["evidence"], "fresh": row["fresh"], "age_days": row["age_days"],
        "maximum_age_days": row["maximum_age_days"]} for row in rows]
    for quote in quotes:
        for key in ("old", "current"):
            value = (quote[key] or {}).get("effective_at")
            quote[key + "_date"] = timezone.localdate(parse_datetime(value)) if value else None
    resolved, error, token = None, None, None
    try:
        resolved = resolve_pawn_draft_economics(workspace_id=loan.workspace_id,
            license_id=loan.license_id, series_id=loan.series_id, as_of_date=today,
            collateral=items, require_fresh_rates=True)
    except (ValueError, ValidationError) as exc:
        error = str(exc)
    if resolved:
        basis = {
            "loan": _policy_values(loan), "approval": approval.fingerprint,
            "items": [_policy_values(item) for item in items],
            "photos": [list(item.photos.order_by("pk").values()) for item in items],
            "economics": asdict(resolved.economics), "quotes": resolved.valuation_quotes,
            "maximum_quote_age_days": resolved.maximum_quote_age_days,
            "policies": [_policy_values(row) for row in
                (resolved.economic_policy, *resolved.rate_policies, *resolved.fee_policies)],
            "today": today,
        }
        digest = hashlib.sha256(json.dumps(basis, sort_keys=True, default=str).encode()).hexdigest()
        token = signing.dumps({"workspace": loan.workspace_id, "loan": loan.pk,
            "actor": actor.pk, "date": today.isoformat(), "digest": digest}, salt=SALT)
    old = dict(approval.payload["collateral_economics"], gross_principal=approval.payload["principal_amount"])
    old_tranches = {row["collateral_item_id"]: row for row in old.get("tranches", [])}
    item_rows = [{"description": item.description, "principal": item.allocated_principal,
        "old": old_tranches.get(item.pk),
        "current": resolved.economics.tranches[index - 1] if resolved else None}
        for index, item in enumerate(items, start=1)]
    totals = [{"label": label, "old": old.get(key),
        "current": getattr(resolved.economics, key) if resolved else None}
        for key, label in (("gross_principal", "Principal"), ("monthly_interest", "Monthly interest"),
            ("advance_interest", "Advance interest deducted"), ("deducted_fees", "Fees deducted"),
            ("net_disbursed", "Net cash to pay"))]
    policy_rows = []
    for key, label in (("valuation_method", "Valuation method"), ("interest_method", "Interest method"),
            ("minimum_first_month", "Full first month minimum"),
            ("advance_interest_periods", "Advance-interest periods"), ("partial_month_method", "Part-month interest"),
            ("partial_month_cutoff_days", "Part-month cutoff days"), ("partial_month_lower_fraction", "Part-month fraction"),
            ("capitalization_interval_periods", "Capitalization interval"), ("rounding_method", "Rounding method"),
            ("currency_quantum", "Rounding unit")):
        def display(value):
            return str(value).replace("_", " ").capitalize() if value is not None else "Not yet validated"
        policy_rows.append({"label": label, "old": display(old.get(key)),
            "current": display(getattr(resolved.economic_policy, key)) if resolved else "Not yet validated"})
    return {"approval": approval, "today": today, "quotes": quotes, "totals": totals,
        "old_economics": old, "resolved": resolved, "items": items,
        "item_rows": item_rows, "old_ltv": Decimal(old["maximum_ltv_ratio"]) * 100,
        "policy_rows": policy_rows,
        "current_ltv": resolved.economic_policy.maximum_ltv_ratio * 100 if resolved else None,
        "error": error, "token": token}


@transaction.atomic
def confirm_updated_valuation(loan_id, *, actor, token, unpaid=False):
    workspace = Company.objects.select_for_update().get(pk=current_workspace_id())
    loan = PawnLoan.objects.select_for_update().select_related("workspace", "series", "license").get(
        workspace=workspace, pk=loan_id)
    require_loan_action(loan, actor, "data.edit", "loan.approve")
    if unpaid is not True:
        raise ValueError("Confirm that no cash has been paid for this loan. Money already paid needs the earlier-payout workflow.")
    try:
        reviewed = signing.loads(token or "", salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError("This review has expired or is invalid. Open a fresh valuation review.") from exc
    if (reviewed.get("workspace") != workspace.pk or reviewed.get("loan") != loan.pk
            or reviewed.get("actor") != actor.pk):
        raise PermissionDenied("This valuation review belongs to another loan, workspace or signed-in user.")
    # Durable replay identity lives in the immutable approval, not a browser flag.
    completed = loan.approval_snapshots.filter(
        payload__valuation_review__digest=reviewed["digest"], approved_by=actor).first()
    if completed:
        return loan, False
    if reviewed.get("date") != timezone.localdate().isoformat():
        raise ValueError("The day changed. Review today's prices again.")
    preview = preview_updated_valuation(loan, actor=actor)
    if preview["error"]:
        raise ValueError(preview["error"])
    fresh = signing.loads(preview["token"], salt=SALT)
    if fresh["digest"] != reviewed["digest"]:
        raise ValueError("Loan details, prices or policies changed. Open a fresh valuation review before confirming.")
    economics = preview["resolved"].economics
    marker = {"digest": reviewed["digest"], "actor_id": actor.pk,
        "previous_approval_id": preview["approval"].pk, "previous_loan_date": loan.loan_date.isoformat(),
        "reviewed_date": preview["today"].isoformat(), "cash_not_paid": True}
    reopen_pawn_loan(loan.pk, actor=actor, reason="Updated valuation reviewed before cash payment.")
    update_pawn_draft(loan.pk, UpdatePawnDraftCommand(borrower_id=loan.borrower_id,
        principal_amount=loan.principal_amount, monthly_interest_rate=economics.effective_monthly_rate,
        loan_date=preview["today"], tenure_months=loan.tenure_months,
        collateral=_inputs(preview["items"])), actor=actor)
    approval = approve_pawn_loan(loan.pk, actor=actor, valuation_review=marker)
    frozen = approval.payload["collateral_economics"]
    if (approval.payload["origination_rates"]["quotes"] != preview["resolved"].valuation_quotes
            or approval.payload["principal_amount"] != str(economics.gross_principal)
            or any(frozen[key] != str(getattr(economics, key)) for key in
                ("monthly_interest", "advance_interest", "deducted_fees", "net_disbursed"))):
        raise ValueError("Valuation changed during confirmation. Review again.")
    loan.refresh_from_db()
    return loan, True
