from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from apps.orgs.audit import AuditLog
from apps.tenant_apps.party.models import PartyPortalAccess


ACTION_PORTAL_ACCESS_ACTIVATE = "PARTY_PORTAL_ACCESS_ACTIVATE"
ACTION_PORTAL_ACCESS_SUSPEND = "PARTY_PORTAL_ACCESS_SUSPEND"
ACTION_PORTAL_ACCESS_REVOKE = "PARTY_PORTAL_ACCESS_REVOKE"


class PortalAccessLifecycleError(ValueError):
    """Raised when a portal access grant transition is not allowed."""


@dataclass(frozen=True)
class PortalAccessLifecycleResult:
    grant: PartyPortalAccess
    changed: bool


def activate_portal_access(
    grant: PartyPortalAccess,
    *,
    actor=None,
    request=None,
    workspace=None,
) -> PortalAccessLifecycleResult:
    if grant.status == PartyPortalAccess.Status.REVOKED:
        raise PortalAccessLifecycleError("Revoked portal access cannot be activated.")

    previous_status = grant.status
    changed = previous_status != PartyPortalAccess.Status.ACTIVE
    with transaction.atomic():
        grant.activate(save=True)

    if changed:
        _log_portal_access_event(
            action=ACTION_PORTAL_ACCESS_ACTIVATE,
            grant=grant,
            actor=actor,
            request=request,
            workspace=workspace,
            previous_status=previous_status,
        )
    return PortalAccessLifecycleResult(grant=grant, changed=changed)


def suspend_portal_access(
    grant: PartyPortalAccess,
    *,
    actor=None,
    request=None,
    workspace=None,
) -> PortalAccessLifecycleResult:
    if grant.status == PartyPortalAccess.Status.REVOKED:
        raise PortalAccessLifecycleError("Revoked portal access cannot be suspended.")

    previous_status = grant.status
    changed = previous_status != PartyPortalAccess.Status.SUSPENDED
    if changed:
        with transaction.atomic():
            grant.status = PartyPortalAccess.Status.SUSPENDED
            grant.save(update_fields=["status", "updated_at"])
        _log_portal_access_event(
            action=ACTION_PORTAL_ACCESS_SUSPEND,
            grant=grant,
            actor=actor,
            request=request,
            workspace=workspace,
            previous_status=previous_status,
        )
    return PortalAccessLifecycleResult(grant=grant, changed=changed)


def revoke_portal_access(
    grant: PartyPortalAccess,
    *,
    actor=None,
    request=None,
    workspace=None,
) -> PortalAccessLifecycleResult:
    previous_status = grant.status
    changed = previous_status != PartyPortalAccess.Status.REVOKED
    if changed:
        with transaction.atomic():
            grant.revoke(save=True)
        _log_portal_access_event(
            action=ACTION_PORTAL_ACCESS_REVOKE,
            grant=grant,
            actor=actor,
            request=request,
            workspace=workspace,
            previous_status=previous_status,
        )
    return PortalAccessLifecycleResult(grant=grant, changed=changed)


def _log_portal_access_event(
    *,
    action,
    grant,
    actor,
    request,
    workspace,
    previous_status,
) -> None:
    workspace = _resolve_workspace(
        workspace=workspace,
        request=request,
        grant=grant,
    )
    data = {
        "party_id": grant.party_id,
        "target_user_id": grant.user_id,
        "portal_access_id": grant.pk,
        "previous_status": previous_status,
        "new_status": grant.status,
    }
    description = (
        f"Portal access for party {grant.party_id} changed from "
        f"{previous_status} to {grant.status}."
    )
    AuditLog.log(
        action,
        user=actor,
        company=workspace,
        description=description,
        data=data,
        request=request,
        success=True,
    )


def _resolve_workspace(*, workspace, request, grant):
    if workspace is not None:
        return workspace

    request_workspace = getattr(request, "workspace", None)
    if request_workspace is not None:
        return request_workspace
    return grant.workspace
