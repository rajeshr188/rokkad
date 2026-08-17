from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError

from apps.orgs.models import Company
from apps.orgs.permissions import is_platform_admin


ALLOWED_TRANSITIONS = {
    Company.LifecycleState.ACTIVE: {
        Company.LifecycleState.SUSPENDED,
        Company.LifecycleState.ARCHIVED,
    },
    Company.LifecycleState.SUSPENDED: {
        Company.LifecycleState.ACTIVE,
        Company.LifecycleState.ARCHIVED,
    },
    Company.LifecycleState.ARCHIVED: {
        Company.LifecycleState.ACTIVE,
        Company.LifecycleState.DELETION_PENDING,
    },
    Company.LifecycleState.DELETION_PENDING: {
        Company.LifecycleState.ARCHIVED,
    },
}


@dataclass(frozen=True)
class WorkspaceLifecycleAccess:
    may_enter_business: bool
    may_use_recovery: bool
    may_view_metadata: bool


def lifecycle_access(*, workspace, access):
    state = getattr(workspace, "lifecycle_state", Company.LifecycleState.ACTIVE)
    elevated = access.platform_override or access.can("workspace.settings.manage")
    owner_or_platform = access.platform_override or (
        getattr(workspace, "owner_id", None) == getattr(access.actor, "id", None)
    )
    return WorkspaceLifecycleAccess(
        may_enter_business=state == Company.LifecycleState.ACTIVE,
        may_use_recovery=(state == Company.LifecycleState.SUSPENDED and elevated)
        or (
            state
            in {
                Company.LifecycleState.ARCHIVED,
                Company.LifecycleState.DELETION_PENDING,
            }
            and owner_or_platform
        ),
        may_view_metadata=state == Company.LifecycleState.ACTIVE
        or elevated
        or owner_or_platform,
    )


def validate_transition(*, workspace, target_state, actor):
    if target_state not in Company.LifecycleState.values:
        raise ValidationError("Unknown Workspace lifecycle state.")
    if target_state == workspace.lifecycle_state:
        raise ValidationError("Workspace is already in that lifecycle state.")
    if target_state not in ALLOWED_TRANSITIONS[workspace.lifecycle_state]:
        raise ValidationError(
            f"Invalid Workspace lifecycle transition: {workspace.lifecycle_state} -> {target_state}."
        )

    platform = is_platform_admin(actor)
    owner = workspace.owner_id == getattr(actor, "id", None)
    if target_state == Company.LifecycleState.SUSPENDED and not platform:
        raise PermissionDenied("Only a platform administrator may suspend a Workspace.")
    if (
        workspace.lifecycle_state == Company.LifecycleState.SUSPENDED
        and target_state == Company.LifecycleState.ACTIVE
        and not platform
    ):
        raise PermissionDenied("Only a platform administrator may clear a suspension.")
    if target_state == Company.LifecycleState.DELETION_PENDING and not platform:
        raise PermissionDenied("Only a platform administrator may schedule erasure.")
    if not (owner or platform):
        raise PermissionDenied(
            "Only the Workspace owner or platform administrator may change lifecycle state."
        )
