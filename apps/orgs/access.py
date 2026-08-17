from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied

from apps.orgs.permissions import (
    get_all_permission_codenames,
    get_permissions_for_role,
    is_platform_admin,
)


ACTION_ALIASES = {
    "workspace_view": "workspace.view",
    "workspace_edit": "workspace.edit",
    "workspace_settings": "workspace.settings.manage",
    "workspace_archive": "workspace.archive",
    "workspace_delete": "workspace.delete",
    "workspace_transfer": "workspace.transfer",
    "team_view": "team.view",
    "team_list": "team.view",
    "team_invite": "team.invite",
    "team_invite_admin": "team.invite.elevated",
    "team_remove": "team.member.remove",
    "team_change_role": "team.member.role.change",
    "billing_view": "billing.view",
    "billing_manage": "billing.manage",
    "data_view": "data.view",
    "data_create": "data.create",
    "data_edit": "data.edit",
    "data_delete": "data.delete",
    "data_import": "data.import",
    "data_export": "data.export",
}


def normalize_action(code: str) -> str:
    return ACTION_ALIASES.get(code, code if "." in code else code.replace("_", "."))


@dataclass(frozen=True)
class WorkspaceAccess:
    actor: object
    workspace: object
    membership: object | None
    platform_override: bool
    actions: frozenset[str]

    def can(self, action: str) -> bool:
        return normalize_action(action) in self.actions

    def require(self, action: str) -> None:
        if not self.can(action):
            raise PermissionDenied(f"Workspace action denied: {normalize_action(action)}")


def resolve_workspace_access(*, actor, workspace) -> WorkspaceAccess:
    if not actor or not getattr(actor, "is_authenticated", False) or workspace is None:
        return WorkspaceAccess(actor, workspace, None, False, frozenset())

    if is_platform_admin(actor):
        codes = set(get_all_permission_codenames()) | {"admin_access"}
        return WorkspaceAccess(
            actor, workspace, None, True, frozenset(normalize_action(code) for code in codes)
        )

    from apps.orgs.models import Membership

    membership = (
        Membership.objects.select_related("role")
        .filter(user=actor, company=workspace)
        .first()
    )
    if membership is None:
        return WorkspaceAccess(actor, workspace, None, False, frozenset())

    codes = set(get_permissions_for_role(membership.role.name))
    role_permissions = getattr(membership.role, "permissions", None)
    if role_permissions is not None:
        codes.update(role_permissions.values_list("codename", flat=True))
    return WorkspaceAccess(
        actor,
        workspace,
        membership,
        False,
        frozenset(normalize_action(code) for code in codes),
    )
