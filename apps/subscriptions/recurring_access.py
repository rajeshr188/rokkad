"""Explicit application of started future-payment holds; never a charge or timer."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.utils import timezone

from apps.orgs.models import Company
from .billing import transition_subscription
from .checkout import require_billing_owner
from .models import (BillingResolution, Invoice, Payment, RecurringAccessResolution, RecurringAgreement,
                     RecurringAgreementEvent, RecurringCycle, Subscription, SubscriptionEvent)
from .recurring import provider_test_mode, verify_agreement_observation
from .recurring_cycles import _facts
from .razorpay_service import RazorpayService
from .recovery import _validate_refund
from .services import ensure_entitlements_for_subscription, get_workspace_member_usage


def _active_owner(workspace, actor):
    current = get_user_model().objects.filter(pk=actor.pk, is_active=True).first()
    if current is None:
        raise PermissionDenied("An active billing owner is required.")
    require_billing_owner(workspace=workspace, actor=current)
    return current


def apply_held_period(*, workspace, actor, cycle_id, revision, reason):
    """Caller supplies explicit Workspace context and the reviewed subscription revision."""
    actor = _active_owner(workspace, actor)
    mode = provider_test_mode()
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("A review reason of up to 1000 characters is required.")
    cycle = RecurringCycle.objects.select_related("agreement__binding", "invoice").filter(
        pk=cycle_id, agreement__workspace=workspace, agreement__binding__mode=mode).first()
    if cycle is None:
        raise ValidationError("A known held cycle in this Workspace and provider mode is required.")
    existing = RecurringAccessResolution.objects.filter(cycle=cycle).first()
    if existing:
        return existing  # A retry reports history, never reactivates access after later changes/refunds.
    if (cycle.access_action != "review" or
            cycle.invoice.checkout_snapshot.get("access_review_reason") != "future_period"):
        raise ValidationError("Only a recorded future-period hold can be applied here.")
    # Provider reads do not assert local eligibility; recheck local state under the Company lock.
    evidence, provider_payment, start, end, _ = _facts(cycle.agreement, cycle.provider_invoice_id)
    if (evidence != cycle.evidence or provider_payment["status"] != "captured" or
            provider_payment["amount_refunded"]):
        raise ValidationError("The saved period needs matching captured, unrefunded provider evidence.")
    with transaction.atomic():
        company = Company.all_objects.select_for_update().get(pk=workspace.pk)
        actor = _active_owner(company, actor)
        agreement = RecurringAgreement.objects.select_for_update().select_related("binding").get(pk=cycle.agreement_id)
        invoice = Invoice.objects.select_for_update().get(pk=cycle.invoice_id)
        subscription = Subscription.objects.select_for_update().get(pk=invoice.subscription_id)
        existing = RecurringAccessResolution.objects.filter(cycle=cycle).first()
        if existing:
            return existing
        now = timezone.now()
        if not start <= now < end:
            raise ValidationError("The held period must have started and must not have expired.")
        if revision != subscription.updated_at.isoformat():
            raise ValidationError("Subscription changed during review. Reload and review its current terms.")
        if (company.lifecycle_state != Company.LifecycleState.ACTIVE or agreement.state != "verified" or
                agreement.closed_at is not None or
                RecurringAgreement.objects.filter(workspace=company, closed_at__isnull=True).exclude(pk=agreement.pk).exists()):
            raise ValidationError("An active Workspace and its current verified agreement are required.")
        snapshot = agreement.binding.snapshot
        if (subscription.company_id != company.pk or subscription.plan_id != snapshot["plan_id"] or
                subscription.status not in {"active", "past_due", "expired"} or
                subscription.end_date > start or
                (subscription.trial_end_date and subscription.trial_end_date > start)):
            raise ValidationError("Current subscription terms conflict with this held period; separate review is required.")
        payment = Payment.objects.select_for_update().filter(invoice=invoice,
            razorpay_payment_id=evidence["payment_id"]).first()
        if (invoice.status != "paid" or not payment or payment.status != "captured" or
                payment.refund_amount or payment.refunds.exists()):
            raise ValidationError("A locally recorded, unrefunded captured payment is required.")
        seats = next(item for item in snapshot["entitlements"] if item["feature_code"] == "workspace.max_members")
        if get_workspace_member_usage(workspace=company, include_pending_invitations=True) > int(seats["value"]):
            raise ValidationError("Workspace members and pending invitations exceed this offer's seats.")
        before = {"status": subscription.status, "end_date": subscription.end_date.isoformat(),
                  "plan_id": subscription.plan_id, "revision": revision}
        subscription.end_date = end
        subscription.save(update_fields=["end_date", "updated_at"])
        subscription, _ = transition_subscription(subscription=subscription, target_status="active",
            event_type="recurring.held_period_applied", payload={"cycle_id": cycle.pk, "actor_id": actor.pk})
        ensure_entitlements_for_subscription(subscription, projection=snapshot["entitlements"])
        resolution = RecurringAccessResolution.objects.create(cycle=cycle, actor=actor, reason=reason.strip(),
            evidence={"before": before, "after": {"status": subscription.status,
                "end_date": end.isoformat(), "plan_id": subscription.plan_id,
                "revision": subscription.updated_at.isoformat()}, "provider": evidence,
                "verified_at": now.isoformat(), "provider_payment_status": provider_payment["status"],
                "provider_amount_refunded": provider_payment["amount_refunded"]})
        payload = {"resolution_id": resolution.pk, "cycle_id": cycle.pk, "invoice_id": invoice.pk,
                   "actor_id": actor.pk, "reason": reason.strip()}
        SubscriptionEvent.objects.create(subscription=subscription, event_type="recurring.access_resolved", payload=payload)
        RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor,
            event_type="cycle.access_applied", detail=payload)
        return resolution


def resolve_recurring_refund(*, workspace, actor, invoice_id, action, reason, revision):
    """Review a recorded full refund; never issue money or cancel/release a mandate."""
    actor = _active_owner(workspace, actor)
    mode = provider_test_mode()
    if action not in {"retain_access", "end_access"}:
        raise ValidationError("Recurring refunds support retaining access or ending the current refunded term.")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("A review reason of up to 1000 characters is required.")
    cycle = RecurringCycle.objects.select_related("agreement__binding", "invoice__subscription").filter(
        invoice_id=invoice_id, agreement__workspace=workspace, agreement__binding__mode=mode).first()
    if cycle is None:
        raise ValidationError("A known recurring invoice in this Workspace and provider mode is required.")
    existing = BillingResolution.objects.filter(invoice_id=invoice_id).first()
    if existing:
        if existing.action != action:
            raise ValidationError("This invoice already has a different final decision.")
        return existing
    evidence, provider_payment, start, end, _ = _facts(cycle.agreement, cycle.provider_invoice_id)
    if (evidence != cycle.evidence or provider_payment["status"] != "refunded" or
            provider_payment["amount_refunded"] != evidence["amount"]):
        raise ValidationError("Fresh provider evidence of the exact fully refunded cycle is required.")
    provider = RazorpayService.get_subscription(cycle.agreement.provider_subscription_id)
    verify_agreement_observation(cycle.agreement, provider)
    payment = Payment.objects.filter(invoice_id=invoice_id, razorpay_payment_id=evidence["payment_id"]).first()
    refunds = list(payment.refunds.order_by("pk")) if payment else []
    verified_refunds = []
    for refund in refunds:
        remote = RazorpayService.get_refund(refund.provider_refund_id)
        _validate_refund(cycle.invoice, provider_payment, remote, refund.provider_refund_id)
        if remote["amount"] != int(refund.amount * 100):
            raise ValidationError("Provider refund differs from recorded refund evidence.")
        verified_refunds.append(refund.provider_refund_id)
    with transaction.atomic():
        company = Company.all_objects.select_for_update().get(pk=workspace.pk)
        actor = _active_owner(company, actor)
        agreement = RecurringAgreement.objects.select_for_update().get(pk=cycle.agreement_id)
        verify_agreement_observation(agreement, provider)
        invoice = Invoice.objects.select_for_update().get(pk=invoice_id)
        subscription = Subscription.objects.select_for_update().get(pk=invoice.subscription_id)
        existing = BillingResolution.objects.filter(invoice=invoice).first()
        if existing:
            if existing.action != action:
                raise ValidationError("This invoice already has a different final decision.")
            return existing
        if revision != subscription.updated_at.isoformat():
            raise ValidationError("Subscription changed during review. Reload and review its current terms.")
        payment = Payment.objects.select_for_update().filter(invoice=invoice,
            razorpay_payment_id=evidence["payment_id"]).first()
        if (invoice.status != "paid" or not payment or payment.status != "refunded" or
                payment.refund_amount != payment.amount or payment.amount != invoice.total_amount or
                payment.refunds.aggregate(total=Sum("amount"))["total"] != payment.amount or
                list(payment.refunds.order_by("pk").values_list("provider_refund_id", flat=True)) != verified_refunds):
            raise ValidationError("Matching recorded full-refund evidence is required before reviewing access.")
        before = {"status": subscription.status, "end_date": subscription.end_date.isoformat(),
                  "plan_id": subscription.plan_id, "revision": revision}
        if action == "end_access":
            if provider["status"] not in {"cancelled", "completed", "expired"}:
                raise ValidationError("Stop future renewals and verify the ended agreement before ending refunded access.")
            latest = SubscriptionEvent.objects.filter(subscription=subscription).filter(
                Q(event_type="recurring.cycle_paid", payload__access_action="applied") |
                Q(event_type__in=["checkout.completed", "recurring.access_resolved"])
            ).order_by("-created_at", "-pk").first()
            if (not latest or latest.payload.get("cycle_id") != cycle.pk or
                    subscription.plan_id != cycle.agreement.binding.plan_id or subscription.status != "active" or
                    not start <= timezone.now() < end or subscription.end_date != end or
                    RecurringCycle.objects.filter(invoice__subscription=subscription, period_end__gt=timezone.now())
                    .exclude(pk=cycle.pk).filter(invoice__payment__refund_amount__lt=F("invoice__payment__amount")).exists()):
                raise ValidationError("Only the current applied refunded term can end; other paid periods require separate review.")
            subscription, _ = transition_subscription(subscription=subscription, target_status="cancelled",
                event_type="refund.access_ended", payload={"invoice_id": invoice.pk, "cycle_id": cycle.pk,
                                                          "actor_id": actor.pk, "reason": reason.strip()})
        resolution = BillingResolution.objects.create(invoice=invoice, action=action, actor=actor, reason=reason.strip(),
            evidence={"before": before, "after_status": subscription.status, "reviewed_revision": revision,
                      "provider": evidence, "provider_status": provider["status"],
                      "provider_amount_refunded": provider_payment["amount_refunded"],
                      "refund_ids": verified_refunds, "cycle_id": cycle.pk})
        audit = {"resolution_id": resolution.pk, "invoice_id": invoice.pk, "cycle_id": cycle.pk,
                 "action": action, "actor_id": actor.pk, "reason": reason.strip()}
        SubscriptionEvent.objects.create(subscription=subscription, event_type="billing.review.resolved", payload=audit)
        RecurringAgreementEvent.objects.create(agreement=agreement, actor=actor, event_type="refund.access_reviewed", detail=audit)
        return resolution
