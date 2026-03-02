"""
Views for Custody Tracking and Repledge Management.

Handles:
- Checking custody status before release
- Returning items from lenders (automatic and manual)
- Creating multi-item repledges
- Viewing custody history
"""

from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.girvi.models.loan import GivenLoan, TakenLoan, LoanItem
from apps.tenant_apps.girvi.models.custody_tracking import (
    ItemCustodyStatus,
    RepledgeHistory,
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

    items_by_custody = {"in_vault": [], "with_lender": [], "with_customer": []}

    for item in loan.loanitems.all():
        status = item.custody_status
        items_by_custody[status].append(item)

    # Group items with lenders by lender
    by_lender = {}
    for item in items_by_custody["with_lender"]:
        if item.repledged_to:
            lender_name = item.repledged_to.lender.name
            if lender_name not in by_lender:
                by_lender[lender_name] = []
            by_lender[lender_name].append(item)

    can_release, release_message = (
        loan.can_release() if hasattr(loan, "can_release") else (True, "")
    )

    context = {
        "loan": loan,
        "items_by_custody": items_by_custody,
        "items_by_lender": by_lender,
        "can_release": can_release,
        "release_message": release_message,
        "total_items": loan.loanitems.count(),
    }

    return render(request, "girvi/loan_custody_summary.html", context)


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
    return redirect("girvi:loanitem_detail", pk=item_id)


@login_required
@require_http_methods(["POST"])
def return_all_items_from_lender(request, loan_id, taken_loan_id):
    """
    Return all items from a specific TakenLoan to vault.

    POST /girvi/loans/<loan_id>/return-from/<taken_loan_id>/
    """
    loan = get_object_or_404(GivenLoan, pk=loan_id)
    taken_loan = get_object_or_404(TakenLoan, pk=taken_loan_id)

    items = loan.loanitems.filter(
        repledged_to=taken_loan, custody_status=ItemCustodyStatus.WITH_LENDER
    )

    returned_count = 0
    errors = []

    with transaction.atomic():
        for item in items:
            try:
                item.return_from_lender(
                    user=request.user,
                    notes=f"Bulk return from {taken_loan.lender.name}",
                )
                returned_count += 1
            except ValidationError as e:
                errors.append(f"{item.itemdesc}: {e}")

    if returned_count:
        messages.success(
            request, f"Returned {returned_count} item(s) from {taken_loan.lender.name}"
        )

    if errors:
        messages.warning(
            request, "Some items could not be returned: " + "; ".join(errors)
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
        return redirect("girvi:loan_detail", pk=loan_id)

    items_by_custody = {
        status: list(loan.loanitems.filter(custody_status=status))
        for status in [
            ItemCustodyStatus.IN_VAULT,
            ItemCustodyStatus.WITH_LENDER,
            ItemCustodyStatus.WITH_CUSTOMER,
        ]
    }

    with_lender = items_by_custody[ItemCustodyStatus.WITH_LENDER]

    if with_lender:
        # Group by lender for display
        by_lender = {}
        for item in with_lender:
            if item.repledged_to:
                lender_name = item.repledged_to.lender.name
                if lender_name not in by_lender:
                    by_lender[lender_name] = []
                by_lender[lender_name].append(item)

        context = {
            "loan": loan,
            "items_by_custody": items_by_custody,
            "items_by_lender": by_lender,
            "needs_return": True,
            "total_with_lenders": len(with_lender),
        }

        return render(request, "girvi/release_custody_check.html", context)

    # All items in vault - proceed to normal release
    return redirect("girvi:loan_release_create", loan_id=loan_id)


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
        return redirect("girvi:loan_detail", pk=loan_id)

    release_date = request.POST.get("release_date")
    released_by = request.POST.get("released_by")

    try:
        with transaction.atomic():
            # Use the enhanced release method if available
            if hasattr(loan, "release_with_return_workflow"):
                release = loan.release_with_return_workflow(
                    release_date=release_date,
                    released_by=released_by,
                    created_by=request.user,
                )
            else:
                # Manual workflow
                # Step 1: Return items from lenders
                items_with_lender = loan.loanitems.filter(
                    custody_status=ItemCustodyStatus.WITH_LENDER
                )
                for item in items_with_lender:
                    item.return_from_lender(
                        user=request.user,
                        notes=f"Returned for loan {loan.loan_id} release",
                    )

                # Step 2: Release items to customer
                items_in_vault = loan.loanitems.filter(
                    custody_status=ItemCustodyStatus.IN_VAULT
                )
                for item in items_in_vault:
                    item.release_to_customer(user=request.user)

                # Step 3: Create release document
                release = loan.create_release(
                    release_date=release_date,
                    released_by=released_by,
                    created_by=request.user,
                )

        messages.success(
            request,
            f"Loan {loan.loan_id} released successfully. "
            f"All items returned from lenders and released to customer.",
        )
        return redirect("girvi:release_detail", pk=release.id)

    except ValidationError as e:
        messages.error(request, f"Release failed: {e}")
        return redirect("girvi:loan_detail", pk=loan_id)


# ============================================================================
# Repledge Creation (Multi-Item Collateral)
# ============================================================================


@login_required
def create_repledge_select_items(request):
    """
    Step 1: Select items from multiple GivenLoans to use as collateral.

    GET /girvi/repledge/create/
    """
    # Get all items available for repledge
    available_items = LoanItem.objects.filter(
        custody_status=ItemCustodyStatus.IN_VAULT,
        repledged_to__isnull=True,
        loan__release__isnull=True,
    ).select_related("loan", "loan__borrower")

    # Group by customer for easier selection
    by_customer = {}
    for item in available_items:
        customer = item.loan.borrower
        if customer not in by_customer:
            by_customer[customer] = []
        by_customer[customer].append(item)

    context = {
        "available_items": available_items,
        "items_by_customer": by_customer,
        "total_value": sum(item.current_value() for item in available_items),
    }

    return render(request, "girvi/repledge_select_items.html", context)


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
    loan_amount = Decimal(request.POST.get("loan_amount", 0))

    if not item_ids:
        messages.error(request, "No items selected")
        return redirect("girvi:create_repledge_select_items")

    try:
        with transaction.atomic():
            # Get items
            items = LoanItem.objects.filter(id__in=item_ids)

            # Validate all items
            for item in items:
                if not item.is_available_for_repledge:
                    raise ValidationError(
                        f"Item {item.itemdesc} is not available for repledge"
                    )

            # Create TakenLoan
            taken_loan = TakenLoan.objects.create(
                lender_id=lender_id,
                loan_date=request.POST.get("loan_date"),
                # ... other fields
            )

            # Add collateral using enhanced method
            if hasattr(taken_loan, "add_collateral"):
                taken_loan.add_collateral(
                    loan_items=list(items),
                    user=request.user,
                    notes=request.POST.get("notes", ""),
                )
            else:
                # Manual repledge
                total_value = sum(item.current_value() for item in items)
                for item in items:
                    item_amount = (item.current_value() / total_value) * loan_amount
                    item.repledge_to(
                        taken_loan=taken_loan,
                        amount=item_amount,
                        user=request.user,
                        notes=request.POST.get("notes", ""),
                    )

        messages.success(
            request,
            f"TakenLoan {taken_loan.loan_id} created with {len(items)} collateral item(s)",
        )
        return redirect("girvi:loan_detail", pk=taken_loan.id)

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

    # Get collateral items
    collateral = (
        loan.collateral_items.all() if hasattr(loan, "collateral_items") else []
    )

    # Group by source customer
    by_customer = {}
    for item in collateral:
        customer = item.loan.borrower
        if customer not in by_customer:
            by_customer[customer] = {"items": [], "total_value": Decimal(0), "count": 0}
        by_customer[customer]["items"].append(item)
        by_customer[customer]["total_value"] += item.current_value()
        by_customer[customer]["count"] += 1

    # Calculate LTV ratio
    total_collateral_value = sum(item.current_value() for item in collateral)
    loan_amount = (
        loan.get_loan_amount if hasattr(loan, "get_loan_amount") else loan.loan_amount
    )
    ltv_ratio = (
        (loan_amount / total_collateral_value * 100)
        if total_collateral_value > 0
        else 0
    )

    context = {
        "loan": loan,
        "collateral_items": collateral,
        "by_customer": by_customer,
        "total_collateral_value": total_collateral_value,
        "loan_amount": loan_amount,
        "ltv_ratio": ltv_ratio,
        "can_return_all": collateral.exists(),
    }

    return render(request, "girvi/taken_loan_collateral.html", context)


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
        return redirect("girvi:loan_detail", pk=loan_id)

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
