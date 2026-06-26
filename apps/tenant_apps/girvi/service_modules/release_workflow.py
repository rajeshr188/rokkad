"""Release workflow orchestration helpers to keep views thin."""

from dataclasses import dataclass, field as dc_field
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError

from apps.tenant_apps.girvi.policies import assert_can_create_release
from apps.tenant_apps.girvi.service_modules.custody import (
    build_release_readiness_checklist,
)
from apps.tenant_apps.girvi.services import ReleaseCreateCommand, ReleaseLifecycleService


@dataclass
class ReleaseFlowStep:
    label: str
    status: str
    detail: str
    passed: bool = False
    badge_class: str = "bg-secondary"


@dataclass
class ReleaseFlowContext:
    loan: object | None = None
    checklist: dict | None = None
    preview: object | None = None
    can_submit: bool = False
    recipient_label: str = ""
    document_status: str = "Pending"
    document_detail: str = "Form H will be generated after the release is saved."
    posting_status: str = "Pending"
    posting_detail: str = "Release submit will run the accounting posting step."
    blockers: list[str] = dc_field(default_factory=list)
    warnings: list[str] = dc_field(default_factory=list)
    steps: list[ReleaseFlowStep] = dc_field(default_factory=list)


@dataclass
class ReleaseSubmissionResult:
    success: bool = False
    release: object | None = None
    message: str = ""
    warnings: list[str] = dc_field(default_factory=list)
    blocker_messages: list[str] = dc_field(default_factory=list)
    execution_error: str = ""


class ReleaseWorkflowService:
    """Orchestrate release preview and submit business flow."""

    @staticmethod
    def _display_name(value):
        if not value:
            return ""
        for attr in ("name", "full_name", "username"):
            label = getattr(value, attr, None)
            if label:
                return str(label)
        return str(value)

    @staticmethod
    def _amount_gt_zero(value):
        if value is None:
            return False
        try:
            return Decimal(str(value)) > Decimal("0.00")
        except (InvalidOperation, TypeError, ValueError):
            return False

    @staticmethod
    def build_preview(loan, *, user, release_date=None, released_by=None):
        if not loan or not user:
            return None

        return ReleaseLifecycleService.preview(
            ReleaseCreateCommand(
                loan=loan,
                created_by=user,
                release_date=release_date,
                released_by=released_by,
            )
        )

    @classmethod
    def build_flow_context(
        cls,
        loan,
        *,
        user,
        checklist=None,
        preview=None,
        release_date=None,
        released_by=None,
    ):
        if not loan:
            return None

        readiness = checklist or build_release_readiness_checklist(loan)
        release_preview = preview
        if release_preview is None and user:
            release_preview = cls.build_preview(
                loan,
                user=user,
                release_date=release_date,
                released_by=released_by,
            )

        preview_errors = list(getattr(release_preview, "errors", []) or [])
        preview_warnings = list(getattr(release_preview, "warnings", []) or [])
        blockers = list(readiness.get("blockers", []) or []) + preview_errors
        outstanding_amount = readiness.get("outstanding_amount")
        release_ready = bool(readiness.get("can_release", False))
        settlement_clear = bool(readiness.get("dues_clear", release_ready))
        custody_clear = bool(readiness.get("custody_clear", release_ready))
        total_with_lenders = readiness.get("total_with_lenders", 0)
        recipient = released_by or getattr(release_preview, "released_by", None)
        recipient_label = cls._display_name(recipient or getattr(loan, "borrower", None))

        if cls._amount_gt_zero(outstanding_amount):
            posting_detail = (
                "Release submit will create the release document and post the "
                "settlement receipt through the accounting adapter."
            )
        else:
            posting_detail = (
                "Release submit will create the release document; no receipt is "
                "expected when settlement outstanding is already clear."
            )

        can_submit = bool(
            release_ready
            and not preview_errors
            and release_preview is not None
        )

        steps = [
            ReleaseFlowStep(
                label="Settlement",
                status="Clear" if settlement_clear else "Pending",
                detail=f"Outstanding: {outstanding_amount}",
                passed=settlement_clear,
                badge_class="bg-success" if settlement_clear else "bg-danger",
            ),
            ReleaseFlowStep(
                label="Custody",
                status="Ready" if custody_clear else "Return Required",
                detail=f"{total_with_lenders} item(s) with lenders",
                passed=custody_clear,
                badge_class="bg-success" if custody_clear else "bg-danger",
            ),
            ReleaseFlowStep(
                label="Recipient",
                status="Selected" if recipient_label else "Missing",
                detail=recipient_label or "Select the person receiving the collateral.",
                passed=bool(recipient_label),
                badge_class="bg-success" if recipient_label else "bg-warning text-dark",
            ),
            ReleaseFlowStep(
                label="Document",
                status="After Submit",
                detail="Form H is generated from the saved release document.",
                passed=can_submit,
                badge_class="bg-info text-dark" if can_submit else "bg-secondary",
            ),
            ReleaseFlowStep(
                label="Accounting",
                status="Will Post" if can_submit else "Blocked",
                detail=posting_detail,
                passed=can_submit,
                badge_class="bg-info text-dark" if can_submit else "bg-secondary",
            ),
        ]

        return ReleaseFlowContext(
            loan=loan,
            checklist=readiness,
            preview=release_preview,
            can_submit=can_submit,
            recipient_label=recipient_label,
            document_status="After Submit",
            posting_status="Will Post" if can_submit else "Blocked",
            posting_detail=posting_detail,
            blockers=[message for message in blockers if message],
            warnings=preview_warnings,
            steps=steps,
        )

    @classmethod
    def submit(cls, *, loan, release_date, released_by, user, checklist=None):
        readiness = checklist or build_release_readiness_checklist(loan)

        try:
            assert_can_create_release(loan, checklist=readiness)
        except ValidationError as exc:
            blockers = list(readiness.get("blockers", []))
            blockers.extend(getattr(exc, "messages", None) or [str(exc)])
            return ReleaseSubmissionResult(
                success=False,
                blocker_messages=[message for message in blockers if message],
                execution_error="Release checklist is not ready.",
            )

        result = ReleaseLifecycleService.execute(
            ReleaseCreateCommand(
                loan=loan,
                created_by=user,
                release_date=release_date,
                released_by=released_by,
            )
        )
        if result.success:
            return ReleaseSubmissionResult(
                success=True,
                release=result.release,
                message=result.message,
                warnings=list(result.warnings or []),
            )

        return ReleaseSubmissionResult(
            success=False,
            execution_error=result.message,
        )
