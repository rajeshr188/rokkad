"""Pawn read helpers; existing services own business rules."""

from django.shortcuts import get_object_or_404

from apps.tenant_apps.loans.access import (
    LOANS_ADMIN_ACTION,
    LOANS_OWNER_ACTION,
)
from apps.tenant_apps.loans.models import PawnLoan


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items",
            "collateral_items__photos",
            "collateral_items__storage_movements__from_location",
            "collateral_items__storage_movements__to_location",
            "collateral_items__storage_movements__moved_by",
            "interest_accruals__lines__collateral_item",
            "change_log__actor",
            "loan_events",
            "loan_events__reversed_by_event",
            "loan_events__repayment_allocation_lines__collateral_item",
            "releases__items__collateral_item",
            "approval_snapshots",
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _can_administer(request):
    return request.loans_workspace_access.can(LOANS_ADMIN_ACTION)


def _can_manage_storage(request):
    return request.loans_workspace_access.can(LOANS_OWNER_ACTION)
