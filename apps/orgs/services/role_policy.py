from __future__ import annotations

from django.core.exceptions import PermissionDenied, ValidationError

from apps.orgs.permissions import get_effective_permissions, is_platform_admin


ELEVATED_ROLE_NAMES = {"owner", "admin"}
OWNER_ROLE_NAME = "owner"


def role_name(role) -> str:
    return (getattr(role, "name", "") or "").strip().lower()


def membership_role_name(membership) -> str:
    return role_name(getattr(membership, "role", None))


def is_owner_membership(membership) -> bool:
    return membership_role_name(membership) == OWNER_ROLE_NAME


def owner_membership_count(workspace) -> int:
    from apps.orgs.models import Membership

    return Membership.objects.filter(
        company=workspace,
        role__name__iexact="Owner",
    ).count()


def actor_can_grant_role(*, actor, workspace, role) -> bool:
    """Return whether actor may assign/invite the target role."""
    if is_platform_admin(actor):
        return True

    target_role = role_name(role)
    effective_permissions = get_effective_permissions(actor, workspace)

    if target_role in ELEVATED_ROLE_NAMES:
        return "team_invite_admin" in effective_permissions and _actor_is_owner(
            actor,
            workspace,
        )

    return "team_invite" in effective_permissions


def allowed_invitation_roles(*, actor, workspace):
    """Return Role queryset filtered to the roles actor may invite."""
    from apps.orgs.models import Role

    roles = Role.objects.all().order_by("name")
    if is_platform_admin(actor) or _actor_is_owner(actor, workspace):
        return roles
    return roles.exclude(name__iexact="Owner").exclude(name__iexact="Admin")


def assert_can_invite_role(*, actor, workspace, role):
    if not actor_can_grant_role(actor=actor, workspace=workspace, role=role):
        raise ValidationError(
            "You do not have permission to invite users with this role."
        )


def assert_can_change_role(*, actor, workspace, membership, new_role):
    """Validate role transitions before changing a membership role."""
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
    from apps.orgs.models import Membership

    return Membership.objects.filter(
        user=actor,
        company=workspace,
        role__name__iexact="Owner",
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
