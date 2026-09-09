from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError

from apps.orgs.access import resolve_workspace_access
from apps.orgs.permissions import is_platform_admin


ELEVATED_ROLE_NAMES = {"owner", "admin"}
OWNER_ROLE_NAME = "owner"


def role_name(role) -> str:
    return (getattr(role, "name", "") or "").strip().lower()


def membership_role_name(membership) -> str:
    return role_name(getattr(membership, "role", None))


def is_owner_membership(membership) -> bool:
    if not membership:
        return False
    company = membership.company
    canonical_owner_id = getattr(company, "owner_id", None)
    if canonical_owner_id is None and getattr(company, "owner", None) is not None:
        canonical_owner_id = getattr(company.owner, "id", None)
    if canonical_owner_id is None:
        return membership_role_name(membership) == OWNER_ROLE_NAME
    member_user_id = getattr(
        membership, "user_id", getattr(getattr(membership, "user", None), "id", None)
    )
    return member_user_id == canonical_owner_id


def owner_membership_count(workspace) -> int:
    return 1 if getattr(workspace, "owner_id", None) else 0


def actor_can_grant_role(*, actor, workspace, role) -> bool:
    """Authorize the actual local grants, never just a harmless-looking label."""
    from apps.orgs.access import normalize_action
    from apps.orgs.models import WorkspaceRole
    from apps.orgs.services.workspace_roles import stored_role_codes
    from apps.tenancy.context import workspace_context
    if role_name(role) == OWNER_ROLE_NAME:
        return False
    with workspace_context(workspace.pk):
        if not WorkspaceRole.objects.filter(workspace=workspace, role=role).exists():
            return False
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if access.platform_override:
        return True
    if not access.membership:
        return False
    if _actor_is_owner(actor, workspace):
        return access.can("team.invite")
    if not access.can("team.invite"):
        return False
    target = {normalize_action(code) for code in stored_role_codes(workspace.pk, role.pk)}
    protected = {"workspace.edit", "workspace.settings.manage", "workspace.archive",
                 "workspace.delete", "workspace.transfer", "team.member.remove",
                 "team.member.role.change", "team.invite.elevated", "billing.manage",
                 "billing.edit", "billing.cancel", "admin.access"}
    return not (target & protected) and target <= access.actions


def allowed_invitation_roles(*, actor, workspace):
    from apps.orgs.models import Role
    allowed = [role.pk for role in Role.objects.order_by("name")
               if actor_can_grant_role(actor=actor, workspace=workspace, role=role)]
    return Role.objects.filter(pk__in=allowed).order_by("name")


def assert_can_invite_role(*, actor, workspace, role):
    if not actor_can_grant_role(actor=actor, workspace=workspace, role=role):
        raise ValidationError(
            "You do not have permission to invite users with this role."
        )


def assert_can_change_role(*, actor, workspace, membership, new_role):
    """Validate role transitions before changing a membership role."""
    from apps.orgs.models import WorkspaceRole
    from apps.tenancy.context import workspace_context
    with workspace_context(workspace.pk):
        if not WorkspaceRole.objects.filter(workspace=workspace, role=new_role).exists():
            raise PermissionDenied("Role is not available in this workspace.")
    if role_name(new_role) == OWNER_ROLE_NAME:
        raise PermissionDenied("Use ownership transfer to assign the Owner role.")
    if is_platform_admin(actor):
        _assert_owner_count_safe(membership=membership, new_role=new_role)
        return

    if not _actor_is_owner(actor, workspace):
        raise PermissionDenied("Only workspace owners can change member roles.")

    if getattr(membership, "user", None) == actor and role_name(new_role) != OWNER_ROLE_NAME:
        raise PermissionDenied("Owners must transfer ownership before changing their own owner role.")

    _assert_owner_count_safe(membership=membership, new_role=new_role)


def assert_can_remove_membership(*, actor, workspace, membership):
    """Validate membership removal, including self-leave and last-owner protection."""
    if is_platform_admin(actor):
        _assert_can_remove_owner(membership=membership)
        return

    if getattr(membership, "user", None) == actor:
        if is_owner_membership(membership):
            raise PermissionDenied("Owner must transfer ownership before leaving the workspace.")
        return

    if not _actor_is_owner(actor, workspace):
        raise PermissionDenied("Only workspace owners can remove team members.")

    _assert_can_remove_owner(membership=membership)


def _actor_is_owner(actor, workspace) -> bool:
    owner_id = getattr(workspace, "owner_id", None)
    if owner_id is not None:
        return owner_id == getattr(actor, "id", None)
    owner = getattr(workspace, "owner", None)
    if owner is not None:
        return owner == actor
    from apps.orgs.models import Membership
    return Membership.objects.filter(
        user=actor, company=workspace, role__name__iexact="Owner"
    ).exists()


def _assert_owner_count_safe(*, membership, new_role):
    demoting_owner = (
        is_owner_membership(membership)
        and role_name(new_role) != OWNER_ROLE_NAME
    )
    if demoting_owner and owner_membership_count(membership.company) <= 1:
        raise PermissionDenied("Cannot demote the last owner. Transfer ownership first.")


def _assert_can_remove_owner(*, membership):
    if is_owner_membership(membership) and owner_membership_count(membership.company) <= 1:
        raise PermissionDenied("Cannot remove the last owner. Transfer ownership first.")
