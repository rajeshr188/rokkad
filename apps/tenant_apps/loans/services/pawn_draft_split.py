import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from apps.tenant_apps.loans.domain import LoanDocumentKind, PawnLoanEventKind, PawnLoanState
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanProductVersion,
    LoanSeries,
    PawnLoan,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.number_allocation import preview_number
from apps.tenant_apps.loans.services.pawn_drafts import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    UpdatePawnDraftCommand,
    create_pawn_draft,
    update_pawn_draft,
)
from apps.tenant_apps.loans.services.pawn_economics import resolve_pawn_draft_economics


class PawnDraftSplitError(ValueError):
    pass


@dataclass(frozen=True)
class PawnDraftSplitPreview:
    source: PawnLoan
    selected_items: tuple
    remaining_items: tuple
    source_economics: object
    new_economics: object
    number_preview: str
    fingerprint: str


def _input(item, *, preserve_identity=True):
    return CollateralDraftInput(
        collateral_item_id=item.pk if preserve_identity else None,
        description=item.description,
        metal=item.metal,
        gross_weight=item.gross_weight,
        net_weight=item.net_weight,
        purity_percentage=item.purity_percentage,
        latest_appraised_value=item.latest_appraised_value,
        allocated_principal=item.allocated_principal,
    )


def preview_pawn_draft_split(
    source_loan_id,
    *,
    collateral_item_ids,
    series,
    product_version,
    loan_date,
    tenure_months,
):
    workspace_id = current_tenant_workspace_id()
    try:
        source = PawnLoan.objects.select_related("borrower", "series__license", "product_version").get(
            pk=source_loan_id, workspace_id=workspace_id
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnDraftSplitError("PawnLoan draft was not found.") from exc
    if source.state != PawnLoanState.DRAFT.value:
        raise PawnDraftSplitError("Only a draft PawnLoan can be split.")
    try:
        series = LoanSeries.objects.select_related("license").get(
            pk=series.pk,
            license__workspace_id=workspace_id,
        )
    except LoanSeries.DoesNotExist as exc:
        raise PawnDraftSplitError("The destination Series must belong to this workspace.") from exc
    try:
        product_version = LoanProductVersion.objects.select_related("product").get(
            pk=product_version.pk,
            product__workspace_id=workspace_id,
            product__is_active=True,
            status="ACTIVE",
        )
    except LoanProductVersion.DoesNotExist as exc:
        raise PawnDraftSplitError(
            "The destination product version must be active in this workspace."
        ) from exc
    all_items = tuple(source.collateral_items.prefetch_related("photos").order_by("pk"))
    selected_ids = frozenset(int(value) for value in collateral_item_ids)
    selected = tuple(item for item in all_items if item.pk in selected_ids)
    remaining = tuple(item for item in all_items if item.pk not in selected_ids)
    if len(selected) != len(selected_ids) or not selected:
        raise PawnDraftSplitError("Select collateral belonging to this draft.")
    if not remaining:
        raise PawnDraftSplitError("At least one collateral item must remain on the source draft.")
    source_economics = resolve_pawn_draft_economics(
        workspace_id=workspace_id,
        license_id=source.license_id,
        as_of_date=source.loan_date,
        collateral=tuple(_input(item) for item in remaining),
    )
    new_economics = resolve_pawn_draft_economics(
        workspace_id=workspace_id,
        license_id=series.license_id,
        as_of_date=loan_date,
        collateral=tuple(_input(item) for item in selected),
    )
    number = preview_number(series=series, document_kind=LoanDocumentKind.PAWN_LOAN)
    payload = {
        "source": source.pk,
        "source_updated": source.updated_at.isoformat(),
        "selected": [(item.pk, item.updated_at.isoformat(), str(item.allocated_principal)) for item in selected],
        "remaining": [(item.pk, item.updated_at.isoformat(), str(item.allocated_principal)) for item in remaining],
        "series": series.pk,
        "product": product_version.pk,
        "date": loan_date.isoformat(),
        "tenure": int(tenure_months),
        "source_policy": source_economics.economic_policy.pk,
        "new_policy": new_economics.economic_policy.pk,
    }
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PawnDraftSplitPreview(source, selected, remaining, source_economics, new_economics, number.value, fingerprint)


@transaction.atomic
def split_pawn_draft(
    source_loan_id,
    *,
    collateral_item_ids,
    series,
    product_version,
    loan_date,
    tenure_months,
    expected_fingerprint,
    actor=None,
):
    source = PawnLoan.objects.select_for_update().get(pk=source_loan_id, workspace_id=current_tenant_workspace_id())
    preview = preview_pawn_draft_split(
        source.pk,
        collateral_item_ids=collateral_item_ids,
        series=series,
        product_version=product_version,
        loan_date=loan_date,
        tenure_months=tenure_months,
    )
    if not expected_fingerprint or expected_fingerprint != preview.fingerprint:
        raise PawnDraftSplitError("Draft changed after preview; review the split again.")
    new_loan = create_pawn_draft(
        CreatePawnDraftCommand(
            workspace_id=source.workspace_id,
            borrower_id=source.borrower_id,
            license_id=series.license_id,
            series_id=series.pk,
            product_version_id=product_version.pk,
            principal_amount=preview.new_economics.economics.gross_principal,
            monthly_interest_rate=preview.new_economics.economics.effective_monthly_rate,
            loan_date=loan_date,
            tenure_months=tenure_months,
            collateral=tuple(
                _input(item, preserve_identity=False) for item in preview.selected_items
            ),
        ),
        actor=actor,
    )
    generated = tuple(new_loan.collateral_items.order_by("pk"))
    editable = ("allocated_principal", "monthly_interest_rate", "interest_rate_policy")
    for original, temporary in zip(preview.selected_items, generated, strict=True):
        for field in editable:
            setattr(original, field, getattr(temporary, field))
        temporary.delete()
        original.loan = new_loan
        original.save(update_fields=("loan", *editable, "updated_at"))
    update_pawn_draft(
        source.pk,
        UpdatePawnDraftCommand(
            borrower_id=source.borrower_id,
            principal_amount=preview.source_economics.economics.gross_principal,
            monthly_interest_rate=preview.source_economics.economics.effective_monthly_rate,
            loan_date=source.loan_date,
            tenure_months=source.tenure_months,
            collateral=tuple(_input(item) for item in preview.remaining_items),
        ),
        actor=actor,
    )
    metadata = {
        "source_loan_id": source.pk,
        "new_loan_id": new_loan.pk,
        "moved_collateral_item_ids": [item.pk for item in preview.selected_items],
    }
    LoanChangeLog.objects.create(
        loan=source, event_kind=PawnLoanEventKind.DRAFT_UPDATED.value,
        from_state="DRAFT", to_state="DRAFT", actor=actor,
        metadata={"draft_split_out": metadata},
    )
    LoanChangeLog.objects.create(
        loan=new_loan, event_kind=PawnLoanEventKind.DRAFT_UPDATED.value,
        from_state="DRAFT", to_state="DRAFT", actor=actor,
        metadata={"draft_split_in": metadata},
    )
    return new_loan
