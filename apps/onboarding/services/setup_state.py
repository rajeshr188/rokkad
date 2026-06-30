"""Workspace setup checklist display state helpers."""

from __future__ import annotations

from dataclasses import dataclass

from django.utils import timezone

from apps.onboarding.models import WorkspaceSetupState


@dataclass(frozen=True)
class WorkspaceSetupDisplayState:
    state: WorkspaceSetupState | None
    is_dismissed: bool
    is_marked_complete: bool
    is_checklist_complete: bool

    @property
    def is_complete(self) -> bool:
        return self.is_marked_complete or self.is_checklist_complete

    @property
    def should_show_dashboard_card(self) -> bool:
        return not self.is_dismissed and not self.is_complete


def build_workspace_setup_display_state(*, user, workspace, checklist):
    """Return setup display state without creating rows for passive reads."""
    state = (
        WorkspaceSetupState.objects.filter(user=user, workspace=workspace)
        .order_by("-updated_at")
        .first()
    )
    return WorkspaceSetupDisplayState(
        state=state,
        is_dismissed=bool(state and state.is_dismissed),
        is_marked_complete=bool(state and state.is_marked_complete),
        is_checklist_complete=checklist.is_complete,
    )


def dismiss_workspace_setup(*, user, workspace):
    state, _created = WorkspaceSetupState.objects.get_or_create(
        user=user,
        workspace=workspace,
    )
    if state.dismissed_at is None:
        state.dismissed_at = timezone.now()
        state.save(update_fields=["dismissed_at", "updated_at"])
    return state


def mark_workspace_setup_complete(*, user, workspace):
    state, _created = WorkspaceSetupState.objects.get_or_create(
        user=user,
        workspace=workspace,
    )
    if state.marked_complete_at is None:
        state.marked_complete_at = timezone.now()
        state.save(update_fields=["marked_complete_at", "updated_at"])
    return state


def reopen_workspace_setup(*, user, workspace):
    state, _created = WorkspaceSetupState.objects.get_or_create(
        user=user,
        workspace=workspace,
    )
    if state.dismissed_at is not None or state.marked_complete_at is not None:
        state.dismissed_at = None
        state.marked_complete_at = None
        state.save(update_fields=["dismissed_at", "marked_complete_at", "updated_at"])
    return state
