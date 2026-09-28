"""Explicit provider mode; credentials never choose an environment implicitly."""
from django.conf import settings
from django.core.exceptions import ValidationError


def provider_mode():
    mode = getattr(settings, "BILLING_PROVIDER_MODE", "disabled")
    if mode not in {"test", "live"}:
        raise ValidationError("Billing provider is disabled or its mode is invalid.")
    key = getattr(settings, "RAZORPAY_KEY_ID", "")
    secret = getattr(settings, "RAZORPAY_KEY_SECRET", "")
    if (not isinstance(key, str) or not key.startswith(f"rzp_{mode}_") or
            not key[len(f"rzp_{mode}_"):] or not isinstance(secret, str) or not secret.strip()):
        raise ValidationError("Billing credentials do not match the configured provider mode.")
    return mode


def invoice_mode(invoice):
    """Never relabel historical evidence from today's process credentials."""
    if invoice.checkout_snapshot.get("kind") == "recurring":
        from .models import RecurringCycle
        return RecurringCycle.objects.filter(invoice=invoice).values_list("agreement__binding__mode", flat=True).first()
    return invoice.checkout_snapshot.get("provider_mode")


def require_invoice_mode(invoice):
    mode = provider_mode()
    recorded = invoice_mode(invoice)
    # Older one-off Test Mode fixtures have no recorded mode. Preserve recovery
    # only in Test Mode; never silently reinterpret them as live purchases.
    if recorded != mode and not (recorded is None and mode == "test"):
        raise ValidationError("Invoice provider mode needs reconciliation before payment processing.")
    return mode
