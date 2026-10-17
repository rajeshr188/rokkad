"""Replace an unposted preparation identity; never move a posted agreement."""

from dataclasses import asdict
from datetime import date
import hashlib
import json
from uuid import UUID

from django.core import signing
from django.db import transaction

from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from .action_access import require_loan_action
from .pawn_draft_split import _create_split_draft, PawnDraftSplitRow
from .license_series import assert_series_can_issue
from .pawn_drafts import (
    CollateralDraftInput,
    _active_product_version,
    _require_interest_override_access,
    _draft_snapshot,
)
from .pawn_economics import resolve_pawn_draft_economics
from .pawn_lifecycle import cancel_pawn_loan

SALT = "loans.unposted-draft-replacement.v1"


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, default=str).encode()
    ).hexdigest()


def _source(loan_id, actor, *, lock=False):
    query = m.PawnLoan.objects.filter(workspace_id=m.current_tenant_workspace_id())
    if lock:
        query = query.select_for_update()
    try:
        loan = query.get(pk=loan_id)
    except m.PawnLoan.DoesNotExist:
        raise ValueError("Draft not found in this Workspace.") from None
    require_loan_action(loan, actor, "data.edit", "data.create")
    return loan


def _facts(values):
    expected = {
        "series_id",
        "product_version_id",
        "loan_date",
        "tenure_months",
        "reason",
        "request_key",
    }
    if not isinstance(values, dict) or set(values) != expected:
        raise ValueError(
            "Choose the replacement series/product, date, tenure and reason."
        )
    if (
        any(
            type(values[key]) is not int or values[key] <= 0
            for key in ("series_id", "product_version_id", "tenure_months")
        )
        or type(values["loan_date"]) is not date
    ):
        raise ValueError("Choose valid replacement details.")
    reason = str(values["reason"]).strip()
    if not reason or len(reason) > 500:
        raise ValueError(
            "Explain why this draft needs a different register or product."
        )
    return dict(
        values, reason=reason, request_key=str(UUID(str(values["request_key"])))
    )


def _proposal(loan, actor, facts):
    if loan.state != "DRAFT" or loan.loan_events.exists():
        raise ValueError(
            "Only an unposted preparation draft can be replaced. Review any financial history separately."
        )
    if (
        m.PawnLoanRenewal.objects.filter(source_loan=loan).exists()
        or m.PawnLoanRenewal.objects.filter(successor_loan=loan).exists()
        or m.FundingLoanDraftCollateral.objects.filter(
            collateral_item__loan=loan
        ).exists()
        or m.FundingPledgeItem.objects.filter(collateral_item__loan=loan).exists()
        or loan.collateral_items.exclude(custody_state="IN_VAULT").exists()
        or m.PawnCollateralStorageMovement.objects.filter(
            collateral_item__loan=loan
        ).exists()
        or m.PawnCollateralCustodyEvent.objects.filter(
            collateral_item__loan=loan
        ).exists()
    ):
        raise ValueError(
            "Connected collateral, funding or custody records need their own reconciliation; this draft cannot be replaced independently."
        )
    if (
        facts["series_id"] == loan.series_id
        and facts["product_version_id"] == loan.product_version_id
    ):
        raise ValueError(
            "The register and product are unchanged. Correct this draft normally."
        )
    try:
        series = m.LoanSeries.objects.select_related("license").get(
            pk=facts["series_id"], workspace_id=loan.workspace_id
        )
    except m.LoanSeries.DoesNotExist:
        raise ValueError("Choose a replacement series in this Workspace.") from None
    assert_series_can_issue(series)
    product = _active_product_version(
        loan.workspace_id,
        facts["product_version_id"],
        facts["loan_date"],
        facts["tenure_months"],
    )
    items = tuple(loan.collateral_items.prefetch_related("photos").order_by("pk"))
    inputs = tuple(
        CollateralDraftInput(
            description=item.description,
            metal=item.metal,
            quantity=item.quantity,
            gross_weight=item.gross_weight,
            net_weight=item.net_weight,
            purity_percentage=item.purity_percentage,
            latest_appraised_value=item.latest_appraised_value,
            allocated_principal=item.allocated_principal,
            interest_rate_override=item.interest_rate_override,
            interest_override_reason=item.interest_override_reason,
        )
        for item in items
    )
    _require_interest_override_access(loan.workspace, actor, inputs)
    resolved = resolve_pawn_draft_economics(
        workspace_id=loan.workspace_id,
        license_id=series.license_id,
        series_id=series.pk,
        as_of_date=facts["loan_date"],
        collateral=inputs,
    )
    state = _digest(
        dict(
            source=list(m.PawnLoan.objects.filter(pk=loan.pk).values()),
            items=list(loan.collateral_items.order_by("pk").values()),
            photos=[list(item.photos.order_by("pk").values()) for item in items],
            target_series=list(m.LoanSeries.objects.filter(pk=series.pk).values()),
            target_product=list(
                m.LoanProductVersion.objects.filter(pk=product.pk).values()
            ),
            target_license=list(
                m.LoanLicense.objects.filter(pk=series.license_id).values()
            ),
            target_license_evidence=list(
                m.LoanLicenseRevision.objects.filter(license_id=series.license_id)
                .order_by("pk")
                .values()
            ),
            economics=asdict(resolved.economics),
            economic_policy=resolved.economic_policy.pk,
            rates=[row.pk for row in resolved.rate_policies],
            fees=[row.pk for row in resolved.fee_policies],
            numbering="AT_APPROVAL",
        )
    )
    return dict(
        source=loan,
        series=series,
        product=product,
        items=items,
        economics=resolved.economics,
        resolved=resolved,
        number="Assigned at approval",
        state=state,
        photo_count=sum(item.photos.count() for item in items),
    )


def preview_draft_replacement(loan_id, *, actor, values):
    loan = _source(loan_id, actor)
    facts = _facts(values)
    preview = _proposal(loan, actor, facts)
    token = signing.dumps(
        dict(
            workspace=loan.workspace_id,
            actor=actor.pk,
            loan=loan.pk,
            request=_digest(facts),
            state=preview["state"],
        ),
        salt=SALT,
        compress=True,
    )
    return preview, token


@transaction.atomic
def replace_draft(loan_id, *, actor, values, token, confirmed=False):
    facts = _facts(values)
    if confirmed is not True:
        raise ValueError("Confirm the new draft and cancellation of the original.")
    Company.all_objects.select_for_update(no_key=True).get(
        pk=m.current_tenant_workspace_id()
    )
    loan = _source(loan_id, actor, lock=True)
    try:
        signed = signing.loads(token or "", salt=SALT)
        if not isinstance(signed, dict) or (
            signed.get("workspace"),
            signed.get("actor"),
            signed.get("loan"),
            signed.get("request"),
        ) != (loan.workspace_id, actor.pk, loan.pk, _digest(facts)):
            raise ValueError(
                "The replacement review does not match this draft, user or request."
            )
    except (signing.BadSignature, TypeError) as exc:
        raise ValueError("Review invalid. Preview the replacement again.") from exc
    completed = loan.change_log.filter(
        metadata__draft_replacement_out__request_key=facts["request_key"]
    ).first()
    if completed:
        result = completed.metadata["draft_replacement_out"]
        if result["request"] != signed["request"]:
            raise ValueError(
                "This replacement reference was used with different details."
            )
        return (
            m.PawnLoan.objects.get(
                pk=result["source"]["new_loan_id"], workspace_id=loan.workspace_id
            ),
            False,
        )
    try:
        signing.loads(token, salt=SALT, max_age=1800)
    except signing.BadSignature as exc:
        raise ValueError("Review expired. Preview the replacement again.") from exc
    # Protect the reviewed setup and items; no number is allocated here.
    series = m.LoanSeries.objects.filter(
        pk=facts["series_id"], workspace_id=loan.workspace_id
    ).first()
    if series is None:
        raise ValueError("Choose a replacement series in this Workspace.")
    assert_series_can_issue(series, for_update=True)
    list(loan.collateral_items.select_for_update().order_by("pk"))
    preview = _proposal(loan, actor, facts)
    if signed["state"] != preview["state"]:
        raise ValueError(
            "Draft, photographs or setup changed. Preview the replacement again."
        )
    # Ordinary draft movement preserves item/photo IDs and capture facts;
    # no bytes are recopied and no physical handover is invented.
    photo_sources = [
        dict(
            photo_id=photo.pk,
            captured_at=photo.captured_at.isoformat(),
            sha256=photo.sha256,
        )
        for item in preview["items"]
        for photo in item.photos.all()
    ]
    replacement = _create_split_draft(
        loan,
        PawnDraftSplitRow(
            items=preview["items"],
            economics=preview["resolved"],
            number_preview=preview["number"],
        ),
        series=preview["series"],
        product_version=preview["product"],
        loan_date=facts["loan_date"],
        tenure_months=facts["tenure_months"],
        actor=actor,
    )
    # Preparation links are source-local history, not financial graph edges.
    # Portable imports retain the opaque source without inventing local links.
    metadata = dict(
        request_key=facts["request_key"],
        request=signed["request"],
        source=dict(
            workspace_id=loan.workspace_id,
            new_loan_id=replacement.pk,
            old_loan_id=loan.pk,
            old_number=loan.loan_number,
            new_number=replacement.loan_number,
            photo_sources=photo_sources,
        ),
    )
    for subject, key in (
        (loan, "draft_replacement_out"),
        (replacement, "draft_replacement_in"),
    ):
        details = {key: metadata}
        if subject.pk == replacement.pk:
            details["draft"] = _draft_snapshot(
                replacement, replacement.collateral_items.order_by("pk")
            )
        m.LoanChangeLog.objects.create(
            loan=subject,
            event_kind="DRAFT_UPDATED",
            from_state="DRAFT",
            to_state="DRAFT",
            actor=actor,
            reason=facts["reason"],
            metadata=details,
        )
    cancel_pawn_loan(
        loan.pk,
        reason=f"Replaced by {replacement.display_reference}: {facts['reason']}"[:500],
        actor=actor,
    )
    return replacement, True
