"""Provider transport only; billing decisions live in checkout services."""
import hashlib
import hmac

import razorpay
from django.conf import settings
from django.core.exceptions import ValidationError
from .provider_configuration import provider_mode


class BillingProviderError(Exception):
    pass


def client():
    provider_mode()
    return razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


class RazorpayService:
    @staticmethod
    def get_subscription_invoices(subscription_id, *, skip=0, count=100):
        try:
            return client().invoice.all({"subscription_id": subscription_id, "skip": skip, "count": count},
                                        timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Provider invoice listing is unavailable.") from exc

    @staticmethod
    def get_order_payments(order_id):
        try:
            return client().order.payments(order_id, timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Provider order payment verification is unavailable.") from exc

    @staticmethod
    def cancel_subscription(subscription_id):
        try:
            # Stop the mandate now. Rokkad preserves the independently paid period.
            return client().subscription.cancel(subscription_id, data={"cancel_at_cycle_end": False},
                                                timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Cancellation outcome is unknown. Refresh status before any further action.") from exc

    @staticmethod
    def verify_subscription_signature(subscription_id, payment_id, signature):
        try:
            provider_mode()
        except ValidationError:
            return False
        if not all(isinstance(value, str) and value for value in (subscription_id, payment_id, signature)):
            return False
        if not settings.RAZORPAY_KEY_SECRET or not signature.isascii():
            return False
        digest = hmac.new(settings.RAZORPAY_KEY_SECRET.encode(),
                          f"{payment_id}|{subscription_id}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, signature)

    @staticmethod
    def get_invoice(invoice_id):
        try:
            return client().invoice.fetch(invoice_id, timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Provider invoice verification is unavailable.") from exc

    @staticmethod
    def get_plan(plan_id):
        try:
            return client().plan.fetch(plan_id, timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Provider plan verification is unavailable.") from exc

    @staticmethod
    def create_subscription(payload):
        try:
            # No retry: an uncertain POST must be reconciled against the saved attempt.
            return client().subscription.create(data=payload, timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Agreement creation outcome is unknown. Reconcile this attempt before retrying.") from exc

    @staticmethod
    def get_subscription(subscription_id):
        try:
            return client().subscription.fetch(subscription_id, timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Provider agreement verification is unavailable.") from exc

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
        try:
            provider_mode()
        except ValidationError:
            return False
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
            return client().payment.fetch(payment_id, timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Payment verification is temporarily unavailable. Retry the same payment confirmation.") from exc

    @staticmethod
    def get_refund(refund_id):
        try:
            return client().refund.fetch(refund_id, timeout=20, allow_redirects=False)
        except Exception as exc:
            raise BillingProviderError("Refund verification is temporarily unavailable.") from exc

    @staticmethod
    def handle_payment_webhook(event_data):
        from .checkout import handle_provider_event
        return handle_provider_event(event_data)
