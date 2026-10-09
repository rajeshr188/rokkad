import hashlib
import json
from dataclasses import asdict, dataclass

from django.db import transaction
from apps.orgs.models import Company

from .action_access import require_loan_action
from apps.tenant_apps.loans.domain import LoanDocumentKind, PawnLoanEventKind, PawnLoanState
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanNumberSequence,
    LoanProductVersion,
    LoanSeries,
    PawnLoan,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.number_allocation import preview_numbers
from apps.tenant_apps.loans.services.license_series import assert_series_can_issue
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
class PawnDraftSplitRow:
    items: tuple
    economics: object
    number_preview: str


@dataclass(frozen=True)
class PawnDraftSplitPreview:
    source: PawnLoan
    selected_items: tuple
    remaining_items: tuple
    source_economics: object
    new_economics: object
    number_preview: str
    fingerprint: str
    new_drafts: tuple
    original_economics: object
    totals: dict
    split_each: bool


def _input(item, *, preserve_identity=True):
    return CollateralDraftInput(
        collateral_item_id=item.pk if preserve_identity else None,
        description=item.description,
        quantity=item.quantity,
        interest_rate_override=item.interest_rate_override,
        interest_override_reason=item.interest_override_reason,
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
    split_each=False,
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
    if split_each and len(remaining) != 1:
        raise PawnDraftSplitError("Choose exactly one collateral entry to keep on the source draft.")
    source_economics = resolve_pawn_draft_economics(
        workspace_id=workspace_id,
        license_id=source.license_id,
        series_id=source.series_id,
        as_of_date=source.loan_date,
        collateral=tuple(_input(item) for item in remaining),
    )
    groups = tuple((item,) for item in selected) if split_each else (selected,)
    numbers = preview_numbers(series=series, document_kind=LoanDocumentKind.PAWN_LOAN, count=len(groups))
    new_drafts = tuple(PawnDraftSplitRow(
        items=group,
        economics=resolve_pawn_draft_economics(
            workspace_id=workspace_id, license_id=series.license_id,
            series_id=series.pk, as_of_date=loan_date,
            collateral=tuple(_input(item) for item in group),
        ),
        number_preview=number.value,
    ) for group, number in zip(groups, numbers, strict=True))
    original_economics = resolve_pawn_draft_economics(
        workspace_id=workspace_id, license_id=source.license_id,
        series_id=source.series_id, as_of_date=source.loan_date,
        collateral=tuple(_input(item) for item in all_items),
    )
    totals = {
        field: sum((getattr(row.economics.economics, field) for row in new_drafts),
                   getattr(source_economics.economics, field))
        for field in ("gross_principal", "monthly_interest", "advance_interest", "deducted_fees", "net_disbursed")
    }
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
    }
    payload.update({
        "split_each": bool(split_each),
        "items": [asdict(_input(item)) for item in all_items],
        "photos": [[(photo.pk, photo.sha256, photo.file.name) for photo in item.photos.all()] for item in all_items],
        "source_economics": asdict(source_economics.economics),
        "new_drafts": [{"number": row.number_preview, "economics": asdict(row.economics.economics),
                        "policy": row.economics.economic_policy.pk} for row in new_drafts],
    })
    fingerprint = _fingerprint(payload)
    return PawnDraftSplitPreview(source, selected, remaining, source_economics,
        new_drafts[0].economics, new_drafts[0].number_preview, fingerprint,
        new_drafts, original_economics, totals, bool(split_each))


def _fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


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
    split_each=False,
):
    workspace_id = current_tenant_workspace_id()
    # Match owner availability/combined-entry lock order before writing audit FKs.
    Company.objects.select_for_update(no_key=True).get(pk=workspace_id)
    try:
        source = PawnLoan.objects.select_for_update().get(pk=source_loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise PawnDraftSplitError("PawnLoan draft was not found.") from exc
    require_loan_action(source, actor, "data.edit", "data.create")
    collateral_item_ids = tuple(collateral_item_ids)
    request = _fingerprint({"items": sorted(int(pk) for pk in collateral_item_ids),
        "series": series.pk, "product": product_version.pk, "date": loan_date,
        "tenure": int(tenure_months), "split_each": bool(split_each)})
    if expected_fingerprint:
        completed = source.change_log.filter(
            metadata__draft_split_out__fingerprint=expected_fingerprint,
        ).first()
        if completed:
            details = completed.metadata["draft_split_out"]
            if details["request"] != request:
                raise PawnDraftSplitError("The confirmed split does not match this request.")
            loans = {loan.pk: loan for loan in PawnLoan.objects.filter(
                pk__in=details["new_loan_ids"], workspace_id=workspace_id)}
            result = tuple(loans[pk] for pk in details["new_loan_ids"])
            return result if split_each else result[0]
    # Hold the destination sequence through preview and all allocations.
    if series.workspace_id != workspace_id:
        raise PawnDraftSplitError("The destination Series must belong to this workspace.")
    assert_series_can_issue(series, for_update=True)
    list(LoanNumberSequence.objects.select_for_update().filter(
        series=series, document_kind=LoanDocumentKind.PAWN_LOAN.value))
    list(source.collateral_items.select_for_update().order_by("pk"))
    preview = preview_pawn_draft_split(
        source.pk,
        collateral_item_ids=collateral_item_ids,
        series=series,
        product_version=product_version,
        loan_date=loan_date,
        tenure_months=tenure_months,
        split_each=split_each,
    )
    if not expected_fingerprint or expected_fingerprint != preview.fingerprint:
        raise PawnDraftSplitError("Draft changed after preview; review the split again.")
    new_loans = tuple(_create_split_draft(source, row, series=series,
        product_version=product_version, loan_date=loan_date,
        tenure_months=tenure_months, actor=actor) for row in preview.new_drafts)
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
        "new_loan_id": new_loans[0].pk,
        "new_loan_ids": [loan.pk for loan in new_loans],
        "moved_collateral_item_ids": [item.pk for item in preview.selected_items],
        "original_collateral_item_ids": [item.pk for item in (*preview.selected_items, *preview.remaining_items)],
        "fingerprint": expected_fingerprint, "request": request, "split_each": bool(split_each),
        "series_id": series.pk, "product_version_id": product_version.pk,
    }
    LoanChangeLog.objects.create(
        loan=source, event_kind=PawnLoanEventKind.DRAFT_UPDATED.value,
        from_state="DRAFT", to_state="DRAFT", actor=actor,
        metadata={"draft_split_out": metadata},
    )
    for loan, row in zip(new_loans, preview.new_drafts, strict=True):
        LoanChangeLog.objects.create(
            loan=loan, event_kind=PawnLoanEventKind.DRAFT_UPDATED.value,
            from_state="DRAFT", to_state="DRAFT", actor=actor,
            metadata={"draft_split_in": {**metadata,
                "new_loan_id": loan.pk, "moved_collateral_item_ids": [item.pk for item in row.items]}},
        )
    return new_loans if split_each else new_loans[0]


def _create_split_draft(source, row, *, series, product_version, loan_date, tenure_months, actor):
    new_loan = create_pawn_draft(
        CreatePawnDraftCommand(
            workspace_id=source.workspace_id,
            borrower_id=source.borrower_id,
            license_id=series.license_id,
            series_id=series.pk,
            product_version_id=product_version.pk,
            principal_amount=row.economics.economics.gross_principal,
            monthly_interest_rate=row.economics.economics.effective_monthly_rate,
            loan_date=loan_date,
            tenure_months=tenure_months,
            collateral=tuple(
                _input(item, preserve_identity=False) for item in row.items
            ),
        ),
        actor=actor,
    )
    generated = tuple(new_loan.collateral_items.order_by("pk"))
    editable = ("allocated_principal", "monthly_interest_rate", "interest_rate_policy")
    for original, temporary in zip(row.items, generated, strict=True):
        for field in editable:
            setattr(original, field, getattr(temporary, field))
        temporary.delete()
        original.loan = new_loan
        original.save(update_fields=("loan", *editable, "updated_at"))
    return new_loan
