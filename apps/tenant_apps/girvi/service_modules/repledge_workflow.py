"""Workflow helpers for custody repledge create views."""

from dataclasses import dataclass

from apps.tenant_apps.girvi.service_modules.custody import (
    build_repledge_selection_context,
    create_repledge_from_items,
)


@dataclass
class RepledgeCreationResult:
    success: bool = False
    taken_loan: object | None = None
    error_message: str = ""
    selected_item_count: int = 0


class RepledgeWorkflowService:
    """Centralize request-data parsing and orchestration for repledge create paths."""

    @staticmethod
    def build_selection_context():
        return build_repledge_selection_context()

    @staticmethod
    def parse_create_payload(post_data):
        return {
            "item_ids": post_data.getlist("item_ids"),
            "lender_id": post_data.get("lender_id"),
            "loan_amount": post_data.get("loan_amount", 0),
            "loan_date": post_data.get("loan_date"),
            "notes": post_data.get("notes", ""),
            "series_id": post_data.get("series_id") or post_data.get("series"),
        }

    @classmethod
    def create_repledge(cls, post_data, *, user):
        payload = cls.parse_create_payload(post_data)
        try:
            taken_loan = create_repledge_from_items(
                item_ids=payload["item_ids"],
                lender_id=payload["lender_id"],
                loan_amount=payload["loan_amount"],
                loan_date=payload["loan_date"],
                notes=payload["notes"],
                user=user,
                series_id=payload["series_id"],
            )
            return RepledgeCreationResult(
                success=True,
                taken_loan=taken_loan,
                selected_item_count=len(payload["item_ids"]),
            )
        except Exception as exc:
            return RepledgeCreationResult(success=False, error_message=str(exc))
