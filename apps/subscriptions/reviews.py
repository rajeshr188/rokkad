"""Explicit resolutions; never force an old checkout onto newer commercial terms."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.orgs.models import Company
from .billing import transition_subscription
from .checkout import require_billing_owner
from .models import BillingResolution, Invoice, Payment, Subscription, SubscriptionEvent
from .razorpay_service import RazorpayService
from .recovery import _identifier, _record_refund, _validate_payment, _validate_refund


def resolve_billing_review(*, workspace, actor, invoice_id, action, reason, revision,
                           payment_id=None, refund_ids=()):
    require_billing_owner(workspace=workspace, actor=actor)
    if action not in ("retain_access", "end_access", "returned_payment"):
        raise ValidationError("Choose a supported review decision.")
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("A review reason of up to 1000 characters is required.")
    invoice = Invoice.objects.select_related("subscription").filter(pk=invoice_id, subscription__company=workspace).first()
    if not invoice or not invoice.checkout_snapshot:
        raise ValidationError("A known Workspace checkout is required.")
    payment, refunds = None, []
    if action == "returned_payment":
        _identifier(payment_id)
        if not isinstance(refund_ids, (list, tuple)) or not 1 <= len(refund_ids) <= 20 or len(set(refund_ids)) != len(refund_ids):
            raise ValidationError("Provide 1 to 20 distinct processed refund IDs covering the full payment.")
        payment = RazorpayService.get_payment_status(payment_id)
        _validate_payment(invoice, payment, payment_id)
        for refund_id in refund_ids:
            refund = RazorpayService.get_refund(_identifier(refund_id))
            _validate_refund(invoice, payment, refund, refund_id)
            refunds.append(refund)
        if sum(refund["amount"] for refund in refunds) != invoice.checkout_snapshot["amount"]:
            raise ValidationError("Processed refunds must cover this payment in full.")
    with transaction.atomic():
        company = Company.all_objects.select_for_update().get(pk=workspace.pk)
        require_billing_owner(workspace=company, actor=actor)
        invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
        subscription = Subscription.objects.select_for_update().get(pk=invoice.subscription_id)
        existing = BillingResolution.objects.filter(invoice=invoice).first()
        if existing:
            if existing.action != action or (action == "returned_payment" and existing.evidence.get("payment_id") != payment_id):
                raise ValidationError("This invoice already has a different final decision.")
            return existing
        if revision != subscription.updated_at.isoformat():
            raise ValidationError("Subscription changed during review. Reload and review its current terms.")
        before = {"status": subscription.status, "end_date": subscription.end_date.isoformat(), "plan_id": subscription.plan_id}
        if action == "returned_payment":
            if invoice.status != "issued" or invoice.checkout_snapshot["subscription_revision"] == revision:
                raise ValidationError("This resolution is only for an unpaid stale checkout.")
            if Payment.objects.filter(invoice=invoice).exists() or Payment.objects.filter(razorpay_payment_id=payment_id).exists():
                raise ValidationError("Payment is already recorded; review its existing invoice.")
            Payment.objects.create(invoice=invoice, razorpay_payment_id=payment_id,
                                   razorpay_order_id=invoice.razorpay_order_id, amount=invoice.total_amount,
                                   status="captured", payment_date=timezone.now())
            invoice.status = "paid"
            invoice.paid_at = timezone.now()
            invoice.razorpay_payment_id = payment_id
            invoice.save(update_fields=["status", "paid_at", "razorpay_payment_id", "updated_at"])
            for refund in refunds:
                _record_refund(invoice_id=invoice.pk, payment=payment, refund=refund, actor_id=actor.pk, reason=reason.strip())
        else:
            recorded = Payment.objects.select_for_update().filter(invoice=invoice, status="refunded").first()
            if (not recorded or recorded.refund_amount != recorded.amount
                    or recorded.refunds.aggregate(total=Sum("amount"))["total"] != recorded.amount):
                raise ValidationError("A recorded full refund is required before reviewing access.")
            if action == "end_access":
                latest = SubscriptionEvent.objects.filter(subscription=subscription, event_type="checkout.completed").order_by("-created_at", "-pk").first()
                payload = latest.payload if latest else {}
                start = parse_datetime(payload.get("period_start", ""))
                if (payload.get("invoice_id") != invoice.pk or payload.get("period_end") != subscription.end_date.isoformat()
                        or payload.get("plan_id") != subscription.plan_id or not start or start > timezone.now()
                        or subscription.status != "active" or subscription.end_date <= timezone.now()):
                    raise ValidationError("Only the current, started refunded term can end here; newer or future paid terms require separate review.")
                subscription, _ = transition_subscription(subscription=subscription, target_status="cancelled",
                    event_type="refund.access_ended", payload={"invoice_id": invoice.pk, "actor_id": actor.pk, "reason": reason.strip()})
        evidence = {"before": before, "after_status": subscription.status,
                    "reviewed_revision": revision, "payment_id": payment_id,
                    "provider_payment": {key: payment.get(key) for key in ("id", "order_id", "amount", "currency", "status", "created_at")} if payment else {},
                    "refund_ids": list(refund_ids) if action == "returned_payment" else []}
        resolution = BillingResolution.objects.create(invoice=invoice, action=action, actor=actor,
                                                      reason=reason.strip(), evidence=evidence)
        SubscriptionEvent.objects.create(subscription=subscription, event_type="billing.review.resolved", payload={
            "resolution_id": resolution.pk, "invoice_id": invoice.pk, "action": action,
            "actor_id": actor.pk, "reason": reason.strip(),
        })
        return resolution
