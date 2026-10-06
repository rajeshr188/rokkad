"""Reviewed global lifecycle operations; commercial access is never changed."""
from copy import copy

from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.orgs.services.control_plane import transition_workspace_lifecycle
from apps.orgs.services.platform_console import ACCESS_LABELS, require_console_access, workspaces
from apps.subscriptions.access_policy import workspace_activity


ACTIONS = {"suspend": ("ACTIVE", "SUSPENDED"), "restore": ("SUSPENDED", "ACTIVE")}
SALT = "platform.lifecycle.review.v1"


def _review(workspace, action, actor):
    if action not in ACTIONS or workspace.lifecycle_state != ACTIONS[action][0]:
        raise ValidationError("This action is no longer available for this workspace. Return to its overview.")
    projected = copy(workspace)
    projected.lifecycle_state = ACTIONS[action][1]
    now = timezone.now()
    activity = workspace_activity(projected, at=now)
    fingerprint = {
        "workspace": workspace.pk, "actor": actor.pk, "action": action,
        "state": workspace.lifecycle_state, "changed": workspace.lifecycle_changed_at.isoformat(),
        "owner": workspace.owner_id, "owner_email": workspace.owner.email,
        "name": workspace.name, "slug": workspace.slug, "reason": activity.reason,
        "access": activity.mode, "until": activity.until.isoformat() if activity.until else None,
    }
    return {"workspace": workspace, "action": action, "activity": activity,
            "access_label": ACCESS_LABELS[activity.mode], "checked_at": now,
            "review_token": signing.dumps(fingerprint, salt=SALT)}, fingerprint


def review_lifecycle(*, actor, slug, action):
    require_console_access(actor)
    workspace = get_object_or_404(workspaces().select_related("owner"), slug=slug)
    return _review(workspace, action, actor)[0]


def confirm_lifecycle(*, actor, slug, action, token, reason, confirmation, request=None):
    require_console_access(actor)
    if not (reason or "").strip() or len(reason.strip()) > 1000:
        raise ValidationError("Provide a reason of up to 1,000 characters.")
    try:
        reviewed = signing.loads(token, salt=SALT, max_age=900)
    except signing.BadSignature as exc:
        raise ValidationError("This confirmation has expired or is invalid. Review the current details again.") from exc
    with transaction.atomic():
        workspace = get_object_or_404(workspaces().select_for_update(), slug=slug)
        _, current = _review(workspace, action, actor)
        if reviewed != current:
            raise ValidationError("The workspace or its access has changed. Review the current details again.")
        if confirmation != workspace.slug:
            raise ValidationError("Type the workspace slug exactly to confirm.")
        return transition_workspace_lifecycle(workspace=workspace, target_state=ACTIONS[action][1],
            actor=actor, reason=reason, request=request)
