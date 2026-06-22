"""Release workflow orchestration helpers to keep views thin."""

from dataclasses import dataclass, field as dc_field

from django.core.exceptions import ValidationError

from apps.tenant_apps.girvi.policies import assert_can_create_release
from apps.tenant_apps.girvi.service_modules.custody import (
    build_release_readiness_checklist,
)
from apps.tenant_apps.girvi.services import ReleaseCreateCommand, ReleaseLifecycleService


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
