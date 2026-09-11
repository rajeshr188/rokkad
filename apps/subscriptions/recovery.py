"""Verify provider facts before reconciling known Workspace checkout records.

These operations fetch evidence; they never initiate a charge or refund.
"""
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum

from apps.orgs.models import Company
from .checkout import _apply_capture, require_billing_owner
from .models import Invoice, Payment, PaymentRefund, SubscriptionEvent
from .razorpay_service import RazorpayService


def _identifier(value):
    if not isinstance(value, str) or not value or len(value) > 255:
        raise ValidationError("A valid provider identifier is required.")
    return value


def _validate_payment(invoice, payment, payment_id):
    snapshot = invoice.checkout_snapshot
    if (not snapshot or not isinstance(payment, dict) or payment.get("id") != payment_id
            or payment.get("order_id") != invoice.razorpay_order_id
            or snapshot.get("workspace_id") != invoice.subscription.company_id
            or type(payment.get("amount")) is not int
            or payment["amount"] != snapshot["amount"]
            or payment.get("currency") != snapshot["currency"]):
        raise ValidationError("Provider payment does not match this Workspace invoice.")


def _validate_refund(invoice, payment, refund, refund_id):
    _validate_payment(invoice, payment, payment.get("id"))
    if (not isinstance(refund, dict) or refund.get("id") != refund_id
            or refund.get("payment_id") != payment["id"]
            or refund.get("status") != "processed"
            or refund.get("currency") != invoice.checkout_snapshot["currency"]
            or type(refund.get("amount")) is not int
            or not 0 < refund["amount"] <= payment["amount"]
            or payment.get("status") not in ("captured", "refunded")):
        raise ValidationError("Refund must be processed for this exact payment and currency.")


def reconcile_payment(*, workspace, actor, invoice_id, payment_id, reason, refund_id=None, apply=False):
    require_billing_owner(workspace=workspace, actor=actor)
    _identifier(payment_id)
    if refund_id:
        _identifier(refund_id)
    if not isinstance(reason, str) or not reason.strip() or len(reason) > 1000:
        raise ValidationError("Provide a review reason (up to 1000 characters).")
    invoice = Invoice.objects.select_related("subscription").filter(
        pk=invoice_id, subscription__company=workspace,
    ).first()
    if not invoice or not invoice.checkout_snapshot or not invoice.razorpay_order_id:
        raise ValidationError("A known checkout invoice in this Workspace is required.")
    payment = RazorpayService.get_payment_status(payment_id)
    _validate_payment(invoice, payment, payment_id)
    refund = RazorpayService.get_refund(refund_id) if refund_id else None
    if refund_id:
        _validate_refund(invoice, payment, refund, refund_id)
    elif payment.get("status") != "captured" or payment.get("amount_refunded", 0):
        raise ValidationError("A captured, unrefunded payment is required; provide the processed refund ID to reconcile a refund.")
    summary = {"invoice_id": invoice.pk, "payment_id": payment_id, "refund_id": refund_id,
               "provider_status": payment["status"], "applied": False}
    if not apply:
        return summary
    with transaction.atomic():
        locked_workspace = Company.all_objects.select_for_update().get(pk=workspace.pk)
        require_billing_owner(workspace=locked_workspace, actor=actor)
        if refund_id:
            _record_refund(invoice_id=invoice.pk, payment=payment, refund=refund,
                           actor_id=actor.pk, reason=reason.strip())
        else:
            _apply_capture(invoice_id=invoice.pk, payment=payment, actor=actor, workspace=locked_workspace)
        SubscriptionEvent.objects.create(subscription_id=invoice.subscription_id, event_type="payment.reconciled", payload={
            "invoice_id": invoice.pk, "payment_id": payment_id, "refund_id": refund_id,
            "actor_id": actor.pk, "reason": reason.strip(),
        })
    return {**summary, "applied": True}


@transaction.atomic
def _record_refund(*, invoice_id, payment, refund, actor_id=None, reason="Provider processed refund"):
    initial = Invoice.objects.select_related("subscription").get(pk=invoice_id)
    Company.all_objects.select_for_update().get(pk=initial.subscription.company_id)
    invoice = Invoice.objects.select_for_update().select_related("subscription").get(pk=invoice_id)
    _validate_refund(invoice, payment, refund, _identifier(refund.get("id")))
    recorded = Payment.objects.select_for_update().filter(
        invoice=invoice, razorpay_payment_id=payment["id"], razorpay_order_id=invoice.razorpay_order_id,
    ).first()
    if not recorded or invoice.status != "paid" or recorded.status not in ("captured", "refunded"):
        raise ValidationError("Refund has no recorded paid checkout; resolve capture history first.")
    amount = Decimal(refund["amount"]) / 100
    existing = PaymentRefund.objects.filter(provider_refund_id=refund["id"]).first()
    if existing:
        if existing.payment_id != recorded.pk or existing.amount != amount or existing.evidence["currency"] != refund["currency"]:
            raise ValidationError("Refund identity conflicts with saved evidence.")
        return existing
    total = (recorded.refunds.aggregate(total=Sum("amount"))["total"] or Decimal("0")) + amount
    if total > recorded.amount:
        raise ValidationError("Processed refunds exceed the recorded payment.")
    evidence = {key: refund.get(key) for key in ("id", "payment_id", "amount", "currency", "status", "created_at")}
    row = PaymentRefund.objects.create(payment=recorded, provider_refund_id=refund["id"], amount=amount, evidence=evidence)
    recorded.refund_amount = total
    recorded.status = "refunded" if total == recorded.amount else "captured"
    recorded.save(update_fields=["refund_amount", "status", "updated_at"])
    SubscriptionEvent.objects.create(subscription_id=invoice.subscription_id, event_type="refund.recorded", payload={
        "invoice_id": invoice.pk, "payment_id": payment["id"], "refund_id": refund["id"],
        "amount": str(amount), "total_refunded": str(total), "actor_id": actor_id,
        "reason": reason, "access_action": "review_required" if total == recorded.amount else "retained",
    })
    # Preserve paid invoice/term evidence. Refund access policy is a separate decision.
    return row


def process_refund_webhook(event_data):
    entity = event_data.get("payload", {}).get("refund", {}).get("entity", {})
    refund_id = _identifier(entity.get("id"))
    payment_id = _identifier(entity.get("payment_id"))
    recorded = Payment.objects.select_related("invoice").filter(razorpay_payment_id=payment_id).first()
    if not recorded:
        raise ValidationError("Refund payment needs capture reconciliation first.")
    refund = RazorpayService.get_refund(refund_id)
    payment = RazorpayService.get_payment_status(payment_id)
    _validate_payment(recorded.invoice, payment, payment_id)
    _validate_refund(recorded.invoice, payment, refund, refund_id)
    _record_refund(invoice_id=recorded.invoice_id, payment=payment, refund=refund)
    return True
