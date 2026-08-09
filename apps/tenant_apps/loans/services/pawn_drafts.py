from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.loans.domain import (
    CollateralMetal,
    PawnLoanEventKind,
    PawnLoanState,
)
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanLicense,
    LoanSeries,
    PawnCollateralItem,
    PawnLoan,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.license_series import assert_series_can_issue
from apps.tenant_apps.loans.services.number_allocation import (
    allocate_pawn_loan_number,
)
from apps.tenant_apps.loans.services.pawn_economics import (
    resolve_pawn_draft_economics,
)
from apps.tenant_apps.party.models import Party


class PawnDraftError(ValueError):
    """Raised when a PawnLoan draft command violates a workflow boundary."""


@dataclass(frozen=True)
class CollateralDraftInput:
    description: str
    metal: CollateralMetal | str
    gross_weight: Decimal
    net_weight: Decimal
    purity_percentage: Decimal
    latest_appraised_value: Decimal | None = None
    allocated_principal: Decimal | None = None
    collateral_item_id: int | None = None


@dataclass(frozen=True)
class CreatePawnDraftCommand:
    workspace_id: int
    borrower_id: int
    license_id: int
    series_id: int
    principal_amount: Decimal
    monthly_interest_rate: Decimal
    loan_date: date
    tenure_months: int
    collateral: tuple[CollateralDraftInput, ...]


@dataclass(frozen=True)
class UpdatePawnDraftCommand:
    borrower_id: int
    principal_amount: Decimal
    monthly_interest_rate: Decimal
    loan_date: date
    tenure_months: int
    collateral: tuple[CollateralDraftInput, ...]


@transaction.atomic
def create_pawn_draft(command: CreatePawnDraftCommand, *, actor=None) -> PawnLoan:
    workspace_id = _require_active_workspace(command.workspace_id)
    borrower = _active_party(command.borrower_id)
    license, series = _setup_for_workspace(
        workspace_id=workspace_id,
        license_id=command.license_id,
        series_id=command.series_id,
    )
    assert_series_can_issue(series)
    license_revision = license.revisions.order_by("-revision_number").first()

    resolved = _resolve_new_economics(
        workspace_id=workspace_id,
        license_id=license.pk,
        as_of_date=command.loan_date,
        collateral=command.collateral,
    )
    principal_amount, monthly_interest_rate = _aggregate_terms(command, resolved)
    loan = PawnLoan(
        workspace_id=workspace_id,
        license=license,
        license_revision=license_revision,
        series=series,
        borrower=borrower,
        loan_number="PENDING-ALLOCATION",
        state=PawnLoanState.DRAFT.value,
        principal_amount=principal_amount,
        monthly_interest_rate=monthly_interest_rate,
        loan_date=command.loan_date,
        tenure_months=command.tenure_months,
        created_by=actor,
        updated_by=actor,
    )
    loan.full_clean(exclude={"loan_number"})
    collateral = _validated_collateral(loan, command.collateral, resolved=resolved)

    allocation = allocate_pawn_loan_number(series=series, actor=actor)
    loan.loan_number = allocation.value
    loan.full_clean()
    loan.save()
    for item in collateral:
        item.loan = loan
    PawnCollateralItem.objects.bulk_create(collateral)
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.DRAFT_CREATED.value,
        to_state=PawnLoanState.DRAFT.value,
        actor=actor,
        metadata={
            "loan_number": loan.loan_number,
            "sequence_id": allocation.sequence_id,
            "collateral_count": len(collateral),
        },
    )
    return loan


@transaction.atomic
def update_pawn_draft(
    loan_id: int, command: UpdatePawnDraftCommand, *, actor=None
) -> PawnLoan:
    workspace_id = _require_active_workspace()
    try:
        loan = (
            PawnLoan.objects.select_for_update()
            .select_related("license", "series", "borrower")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnDraftError("PawnLoan draft was not found in the active workspace.") from exc
    if loan.state != PawnLoanState.DRAFT.value:
        raise PawnDraftError("Only a draft PawnLoan can be edited.")

    borrower = _active_party(command.borrower_id)
    resolved = _resolve_new_economics(
        workspace_id=workspace_id,
        license_id=loan.license_id,
        as_of_date=command.loan_date,
        collateral=command.collateral,
    )
    principal_amount, monthly_interest_rate = _aggregate_terms(command, resolved)
    candidate = PawnLoan(
        pk=loan.pk,
        workspace_id=workspace_id,
        license=loan.license,
        license_revision=loan.license_revision,
        series=loan.series,
        borrower=borrower,
        loan_number=loan.loan_number,
        state=loan.state,
        principal_amount=principal_amount,
        monthly_interest_rate=monthly_interest_rate,
        loan_date=command.loan_date,
        tenure_months=command.tenure_months,
        created_by=loan.created_by,
        updated_by=actor,
    )
    candidate._state.adding = False
    candidate.full_clean()
    collateral = _validated_collateral(candidate, command.collateral, resolved=resolved)
    before = _draft_snapshot(loan, tuple(loan.collateral_items.all()))

    loan.borrower = borrower
    loan.principal_amount = principal_amount
    loan.monthly_interest_rate = monthly_interest_rate
    loan.loan_date = command.loan_date
    loan.tenure_months = command.tenure_months
    loan.updated_by = actor
    loan.save(
        update_fields=[
            "borrower",
            "principal_amount",
            "monthly_interest_rate",
            "loan_date",
            "tenure_months",
            "updated_by",
            "updated_at",
        ]
    )
    existing = {
        item.pk: item
        for item in PawnCollateralItem.objects.select_for_update().filter(loan=loan)
    }
    supplied_ids = [item.pk for item in collateral if item.pk is not None]
    if len(supplied_ids) != len(set(supplied_ids)) or any(
        item_id not in existing for item_id in supplied_ids
    ):
        raise PawnDraftError("Collateral identity does not belong to this draft.")
    removed = [item for item_id, item in existing.items() if item_id not in supplied_ids]
    if any(item.photos.exists() for item in removed):
        raise PawnDraftError(
            "Collateral with photograph evidence cannot be removed; cancel this draft and start again."
        )
    for item in removed:
        item.delete()
    persisted = []
    editable_fields = (
        "description",
        "metal",
        "gross_weight",
        "net_weight",
        "purity_percentage",
        "latest_appraised_value",
        "allocated_principal",
        "monthly_interest_rate",
        "interest_rate_policy",
    )
    for candidate in collateral:
        if candidate.pk is None:
            candidate.loan = loan
            candidate.save()
            persisted.append(candidate)
            continue
        target = existing[candidate.pk]
        for field in editable_fields:
            setattr(target, field, getattr(candidate, field))
        target.full_clean()
        target.save(update_fields=(*editable_fields, "updated_at"))
        persisted.append(target)
    after = _draft_snapshot(loan, tuple(persisted))
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.DRAFT_UPDATED.value,
        from_state=PawnLoanState.DRAFT.value,
        to_state=PawnLoanState.DRAFT.value,
        actor=actor,
        metadata={"before": before, "after": after},
    )
    return loan


def _require_active_workspace(expected_workspace_id=None) -> int:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnDraftError("PawnLoan draft operations require an active tenant schema.")
    if expected_workspace_id is not None and workspace_id != expected_workspace_id:
        raise PawnDraftError("Draft workspace must match the active tenant.")
    return workspace_id


def _active_party(borrower_id: int) -> Party:
    try:
        return Party.objects.get(pk=borrower_id, status=Party.PartyStatus.ACTIVE)
    except Party.DoesNotExist as exc:
        raise PawnDraftError("Borrower must be an active Party in this workspace.") from exc


def _setup_for_workspace(*, workspace_id, license_id, series_id):
    try:
        license = LoanLicense.objects.get(pk=license_id, workspace_id=workspace_id)
    except LoanLicense.DoesNotExist as exc:
        raise PawnDraftError("License must belong to the active workspace.") from exc
    try:
        series = LoanSeries.objects.select_related("license").get(
            pk=series_id,
            license=license,
        )
    except LoanSeries.DoesNotExist as exc:
        raise PawnDraftError("Series must belong to the selected license.") from exc
    return license, series


def _validated_collateral(loan, inputs, *, resolved=None):
    if not inputs:
        raise PawnDraftError("At least one collateral item is required.")
    items = []
    errors = []
    for index, item in enumerate(inputs):
        try:
            tranche = resolved.economics.tranches[index] if resolved else None
            rate_policy = resolved.rate_policies[index] if resolved else None
            model = PawnCollateralItem(
                pk=item.collateral_item_id,
                loan=loan,
                description=item.description,
                metal=CollateralMetal(item.metal).value,
                gross_weight=item.gross_weight,
                net_weight=item.net_weight,
                purity_percentage=item.purity_percentage,
                latest_appraised_value=item.latest_appraised_value,
                allocated_principal=(
                    tranche.allocated_principal if tranche is not None else None
                ),
                monthly_interest_rate=(
                    tranche.monthly_interest_rate if tranche is not None else None
                ),
                interest_rate_policy=rate_policy,
            )
            if model.pk is not None:
                model._state.adding = False
            model.full_clean(exclude={"loan"})
            items.append(model)
        except (ValidationError, ValueError) as exc:
            errors.append(f"collateral[{index}]: {exc}")
    if errors:
        raise ValidationError(errors)
    return items


def _resolve_new_economics(*, workspace_id, license_id, as_of_date, collateral):
    allocations = [item.allocated_principal for item in collateral]
    if not any(value is not None for value in allocations):
        return None
    if any(value is None for value in allocations):
        raise PawnDraftError("Every collateral item requires an allocated principal.")
    return resolve_pawn_draft_economics(
        workspace_id=workspace_id,
        license_id=license_id,
        as_of_date=as_of_date,
        collateral=collateral,
    )


def _aggregate_terms(command, resolved):
    if resolved is None:
        return command.principal_amount, command.monthly_interest_rate
    return (
        resolved.economics.gross_principal,
        resolved.economics.effective_monthly_rate,
    )


def _draft_snapshot(loan, collateral):
    return {
        "borrower_id": loan.borrower_id,
        "license_id": loan.license_id,
        "license_revision_id": loan.license_revision_id,
        "principal_amount": str(loan.principal_amount),
        "monthly_interest_rate": str(loan.monthly_interest_rate),
        "loan_date": loan.loan_date.isoformat(),
        "tenure_months": loan.tenure_months,
        "collateral": [
            {
                "collateral_item_id": item.pk,
                "public_id": str(item.public_id),
                "description": item.description,
                "metal": item.metal,
                "gross_weight": str(item.gross_weight),
                "net_weight": str(item.net_weight),
                "purity_percentage": str(item.purity_percentage),
                "latest_appraised_value": (
                    str(item.latest_appraised_value)
                    if item.latest_appraised_value is not None
                    else None
                ),
                "allocated_principal": (
                    str(item.allocated_principal)
                    if item.allocated_principal is not None
                    else None
                ),
                "monthly_interest_rate": (
                    str(item.monthly_interest_rate)
                    if item.monthly_interest_rate is not None
                    else None
                ),
                "interest_rate_policy_id": item.interest_rate_policy_id,
            }
            for item in collateral
        ],
    }
