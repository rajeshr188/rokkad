from dataclasses import dataclass

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import Plan, Subscription, SubscriptionEvent


@dataclass(frozen=True)
class BillingDecision:
    status: str
    commercially_available: bool
    recovery_only: bool
    reason: str = "SUBSCRIPTION_INACTIVE"
    message: str = "Subscription access is unavailable."


def effective_billing_state(subscription, *, at=None):
    """Derive commercial availability without mutating stored state."""
    at = at or timezone.now()
    status = subscription.status
    if status == Subscription.StatusChoices.TRIAL:
        available = bool(subscription.trial_end_date and at <= subscription.trial_end_date)
        return BillingDecision(
            status=status if available else Subscription.StatusChoices.PAST_DUE,
            commercially_available=available,
            recovery_only=not available,
        )
    if status == Subscription.StatusChoices.ACTIVE:
        end_date = getattr(subscription, "end_date", None)
        if end_date is None or at >= end_date:
            return BillingDecision(
                status=Subscription.StatusChoices.EXPIRED,
                commercially_available=False,
                recovery_only=True,
                reason="SUBSCRIPTION_EXPIRED",
                message="Your paid subscription period has ended. Renew from Billing to continue.",
            )
        return BillingDecision(status=status, commercially_available=True, recovery_only=False)
    return BillingDecision(status=status, commercially_available=False, recovery_only=True)


ALLOWED_TRANSITIONS = {
    Subscription.StatusChoices.TRIAL: {
        Subscription.StatusChoices.ACTIVE,
        Subscription.StatusChoices.PAST_DUE,
        Subscription.StatusChoices.CANCELLED,
    },
    Subscription.StatusChoices.ACTIVE: {
        Subscription.StatusChoices.PAST_DUE,
        Subscription.StatusChoices.CANCELLED,
        Subscription.StatusChoices.EXPIRED,
    },
    Subscription.StatusChoices.PAST_DUE: {
        Subscription.StatusChoices.ACTIVE,
        Subscription.StatusChoices.CANCELLED,
        Subscription.StatusChoices.EXPIRED,
    },
    Subscription.StatusChoices.CANCELLED: {Subscription.StatusChoices.ACTIVE},
    Subscription.StatusChoices.EXPIRED: {Subscription.StatusChoices.ACTIVE},
}


def transition_subscription(*, subscription, target_status, event_type, payload=None):
    """Perform one locked, event-backed billing transition."""
    if target_status not in Subscription.StatusChoices.values:
        raise ValidationError("Unknown subscription status.")
    with transaction.atomic():
        locked = Subscription.objects.select_for_update().get(pk=subscription.pk)
        if target_status == locked.status:
            return locked, False
        if target_status not in ALLOWED_TRANSITIONS[locked.status]:
            raise ValidationError(
                f"Invalid subscription transition: {locked.status} -> {target_status}."
            )
        previous = locked.status
        locked.status = target_status
        if target_status == Subscription.StatusChoices.CANCELLED:
            locked.cancelled_at = timezone.now()
        elif target_status == Subscription.StatusChoices.ACTIVE:
            locked.cancelled_at = None
            locked.cancellation_reason = None
        locked.save(update_fields=["status", "cancelled_at", "cancellation_reason", "updated_at"])
        SubscriptionEvent.objects.create(
            subscription=locked,
            event_type=event_type,
            payload={"from_status": previous, "to_status": target_status, **(payload or {})},
        )
    return locked, True


def start_trial(*, workspace, plan, actor):
    """Start one explicit trial for a Workspace under a row lock."""
    from apps.orgs.models import Company
    from .services import (
        ensure_billing_account_for_subscription,
        ensure_entitlements_for_subscription,
    )

    if not plan.is_active or plan.trial_days <= 0:
        raise ValidationError("This plan is not eligible for a trial.")

    with transaction.atomic():
        locked_workspace = Company.all_objects.select_for_update().get(pk=workspace.pk)
        if Subscription.objects.filter(company=locked_workspace).exists():
            raise ValidationError("This Workspace already has a subscription or trial.")

        subscription = Subscription.objects.create(
            company=locked_workspace,
            plan=Plan.objects.get(pk=plan.pk, is_active=True),
        )
        ensure_billing_account_for_subscription(subscription)
        ensure_entitlements_for_subscription(subscription)
        SubscriptionEvent.objects.create(
            subscription=subscription,
            event_type="trial.started",
            payload={
                "plan_id": plan.pk,
                "actor_id": getattr(actor, "pk", None),
                "trial_end_date": subscription.trial_end_date.isoformat(),
            },
        )
    return subscription
