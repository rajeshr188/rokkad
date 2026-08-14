from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apps.subscriptions.services import (
    ensure_workspace_member_capacity,
    get_workspace_member_usage,
    resolve_workspace_max_users_limit,
)


NON_SEAT_ROLES = {
    "guest",
    "portal",
    "portal_user",
}


@dataclass
class SeatCapacitySnapshot:
    limit: int | None
    members_used: int
    members_and_pending_used: int

    @property
    def has_limit(self) -> bool:
        return self.limit is not None

    @property
    def members_remaining(self) -> int | None:
        if self.limit is None:
            return None
        return max(self.limit - self.members_used, 0)

    @property
    def members_and_pending_remaining(self) -> int | None:
        if self.limit is None:
            return None
        return max(self.limit - self.members_and_pending_used, 0)


def role_consumes_seat(role: Any) -> bool:
    role_name = str(getattr(role, "name", role) or "").strip().lower()
    if not role_name:
        return True
    return role_name not in NON_SEAT_ROLES


def get_workspace_seat_capacity_snapshot(*, workspace: Any) -> SeatCapacitySnapshot:
    limit = resolve_workspace_max_users_limit(workspace=workspace)
    members_used = get_workspace_member_usage(
        workspace=workspace,
        include_pending_invitations=False,
    )
    members_and_pending_used = get_workspace_member_usage(
        workspace=workspace,
        include_pending_invitations=True,
    )
    return SeatCapacitySnapshot(
        limit=limit,
        members_used=members_used,
        members_and_pending_used=members_and_pending_used,
    )


def ensure_workspace_has_member_capacity(
    *,
    workspace: Any,
    include_pending_invitations: bool,
    extra_slots: int = 1,
) -> None:
    ensure_workspace_member_capacity(
        workspace=workspace,
        include_pending_invitations=include_pending_invitations,
        extra_slots=extra_slots,
    )


def ensure_role_change_within_capacity(
    *,
    workspace: Any,
    old_role: Any,
    new_role: Any,
) -> None:
    if role_consumes_seat(old_role) or not role_consumes_seat(new_role):
        return
    ensure_workspace_has_member_capacity(
        workspace=workspace,
        include_pending_invitations=False,
        extra_slots=1,
    )
