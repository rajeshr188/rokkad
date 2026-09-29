"""The single reviewed public trial; private billing plans are not trial offers."""
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from apps.orgs.models import Company
from .billing import start_trial
from .checkout import require_billing_owner
from .models import Plan, RecurringAgreement, Subscription, WorkspaceAccessDecision
from .services import get_workspace_member_usage


PUBLIC_TRIAL_TERMS = "public-trial-30d-6members-20260929"


def public_trial_plans():
    """Fail closed until a separate zero-price plan is explicitly selected."""
    if not settings.BILLING_ALLOW_TRIAL_START or not settings.BILLING_PUBLIC_TRIAL_PLAN_ID:
        return Plan.objects.none()
    return Plan.objects.filter(
        pk=settings.BILLING_PUBLIC_TRIAL_PLAN_ID, is_active=True,
        price=0, yearly_price=0, trial_days=30, max_users=6,
        recurringplanbinding__isnull=True,
    )


@transaction.atomic
def start_public_trial(*, workspace, actor, plan_id, accepted_terms):
    require_billing_owner(workspace=workspace, actor=actor)
    workspace = Company.all_objects.select_for_update().get(pk=workspace.pk)
    require_billing_owner(workspace=workspace, actor=actor)
    if workspace.owner_id != actor.pk:
        raise PermissionDenied("Only the Workspace owner can accept the trial terms.")
    if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
        raise ValidationError("This Workspace cannot start a trial.")
    from allauth.account.models import EmailAddress
    if not actor.email or not EmailAddress.objects.filter(
        user=actor, email__iexact=actor.email, verified=True,
    ).exists():
        raise ValidationError("Verify your sign-in email before starting the trial.")
    if accepted_terms != PUBLIC_TRIAL_TERMS:
        raise ValidationError("Review and accept the 30-day trial terms before continuing.")
    # Lock the selected catalog row without an outer join in FOR UPDATE.
    plan = Plan.objects.select_for_update().filter(pk=plan_id).first()
    if plan is None or not public_trial_plans().filter(pk=plan.pk).exists():
        raise ValidationError("This plan is not available for public trial signup.")
    if (Subscription.objects.filter(company=workspace).exists()
            or RecurringAgreement.objects.filter(workspace=workspace).exists()
            or WorkspaceAccessDecision.objects.filter(workspace=workspace).exists()):
        raise ValidationError("This Workspace already has billing or access history. Contact support.")
    if get_workspace_member_usage(workspace=workspace, include_pending_invitations=True) > 6:
        raise ValidationError("The trial includes the owner and up to five staff, including pending invitations.")
    return start_trial(workspace=workspace, plan=plan, actor=actor, accepted_terms={
        "version": PUBLIC_TRIAL_TERMS,
        "trial_days": 30, "max_members": 6, "card_required": False,
        "automatic_charge": False, "following_monthly_offer_inr": "1499.00",
        "paid_continuation_requires_separate_consent": True,
    })
