"""Provider transport only; billing decisions live in checkout services."""
import hashlib
import hmac

import razorpay
from django.conf import settings


class BillingProviderError(Exception):
    pass


def client():
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class RazorpayService:
    @staticmethod
    def create_order(*, amount, currency, receipt, workspace_id):
        try:
            return client().order.create(data={
                "amount": amount, "currency": currency, "receipt": receipt,
                "notes": {"workspace_id": str(workspace_id)},
            })
        except Exception as exc:
            raise BillingProviderError("Payment provider could not create the order. Contact support to reconcile the attempt before retrying.") from exc

    @staticmethod
    def verify_payment_signature(razorpay_order_id, razorpay_payment_id, signature):
        if not all(isinstance(value, str) and value for value in (razorpay_order_id, razorpay_payment_id, signature)):
            return False
        if not settings.RAZORPAY_KEY_SECRET or not signature.isascii():
            return False
        digest = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(),
                          f"{razorpay_order_id}|{razorpay_payment_id}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    @staticmethod
    def get_payment_status(payment_id):
        try:
            return client().payment.fetch(payment_id)
        except Exception as exc:
            raise BillingProviderError("Payment verification is temporarily unavailable. Retry the same payment confirmation.") from exc

    @staticmethod
    def get_refund(refund_id):
        try:
            return client().refund.fetch(refund_id)
        except Exception as exc:
            raise BillingProviderError("Refund verification is temporarily unavailable.") from exc

    @staticmethod
    def handle_payment_webhook(event_data):
        from .checkout import handle_provider_event
        return handle_provider_event(event_data)
