"""One selected monthly offer, with signed, time-limited owner consent."""
from decimal import Decimal
from uuid import uuid4

from allauth.account.models import EmailAddress
from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone

from apps.orgs.models import Company, Membership
from .checkout import require_billing_owner
from .models import Invoice, RecurringAgreement, RecurringPlanBinding, Subscription, WorkspaceAccessDecision
from .recurring import _offer, recurring_provider_mode
from .services import get_workspace_member_usage


TERMS = "public-monthly-1499-6members-12collections-20260930"
SALT = "subscriptions.public-monthly"
CONSENT_MAX_AGE = 1800


def selected_binding():
    """No generic catalog publication, provider calls or database writes."""
    if not (settings.BILLING_RECURRING_ENABLED and settings.BILLING_PUBLIC_RECURRING_BINDING_ID):
        raise ValidationError("Monthly subscriptions are not available for self-service yet.")
    binding = RecurringPlanBinding.objects.select_related("plan").filter(
        pk=settings.BILLING_PUBLIC_RECURRING_BINDING_ID, mode=recurring_provider_mode(),
    ).first()
    if binding is None:
        raise ValidationError("The monthly offer is unavailable. Contact support.")
    snapshot = binding.snapshot
    if (snapshot.get("billing_cycle") != "monthly" or snapshot.get("amount") != 149900
            or snapshot.get("currency") != "INR" or binding.plan.max_users != 6
            or Decimal(snapshot.get("tax_rate", "-1")) != 0
            or snapshot != _offer(binding.plan, "monthly", mode=binding.mode)):
        raise ValidationError("The monthly offer has changed. Contact support before paying.")
    return binding


def require_public_owner(*, workspace, actor):
    require_billing_owner(workspace=workspace, actor=actor)
    if (not actor.is_active or workspace.owner_id != actor.pk
            or not Membership.objects.filter(company=workspace, user=actor).exists()):
        raise PermissionDenied("Only the Workspace owner can accept a paid subscription.")
    if not actor.email or not EmailAddress.objects.filter(
        user=actor, email__iexact=actor.email, verified=True,
    ).exists():
        raise ValidationError("Verify your sign-in email before starting paid billing.")


def require_eligible(workspace):
    """First paid subscription only; replacement and access exceptions need review."""
    if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise ValidationError("This Workspace cannot start a paid subscription.")
    if (RecurringAgreement.objects.filter(workspace=workspace).exists()
            or Invoice.objects.filter(subscription__company=workspace).exists()
            or WorkspaceAccessDecision.objects.filter(workspace=workspace).exists()):
        raise ValidationError("This Workspace has billing or access history to review. Contact support.")
    subscription = Subscription.objects.filter(company=workspace).first()
    if subscription and (subscription.status != "trial" or not subscription.trial_end_date
                         or subscription.razorpay_subscription_id):
        raise ValidationError("Contact support to review your existing subscription before paying.")
    if subscription and subscription.trial_end_date > timezone.now():
        raise ValidationError("Your free trial is still active. Return after it ends to start paid billing.")
    if get_workspace_member_usage(workspace=workspace, include_pending_invitations=True) > 6:
        raise ValidationError("This offer allows the owner plus five staff, including pending invitations.")


def offer_context(*, workspace, actor):
    try:
        binding = selected_binding()
        require_public_owner(workspace=workspace, actor=actor)
    except (ValidationError, PermissionDenied):
        return {}
    context = {"monthly_offer": binding, "monthly_terms": TERMS}
    try:
        require_eligible(workspace)
    except ValidationError as exc:
        context["monthly_unavailable_reason"] = exc.messages[0]
    else:
        context["monthly_consent"] = signing.dumps({
            "workspace_id": workspace.pk, "actor_id": actor.pk, "binding_id": binding.pk,
            "snapshot": binding.snapshot, "total_count": 12, "terms": TERMS,
            "request_key": str(uuid4()),
        }, salt=SALT, compress=True)
    return context


def read_consent(token, actor):
    try:
        consent = signing.loads(token, salt=SALT, max_age=CONSENT_MAX_AGE)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise ValidationError("This offer review expired or is invalid. Reload Recurring payments.") from exc
    if consent.get("actor_id") != actor.pk:
        raise PermissionDenied("This offer review belongs to another owner.")
    return consent


def validate_consent(*, workspace, actor, consent, binding_id, total_count, request_key, start_at):
    """Called under the Company lock, before reserving the provider attempt."""
    require_public_owner(workspace=workspace, actor=actor)
    binding = selected_binding()
    if (consent != {"workspace_id": workspace.pk, "actor_id": actor.pk, "binding_id": binding.pk,
                   "snapshot": binding.snapshot, "total_count": 12, "terms": TERMS,
                   "request_key": str(request_key)}
            or binding_id != binding.pk or total_count != 12 or start_at is not None):
        raise ValidationError("The offer has changed. Review the current monthly terms again.")
    return {"version": TERMS, "snapshot": binding.snapshot, "total_count": 12,
            "workspace_id": workspace.pk, "actor_id": actor.pk,
            "accepted_at": timezone.now().isoformat()}
