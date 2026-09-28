"""Owner actions on mode-matched agreements; mandate state is not access.

Cancellation intent is append-only and committed before its single provider POST.
An on-commit callback attempts delivery; an explicit command recovers interrupted
delivery. A dispatched request is only fetched again, never automatically reposted.
"""
import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.orgs.models import Company
from .models import RecurringAgreement, RecurringAgreementEvent, Subscription
from .services import get_workspace_member_usage
from .razorpay_service import BillingProviderError, RazorpayService
from .recurring import (_identity, _locked_owner, _outside_transaction, _creation_mode,
                        _verify_plan, recurring_provider_mode, verify_agreement, verify_agreement_observation)

logger = logging.getLogger(__name__)
TERMINAL = {"cancelled", "completed", "expired"}


def owned_agreement(*, workspace, actor, agreement_id):
    mode = recurring_provider_mode()
    _locked_owner(workspace.pk, actor)
    agreement = RecurringAgreement.objects.select_for_update().select_related("binding").filter(
        pk=agreement_id, workspace=workspace, binding__mode=mode).first()
    if not agreement or agreement.state != "verified" or not agreement.provider_subscription_id:
        raise ValidationError("A verified agreement in this Workspace is required. Contact support to reconcile its creation.")
    return agreement


def _observe(agreement, entity, actor, event_type):
    verify_agreement_observation(agreement, entity)
    if not agreement.closed_at:
        agreement.provider_status = entity["status"]
        agreement.verified_at = timezone.now()
        agreement.save(update_fields=["provider_status", "verified_at"])
    RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor, event_type=event_type,
        detail={"provider_status": entity["status"]})
    return agreement


def refresh_agreement(*, workspace, actor, agreement_id):
    with workspace_context(workspace.pk):
        agreement = owned_agreement(workspace=workspace, actor=actor, agreement_id=agreement_id)
    entity = RazorpayService.get_subscription(agreement.provider_subscription_id)
    with workspace_context(workspace.pk):
        agreement = owned_agreement(workspace=workspace, actor=actor, agreement_id=agreement_id)
        return _observe(agreement, entity, actor, "owner.refreshed")


def authorization_options(*, workspace, actor, agreement_id):
    mode = _creation_mode()
    agreement = refresh_agreement(workspace=workspace, actor=actor, agreement_id=agreement_id)
    with workspace_context(workspace.pk):
        agreement = owned_agreement(workspace=workspace, actor=actor, agreement_id=agreement_id)
        if (agreement.closed_at or agreement.provider_status != "created" or
                agreement.events.filter(event_type="cancel.requested").exists()):
            raise ValidationError("This agreement cannot start another authorization. Refresh its status or contact support.")
        if mode == "live":
            from .seller import require_live_offer
            require_live_offer(agreement.binding.snapshot)
        start_at = agreement.request_snapshot.get("start_at")
        if start_at is not None and mode == "live":
            raise ValidationError("Scheduled live starts require a separately reviewed transition workflow.")
        if start_at is not None and start_at <= timezone.now().timestamp():
            raise ValidationError("The scheduled start has passed. Contact support to review this agreement before authorization.")
        workspace.refresh_from_db(fields=["lifecycle_state"])
        if workspace.lifecycle_state != Company.LifecycleState.ACTIVE:
            raise ValidationError("Only an active Workspace can authorize recurring payments.")
        seats = next(x for x in agreement.binding.snapshot["entitlements"] if x["feature_code"] == "workspace.max_members")
        if get_workspace_member_usage(workspace=workspace, include_pending_invitations=True) > int(seats["value"]):
            raise ValidationError("Members and pending invitations exceed this agreement's seats.")
        subscription = Subscription.objects.filter(company=workspace).first()
        if subscription and ((subscription.status == "active" and subscription.end_date > timezone.now()) or
                (subscription.status == "trial" and subscription.trial_end_date and subscription.trial_end_date > timezone.now())):
            raise ValidationError("Existing paid or trial time requires a scheduled transition review.")
        _verify_plan(RazorpayService.get_plan(agreement.binding.provider_plan_id),
                     agreement.binding.provider_plan_id, agreement.binding.snapshot)
        return {"key": settings.RAZORPAY_KEY_ID, "subscription_id": agreement.provider_subscription_id,
                "name": "Rokkad TEST" if mode == "test" else "Rokkad",
                "description": agreement.binding.snapshot["plan_name"]}


def confirm_authorization(*, workspace, actor, agreement_id, payment_id, signature):
    # Existing callbacks remain verifiable when new authorizations are disabled.
    with workspace_context(workspace.pk):
        agreement = owned_agreement(workspace=workspace, actor=actor, agreement_id=agreement_id)
        payment_id = _identity(payment_id, "pay_")
        if not RazorpayService.verify_subscription_signature(agreement.provider_subscription_id, payment_id, signature):
            raise ValidationError("Authorization signature is invalid.")
        entity = RazorpayService.get_subscription(agreement.provider_subscription_id)
        verify_agreement(agreement, entity)
        if not agreement.events.filter(event_type="authorization.verified", detail__payment_id=payment_id).exists():
            _observe(agreement, entity, actor, "authorization.observed")
            RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor,
                event_type="authorization.verified", detail={"payment_id": payment_id})
        # No invoice, paid time or receipt from an authentication transaction.
        return agreement


def request_cancellation(*, workspace, actor, agreement_id):
    with workspace_context(workspace.pk):
        agreement = owned_agreement(workspace=workspace, actor=actor, agreement_id=agreement_id)
        existing = agreement.events.filter(event_type="cancel.requested").first()
        if existing:
            return existing
        if agreement.closed_at or agreement.provider_status in TERMINAL:
            raise ValidationError("This agreement has already ended. Refresh status to verify it.")
        event = RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor,
            event_type="cancel.requested", detail={"cancel_at_cycle_end": False})
        transaction.on_commit(lambda: _deliver_cancellation(event.pk))
        return event


def _deliver_cancellation(request_id):
    try:
        process_cancellation(request_id=request_id)
    except Exception:
        # Do not leak SDK bodies/credentials; durable intent remains for recovery.
        logger.warning("Recurring cancellation %s needs reconciliation", request_id)


def process_cancellation(*, request_id):
    """Outside request transaction. At most one POST, even after crashes/timeouts."""
    _outside_transaction()
    recurring_provider_mode()
    request = RecurringAgreementEvent.objects.select_related("agreement__workspace").get(
        pk=request_id, event_type="cancel.requested")
    workspace = request.agreement.workspace
    actor = get_user_model().objects.get(pk=request.actor_id)
    with workspace_context(workspace.pk):
        agreement = owned_agreement(workspace=workspace, actor=actor, agreement_id=request.agreement_id)
        if agreement.events.filter(event_type="cancel.dispatched").exists():
            dispatched = True
        else:
            dispatched = False
            RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor,
                event_type="cancel.dispatched", detail={"request_id": request.pk})
    # The claim is committed. Another delivery can fetch, but cannot POST again.
    try:
        entity = RazorpayService.get_subscription(agreement.provider_subscription_id)
        verify_agreement(agreement, entity)
        if entity["status"] not in TERMINAL and not dispatched:
            # Permission was rechecked when committing the dispatch claim.
            response = RazorpayService.cancel_subscription(agreement.provider_subscription_id)
            verify_agreement(agreement, response)
            entity = RazorpayService.get_subscription(agreement.provider_subscription_id)
            verify_agreement(agreement, entity)
        with workspace_context(workspace.pk):
            agreement = owned_agreement(workspace=workspace, actor=actor, agreement_id=agreement.pk)
            event_type = "cancel.confirmed" if entity["status"] in TERMINAL else "cancel.unknown"
            _observe(agreement, entity, actor, event_type)
        return agreement
    except (BillingProviderError, ValidationError):
        with workspace_context(workspace.pk):
            _locked_owner(workspace.pk, actor)
            RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor,
                event_type="cancel.unknown", detail={"request_id": request.pk})
        raise
