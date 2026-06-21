"""
Views for Custody Tracking and Repledge Management.

Handles:
- Checking custody status before release
- Returning items from lenders (automatic and manual)
- Creating multi-item repledges
- Viewing custody history
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.girvi.models import GivenLoan, TakenLoan, LoanItem
from apps.tenant_apps.girvi.models.custody_tracking import (
    ItemCustodyStatus,
    RepledgeHistory,
)
from apps.tenant_apps.girvi.service_modules.custody import (
    build_loan_custody_summary,
    build_release_custody_check,
    build_repledge_selection_context,
    build_taken_loan_collateral_context,
    create_repledge_from_items,
    release_loan_with_custody_return,
    return_all_items_from_taken_loan,
)


# ============================================================================
# Custody Status Views
# ============================================================================


@login_required
def item_custody_status(request, item_id):
    """
    Show custody status and history for a single item.

    GET /girvi/items/<id>/custody/
    """
    item = get_object_or_404(LoanItem, pk=item_id)

    context = {
        "item": item,
        "custody_status": item.get_custody_status_display(),
        "is_repledged": item.is_repledged,
        "repledged_to": item.repledged_to,
        "history": item.repledge_history.all(),
        "can_release": item.is_available_for_release,
        "can_repledge": item.is_available_for_repledge,
        "can_return": item.can_be_returned_from_lender,
    }

    return render(request, "girvi/item_custody_status.html", context)


@login_required
def loan_custody_summary(request, loan_id):
    """
    Show custody summary for all items in a GivenLoan.

    GET /girvi/loans/<id>/custody/
    """
    loan = get_object_or_404(GivenLoan, pk=loan_id)
    context = build_loan_custody_summary(loan)

    template_name = "girvi/loan_custody_summary.html"
    if getattr(request, "htmx", False):
        template_name += "#custody-summary-content"

    return render(request, template_name, context)


# ============================================================================
# Return from Lender Workflow
# ============================================================================


@login_required
@require_http_methods(["POST"])
def return_item_from_lender(request, item_id):
    """
    Return a single item from lender to vault.

    POST /girvi/items/<id>/return-from-lender/
    """
    item = get_object_or_404(LoanItem, pk=item_id)
    notes = request.POST.get("notes", "")

    try:
        item.return_from_lender(user=request.user, notes=notes)
        messages.success(request, f"Item {item.itemdesc} returned from lender to vault")
    except ValidationError as e:
        messages.error(request, str(e))

    # Redirect back to loan or item detail
    if "next" in request.POST:
        return redirect(request.POST["next"])
    return redirect("girvi:girvi_loanitem_detail", pk=item_id)


@login_required
@require_http_methods(["POST"])
def return_all_items_from_lender(request, loan_id, taken_loan_id):
    """
    Return all items from a specific TakenLoan to vault.

    POST /girvi/loans/<loan_id>/return-from/<taken_loan_id>/
    """
    loan = get_object_or_404(GivenLoan, pk=loan_id)
    taken_loan = get_object_or_404(TakenLoan, pk=taken_loan_id)

    result = return_all_items_from_taken_loan(
        loan=loan,
        taken_loan=taken_loan,
        user=request.user,
    )

    if result.returned_count:
        messages.success(
            request,
            f"Returned {result.returned_count} item(s) from {taken_loan.lender.name}",
        )

    if result.errors:
        messages.warning(
            request, "Some items could not be returned: " + "; ".join(result.errors)
        )

    return redirect("girvi:loan_custody_summary", loan_id=loan_id)


# ============================================================================
# Enhanced Release with Auto-Return
# ============================================================================


@login_required
def release_loan_check_custody(request, loan_id):
    """
    Pre-release check: Show custody status and confirm auto-return if needed.

    GET /girvi/loans/<id>/release/check/
    """
    loan = get_object_or_404(GivenLoan, pk=loan_id)

    if loan.is_released:
        messages.info(request, "Loan already released")
        return redirect("girvi:girvi_loan_detail", pk=loan_id)

    context = build_release_custody_check(loan)
    if context["needs_return"]:
        return render(request, "girvi/release_custody_check.html", context)

    # All items in vault - proceed to normal release
    return redirect("girvi:girvi_release_create", pk=loan_id)


@login_required
@require_http_methods(["POST"])
def release_loan_with_return(request, loan_id):
    """
    Release loan with automatic return from lenders if needed.

    POST /girvi/loans/<id>/release/with-return/

    Workflow:
    1. Return all items from lenders
    2. Release to customer
    3. Create Release document
    """
    loan = get_object_or_404(GivenLoan, pk=loan_id)

    if loan.is_released:
        messages.error(request, "Loan already released")
        return redirect("girvi:girvi_loan_detail", pk=loan_id)

    release_date = request.POST.get("release_date")
    released_by = request.POST.get("released_by")

    try:
        release = release_loan_with_custody_return(
            loan=loan,
            release_date=release_date,
            released_by=released_by,
            user=request.user,
        )

        messages.success(
            request,
            f"Loan {loan.loan_id} released successfully. "
            f"All items returned from lenders and released to customer.",
        )
        return redirect("girvi:girvi_release_detail", pk=release.id)

    except ValidationError as e:
        messages.error(request, f"Release failed: {e}")
        return redirect("girvi:girvi_loan_detail", pk=loan_id)


# ============================================================================
# Repledge Creation (Multi-Item Collateral)
# ============================================================================


@login_required
def create_repledge_select_items(request):
    """
    Step 1: Select items from multiple GivenLoans to use as collateral.

    GET /girvi/repledge/create/
    """
    return render(
        request,
        "girvi/repledge_select_items.html",
        build_repledge_selection_context(),
    )


@login_required
@require_http_methods(["POST"])
def create_repledge_with_items(request):
    """
    Step 2: Create TakenLoan and repledge selected items.

    POST /girvi/repledge/create/

    Form data:
    - item_ids: List of LoanItem IDs to use as collateral
    - lender_id: Customer ID of lender
    - loan_amount: Amount to borrow
    - interest_rate: Interest rate
    - loan_date: Date of loan
    - notes: Optional notes
    """
    item_ids = request.POST.getlist("item_ids")
    lender_id = request.POST.get("lender_id")
    loan_amount = request.POST.get("loan_amount", 0)
    series_id = request.POST.get("series_id") or request.POST.get("series")

    try:
        taken_loan = create_repledge_from_items(
            item_ids=item_ids,
            lender_id=lender_id,
            loan_amount=loan_amount,
            loan_date=request.POST.get("loan_date"),
            notes=request.POST.get("notes", ""),
            user=request.user,
            series_id=series_id,
        )

        messages.success(
            request,
            f"TakenLoan {taken_loan.loan_id} created with {len(item_ids)} collateral item(s)",
        )
        return redirect("girvi:taken_loan_collateral_detail", loan_id=taken_loan.id)

    except (ValidationError, ValueError) as e:
        messages.error(request, f"Repledge failed: {e}")
        return redirect("girvi:create_repledge_select_items")


# ============================================================================
# Collateral Management Views
# ============================================================================


@login_required
def taken_loan_collateral_detail(request, loan_id):
    """
    Show all collateral items for a TakenLoan.

    GET /girvi/taken-loans/<id>/collateral/
    """
    loan = get_object_or_404(TakenLoan, pk=loan_id)
    context = build_taken_loan_collateral_context(loan)
    context["can_return_all"] = context["collateral_items"].exists()

    template_name = "girvi/taken_loan_collateral.html"
    if getattr(request, "htmx", False):
        template_name += "#taken-loan-collateral-content"

    return render(request, template_name, context)


@login_required
@require_http_methods(["POST"])
def return_taken_loan_collateral(request, loan_id):
    """
    Return all collateral from TakenLoan when closing it.

    POST /girvi/taken-loans/<id>/return-collateral/
    """
    loan = get_object_or_404(TakenLoan, pk=loan_id)

    try:
        with transaction.atomic():
            if hasattr(loan, "return_all_collateral"):
                loan.return_all_collateral(
                    user=request.user, notes=request.POST.get("notes", "")
                )
            else:
                # Manual return
                for item in loan.collateral_items.all():
                    item.return_from_lender(
                        user=request.user, notes=request.POST.get("notes", "")
                    )

        messages.success(
            request, f"All collateral returned from TakenLoan {loan.loan_id}"
        )
        return redirect("girvi:taken_loan_collateral_detail", loan_id=loan_id)

    except ValidationError as e:
        messages.error(request, f"Return failed: {e}")
        return redirect("girvi:taken_loan_collateral_detail", loan_id=loan_id)


# ============================================================================
# History and Reporting
# ============================================================================


@login_required
def repledge_history_report(request):
    """
    Report showing all repledge history with filters.

    GET /girvi/reports/repledge-history/
    """
    history = RepledgeHistory.objects.select_related(
        "loan_item",
        "loan_item__loan",
        "loan_item__loan__borrower",
        "taken_loan",
        "taken_loan__lender",
        "repledged_by",
        "returned_by",
    )

    # Filters
    status = request.GET.get("status")
    if status == "active":
        history = history.filter(returned_at__isnull=True)
    elif status == "returned":
        history = history.filter(returned_at__isnull=False)

    customer_id = request.GET.get("customer")
    if customer_id:
        history = history.filter(loan_item__loan__borrower_id=customer_id)

    lender_id = request.GET.get("lender")
    if lender_id:
        history = history.filter(taken_loan__lender_id=lender_id)

    context = {
        "history": history[:100],  # Limit for performance
        "total_active": RepledgeHistory.objects.filter(
            returned_at__isnull=True
        ).count(),
        "total_returned": RepledgeHistory.objects.filter(
            returned_at__isnull=False
        ).count(),
    }

    return render(request, "girvi/repledge_history_report.html", context)


# ============================================================================
# AJAX/API Endpoints
# ============================================================================


@login_required
def api_check_release_custody(request, loan_id):
    """
    API endpoint to check custody status before release.

    GET /girvi/api/loans/<id>/check-custody/

    Returns JSON:
    {
        "can_release": bool,
        "needs_return": bool,
        "items_with_lender": int,
        "lenders": ["Lender A", "Lender B"],
        "message": str
    }
    """
    loan = get_object_or_404(GivenLoan, pk=loan_id)

    items_with_lender = loan.loanitems.filter(
        custody_status=ItemCustodyStatus.WITH_LENDER
    )

    lenders = set(
        item.repledged_to.lender.name for item in items_with_lender if item.repledged_to
    )

    can_release = not items_with_lender.exists()

    return JsonResponse(
        {
            "can_release": can_release,
            "needs_return": items_with_lender.exists(),
            "items_with_lender": items_with_lender.count(),
            "lenders": list(lenders),
            "message": (
                "All items in vault - can release"
                if can_release
                else f"{items_with_lender.count()} item(s) with lender(s) - return required"
            ),
        }
    )


@login_required
def api_item_custody_status(request, item_id):
    """
    API endpoint for item custody status.

    GET /girvi/api/items/<id>/custody/
    """
    item = get_object_or_404(LoanItem, pk=item_id)

    return JsonResponse(
        {
            "item_id": item.id,
            "custody_status": item.custody_status,
            "custody_display": item.get_custody_status_display(),
            "is_repledged": item.is_repledged,
            "repledged_to": {
                "id": item.repledged_to.id,
                "loan_id": item.repledged_to.loan_id,
                "lender": item.repledged_to.lender.name,
            }
            if item.repledged_to
            else None,
            "can_release": item.is_available_for_release,
            "can_repledge": item.is_available_for_repledge,
            "can_return": item.can_be_returned_from_lender,
        }
    )
