"""Stored per-Workspace grants for fixed role templates."""
import hashlib
import json

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied, ValidationError

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, Role, WorkspaceRole, WorkspaceRoleGrant
from apps.orgs.permissions import get_all_permission_codenames, get_permissions_for_role
from apps.tenancy.context import workspace_context


DEFAULT_ROLE_NAMES = ("Owner", "Admin", "Member", "Viewer")


def ensure_workspace_role(workspace_id, role_id):
    """Bootstrap only: copying a template never overwrites an existing local role."""
    with workspace_context(workspace_id):
        profile, created = WorkspaceRole.objects.get_or_create(workspace_id=workspace_id, role_id=role_id)
        if created:
            role = Role.objects.get(pk=role_id)
            codes = (set(get_permissions_for_role(role.name)) |
                     set(role.permissions.values_list("codename", flat=True))) & set(get_all_permission_codenames())
            ct = ContentType.objects.get_for_model(Company)
            found = {p.codename: p for p in Permission.objects.filter(content_type=ct, codename__in=codes)}
            Permission.objects.bulk_create([Permission(content_type=ct, codename=c, name=c)
                for c in sorted(codes - set(found))], ignore_conflicts=True)
            permissions = Permission.objects.filter(content_type=ct, codename__in=codes)
            WorkspaceRoleGrant.objects.bulk_create([
                WorkspaceRoleGrant(workspace_id=workspace_id, workspace_role=profile, permission=p)
                for p in permissions])
        return profile


def seed_workspace_roles(workspace_id):
    with workspace_context(workspace_id):
        existing = set(WorkspaceRole.objects.filter(workspace_id=workspace_id).values_list("role__name", flat=True))
        for name in DEFAULT_ROLE_NAMES:
            if name not in existing:
                role, _ = Role.objects.get_or_create(name=name)
                ensure_workspace_role(workspace_id, role.pk)


def stored_role_codes(workspace_id, role_id):
    with workspace_context(workspace_id):
        return set(WorkspaceRoleGrant.objects.filter(workspace_id=workspace_id,
            workspace_role__role_id=role_id).values_list("permission__codename", flat=True))


def role_grant_fingerprint(workspace_id, role_id):
    from apps.orgs.access import normalize_action
    actions = sorted({normalize_action(code) for code in stored_role_codes(workspace_id, role_id)})
    return hashlib.sha256(json.dumps(actions, separators=(",", ":")).encode()).hexdigest()


def update_workspace_role(*, workspace, role_id, permission_codes, revision, actor, request=None):
    from apps.orgs.access import normalize_action, resolve_workspace_access
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    if not access.platform_override and (not access.membership or workspace.owner_id != actor.pk):
        raise PermissionDenied("Only the workspace Owner can edit role permissions.")
    codes = set(permission_codes)
    allowed = set(get_all_permission_codenames())
    if not codes <= allowed:
        raise ValidationError("Unknown permission selection.")
    if any(normalize_action(code) == "workspace.transfer" for code in codes):
        raise ValidationError("Ownership authority cannot be assigned to another role.")
    with workspace_context(workspace.pk):
        profile = WorkspaceRole.objects.select_for_update().select_related("role").get(
            workspace_id=workspace.pk, role_id=role_id)
        if profile.role.name.strip().casefold() == "owner":
            raise PermissionDenied("Owner permissions are protected. Use ownership transfer.")
        if profile.revision != revision:
            raise ValidationError("Permissions changed since this page was opened. Reload and review them.")
        before = sorted(stored_role_codes(workspace.pk, role_id))
        ct = ContentType.objects.get_for_model(Company)
        permissions = [Permission.objects.get_or_create(content_type=ct, codename=c,
            defaults={"name": c})[0] for c in sorted(codes)]
        profile.grants.all().delete()
        WorkspaceRoleGrant.objects.bulk_create([WorkspaceRoleGrant(workspace=workspace,
            workspace_role=profile, permission=p) for p in permissions])
        profile.revision += 1
        profile.save(update_fields=["revision"])
        AuditLog.log("WORKSPACE_ROLE_PERMISSIONS", user=actor, company=workspace, request=request,
            data={"role_id": role_id, "before": before, "after": sorted(codes),
                  "affected_members": workspace.memberships.filter(role_id=role_id).count()}, success=True)
        return profile
