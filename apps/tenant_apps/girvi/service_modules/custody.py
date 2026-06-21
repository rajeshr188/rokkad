from dataclasses import dataclass, field
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from apps.tenant_apps.girvi.models import LoanItem, Series, TakenLoan
from apps.tenant_apps.girvi.models.custody_tracking import ItemCustodyStatus


CUSTODY_DISPLAY_STATUSES = (
    ItemCustodyStatus.IN_VAULT,
    ItemCustodyStatus.WITH_LENDER,
    ItemCustodyStatus.WITH_CUSTOMER,
)


@dataclass
class BulkReturnResult:
    returned_count: int = 0
    errors: list[str] = field(default_factory=list)


def group_loan_items_by_custody(loan):
    return {
        status: list(loan.loanitems.filter(custody_status=status))
        for status in CUSTODY_DISPLAY_STATUSES
    }


def group_items_by_lender(items):
    by_lender = {}
    for item in items:
        if item.repledged_to:
            lender_name = item.repledged_to.lender.name
            by_lender.setdefault(lender_name, []).append(item)
    return by_lender


def build_loan_custody_summary(loan):
    items_by_custody = group_loan_items_by_custody(loan)
    can_release, release_message = (
        loan.can_release() if hasattr(loan, "can_release") else (True, "")
    )
    return {
        "loan": loan,
        "items_by_custody": items_by_custody,
        "items_by_lender": group_items_by_lender(
            items_by_custody[ItemCustodyStatus.WITH_LENDER]
        ),
        "can_release": can_release,
        "release_message": release_message,
        "total_items": loan.loanitems.count(),
    }


def build_release_custody_check(loan):
    items_by_custody = group_loan_items_by_custody(loan)
    with_lender = items_by_custody[ItemCustodyStatus.WITH_LENDER]
    return {
        "loan": loan,
        "items_by_custody": items_by_custody,
        "items_by_lender": group_items_by_lender(with_lender),
        "needs_return": bool(with_lender),
        "total_with_lenders": len(with_lender),
    }


def return_all_items_from_taken_loan(*, loan, taken_loan, user):
    items = loan.loanitems.filter(
        repledged_to=taken_loan,
        custody_status=ItemCustodyStatus.WITH_LENDER,
    )
    result = BulkReturnResult()

    with transaction.atomic():
        for item in items:
            try:
                item.return_from_lender(
                    user=user,
                    notes=f"Bulk return from {taken_loan.lender.name}",
                )
                result.returned_count += 1
            except ValidationError as exc:
                result.errors.append(f"{item.itemdesc}: {exc}")

    return result


def release_loan_with_custody_return(*, loan, release_date, released_by, user):
    if hasattr(loan, "release_with_return_workflow"):
        return loan.release_with_return_workflow(
            release_date=release_date,
            released_by=released_by,
            created_by=user,
        )

    with transaction.atomic():
        for item in loan.loanitems.filter(custody_status=ItemCustodyStatus.WITH_LENDER):
            item.return_from_lender(
                user=user,
                notes=f"Returned for loan {loan.loan_id} release",
            )

        for item in loan.loanitems.filter(custody_status=ItemCustodyStatus.IN_VAULT):
            item.release_to_customer(user=user)

        return loan.create_release(
            release_date=release_date,
            released_by=released_by,
            created_by=user,
        )


def build_repledge_selection_context():
    available_items = LoanItem.objects.filter(
        custody_status=ItemCustodyStatus.IN_VAULT,
        repledged_to__isnull=True,
        loan__release__isnull=True,
    ).select_related("loan", "loan__borrower")

    by_customer = {}
    for item in available_items:
        by_customer.setdefault(item.loan.borrower, []).append(item)

    return {
        "available_items": available_items,
        "items_by_customer": by_customer,
        "total_value": sum(item.current_value() for item in available_items),
        "series_options": _active_taken_loan_series_queryset(),
    }


def _active_taken_loan_series_queryset():
    return Series.objects.active_for_loans().filter(loan_type=Series.LoanType.TAKEN)


def _resolve_repledge_series(series_id=None):
    if series_id:
        series = _active_taken_loan_series_queryset().filter(pk=series_id).first()
        if not series:
            raise ValidationError("Selected series is not active for loan creation")
        return series

    series = _active_taken_loan_series_queryset().order_by("created", "id").first()
    if series:
        return series

    series = Series.objects.active_for_loans().order_by("created", "id").first()
    if series:
        return series

    raise ValidationError("No active loan series is available for repledge creation")


def create_repledge_from_items(
    *, item_ids, lender_id, loan_amount, loan_date, notes, user, series_id=None
):
    if not item_ids:
        raise ValidationError("No items selected")

    with transaction.atomic():
        series = _resolve_repledge_series(series_id)
        items = list(LoanItem.objects.filter(id__in=item_ids))
        for item in items:
            if not item.is_available_for_repledge:
                raise ValidationError(f"Item {item.itemdesc} is not available for repledge")

        taken_loan = TakenLoan.objects.create(
            series=series,
            lender_id=lender_id,
            loan_date=loan_date,
        )

        if hasattr(taken_loan, "add_collateral"):
            taken_loan.add_collateral(
                loan_items=items,
                user=user,
                notes=notes,
            )
            return taken_loan

        total_value = sum(item.current_value() for item in items)
        for item in items:
            item_amount = (item.current_value() / total_value) * Decimal(loan_amount)
            item.repledge_to(
                taken_loan=taken_loan,
                amount=item_amount,
                user=user,
                notes=notes,
            )
        return taken_loan


def build_taken_loan_collateral_context(loan):
    collateral = (
        loan.collateral_items.all()
        if hasattr(loan, "collateral_items")
        else LoanItem.objects.none()
    )
    by_customer = {}
    for item in collateral:
        customer = item.loan.borrower
        by_customer.setdefault(
            customer,
            {"items": [], "total_value": Decimal("0"), "count": 0},
        )
        by_customer[customer]["items"].append(item)
        by_customer[customer]["total_value"] += item.current_value()
        by_customer[customer]["count"] += 1

    total_collateral_value = sum(item.current_value() for item in collateral)
    loan_amount = (
        loan.get_loan_amount if hasattr(loan, "get_loan_amount") else loan.loan_amount
    )
    ltv_ratio = (
        (loan_amount / total_collateral_value * 100)
        if total_collateral_value > 0
        else 0
    )

    return {
        "loan": loan,
        "collateral_items": collateral,
        "by_customer": by_customer,
        "total_collateral_value": total_collateral_value,
        "loan_amount": loan_amount,
        "ltv_ratio": ltv_ratio,
    }
