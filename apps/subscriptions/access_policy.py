"""Workspace activity policy; never changes subscription or payment evidence."""
from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.orgs.permissions import is_platform_admin
from .billing import effective_billing_state
from .models import Plan, Subscription, WorkspaceAccessDecision


@dataclass(frozen=True)
class WorkspaceActivity:
    mode: str
    reason: str
    until: object = None
    subscription: object = None
    grant: object = None

    @property
    def can_write(self):
        return self.mode in {"full", "grace"}

    @property
    def can_read(self):
        return self.mode in {"full", "grace", "read_only"}


def workspace_activity(workspace, *, at=None):
    at = at or timezone.now()
    if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        return WorkspaceActivity("blocked", "Workspace access is restricted by its operational status.")
    subscription = Subscription.objects.filter(company=workspace).first()
    latest = WorkspaceAccessDecision.objects.filter(workspace=workspace).first()
    # Inspect the latest decision only: an older grant must never reappear.
    if latest and latest.mode != "default" and at < latest.expires_at:
        return WorkspaceActivity(latest.mode,
            "Temporary access approved by the platform administrator." if latest.mode == "full"
            else "The platform administrator has temporarily limited this workspace to read-only access.",
            latest.expires_at, subscription, latest)
    if subscription is None:
        if latest:
            return WorkspaceActivity("read_only", "Temporary workspace access has ended. Existing records remain available in read-only mode.")
        return WorkspaceActivity("recovery", "This workspace needs a subscription or administrator-approved access.")
    billing = effective_billing_state(subscription, at=at)
    if billing.commercially_available:
        end = subscription.trial_end_date if subscription.status == "trial" else subscription.end_date
        return WorkspaceActivity("full", "Subscription access is active.", end, subscription)
    end = (subscription.trial_end_date if subscription.status == "trial" else
           subscription.end_date if subscription.status == "active" else None)
    grace_end = end + timedelta(days=settings.SUBSCRIPTION_GRACE_DAYS) if end else None
    label = "Your trial has ended." if subscription.status == "trial" else "Your subscription is no longer active."
    if grace_end and end <= at < grace_end:
        return WorkspaceActivity("grace", label + " Normal access continues during the grace period.", grace_end, subscription)
    return WorkspaceActivity("read_only", label + " Existing records remain available in read-only mode.", subscription=subscription)


def require_business_write(workspace):
    """Guard business commands, including jobs with no HTTP request.

    No-subscription operator provisioning retains its explicit authorization;
    ordinary HTTP requests without a subscription remain recovery-only.
    """
    decision = workspace_activity(workspace)
    if decision.mode in {"read_only", "blocked"}:
        raise PermissionDenied(decision.reason)


@transaction.atomic
def record_access_decision(*, workspace, actor, mode, expires_at=None, reason, plan=None):
    if not actor or not is_platform_admin(actor) or not actor.is_active:
        raise PermissionDenied("Only an active platform administrator may grant or restrict access.")
    locked = Company.all_objects.select_for_update().get(pk=workspace.pk)
    reason = (reason or "").strip()
    if not reason or len(reason) > 1000:
        raise ValidationError("Enter a reason of 1 to 1000 characters.")
    if mode not in WorkspaceAccessDecision.Mode.values:
        raise ValidationError("Choose a supported access mode.")
    now = timezone.now()
    if mode == "default":
        if expires_at is not None:
            raise ValidationError("Returning to the subscription policy does not take an expiry date.")
    elif expires_at is None or timezone.is_naive(expires_at) or expires_at <= now:
        raise ValidationError("Choose a future expiry date with a time zone.")
    subscription = Subscription.objects.filter(company=locked).first()
    snapshot = []
    if mode == "full" and subscription is None:
        if plan is None or not Plan.objects.filter(pk=plan.pk, is_active=True).exists():
            raise ValidationError("Choose an active plan for a workspace without a subscription.")
        from .services import build_entitlement_defaults
        plan = Plan.objects.get(pk=plan.pk)
        snapshot = build_entitlement_defaults(SimpleNamespace(plan=plan))
    else:
        plan = None
    decision = WorkspaceAccessDecision.objects.create(
        workspace=locked, actor=actor, mode=mode, expires_at=expires_at,
        reason=reason, created_at=now, plan=plan, entitlement_snapshot=snapshot,
    )
    from apps.orgs.audit import AuditLog
    AuditLog.log("SETTINGS_UPDATE", user=actor, company=locked,
        description="Platform commercial-access decision", success=True,
        data={"access_decision_id": decision.pk, "mode": mode,
              "expires_at": expires_at.isoformat() if expires_at else None, "reason": reason})
    return decision
