"""Workflow helpers for custody/release view orchestration."""

from dataclasses import dataclass

from django.db import transaction

from apps.tenant_apps.girvi.service_modules.custody import (
    build_release_readiness_checklist,
    release_loan_with_custody_return,
)


@dataclass
class ReleaseWithReturnGate:
    is_released: bool = False
    block_message: str = ""
    redirect_to_checklist: bool = False
    redirect_to_release_create: bool = False
    can_proceed: bool = False


@dataclass
class TakenLoanCollateralReturnResult:
    returned_count: int = 0


@dataclass
class ItemLenderReturnResult:
    item_description: str = ""


class CustodyWorkflowService:
    """Centralize custody/release gate logic used by custody views."""

    @staticmethod
    def build_release_checklist_context(loan):
        return build_release_readiness_checklist(loan)

    @staticmethod
    def evaluate_release_with_return_gate(loan, *, checklist):
        if getattr(loan, "is_released", False):
            return ReleaseWithReturnGate(is_released=True)

        if not (
            checklist.get("dues_clear", False)
            or checklist.get("settlement_collectable", False)
        ):
            return ReleaseWithReturnGate(
                block_message="Release is blocked until settlement can be calculated.",
                redirect_to_checklist=True,
            )

        if not checklist.get("needs_return", False):
            return ReleaseWithReturnGate(redirect_to_release_create=True)

        return ReleaseWithReturnGate(can_proceed=True)

    @staticmethod
    def execute_release_with_return(loan, *, release_date, released_by, user):
        return release_loan_with_custody_return(
            loan=loan,
            release_date=release_date,
            released_by=released_by,
            user=user,
        )

    @staticmethod
    def return_taken_loan_collateral(loan, *, user, notes=""):
        collateral_items = list(loan.collateral_items.all())
        returned_count = len(collateral_items)

        with transaction.atomic():
            if hasattr(loan, "return_all_collateral"):
                loan.return_all_collateral(user=user, notes=notes)
            else:
                for item in collateral_items:
                    item.return_from_lender(user=user, notes=notes)

        return TakenLoanCollateralReturnResult(returned_count=returned_count)

    @staticmethod
    def return_item_from_lender(item, *, user, notes=""):
        item.return_from_lender(user=user, notes=notes)
        return ItemLenderReturnResult(item_description=getattr(item, "itemdesc", str(item)))

    @staticmethod
    def build_release_custody_api_payload(loan):
        items_with_lender = loan.loanitems.filter(custody_status="WITH_LENDER")

        lenders = {
            item.repledged_to.lender.name
            for item in items_with_lender
            if getattr(item, "repledged_to", None)
        }

        can_release = not items_with_lender.exists()
        lender_count = items_with_lender.count()
        return {
            "can_release": can_release,
            "needs_return": not can_release,
            "items_with_lender": lender_count,
            "lenders": list(lenders),
            "message": (
                "All items in vault - can release"
                if can_release
                else f"{lender_count} item(s) with lender(s) - return required"
            ),
        }
