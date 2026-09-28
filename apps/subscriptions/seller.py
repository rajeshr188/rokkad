"""Reviewed live issuer configuration and frozen commercial-invoice wording.

Only the unregistered-supplier pilot is supported. This does not determine whether
the operator is legally required to register for GST.
"""
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.exceptions import ValidationError

NO_GST_NOTE = "GST not charged - supplier not registered under GST."


def billing_tax_rate():
    try:
        rate = Decimal(str(settings.BILLING_TAX_RATE))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Configure an explicit billing tax rate.") from None
    if not rate.is_finite() or not 0 <= rate <= 100:
        raise ValidationError("Configure a valid billing tax rate between 0 and 100.")
    return rate


def validate_seller(seller):
    if not isinstance(seller, dict) or set(seller) != {"name", "address", "tax_status"}:
        raise ValidationError("The saved billing seller needs review.")
    for field, limit in (("name", 160), ("address", 1000)):
        value = seller[field]
        if (not isinstance(value, str) or not value.strip() or len(value) > limit or
                any(ord(char) < 32 and not (field == "address" and char == "\n") for char in value)):
            raise ValidationError("Configure a valid billing seller name and address.")
    if seller["tax_status"] != "unregistered":
        raise ValidationError("Live billing currently supports only the reviewed unregistered-supplier pilot.")
    return seller


def live_seller():
    seller = validate_seller({"name": settings.BILLING_SELLER_NAME,
                              "address": settings.BILLING_SELLER_ADDRESS,
                              "tax_status": settings.BILLING_SELLER_TAX_STATUS})
    if billing_tax_rate() != 0:
        raise ValidationError("An unregistered billing seller must have an explicit zero tax rate.")
    return {key: value.strip() for key, value in seller.items()}


def require_live_offer(snapshot):
    """New authorization requires the reviewed issuer; recovery ignores current settings."""
    seller = live_seller()
    try:
        zero_tax = Decimal(str(snapshot.get("tax_rate", "-1"))) == 0
    except (InvalidOperation, ValueError, TypeError):
        zero_tax = False
    if snapshot.get("seller") != seller or not zero_tax:
        raise ValidationError("The live offer's seller or tax treatment needs a new catalog review.")


def invoice_seller(invoice):
    """Historical invoices never acquire today's seller or tax interpretation."""
    if "seller" not in invoice.checkout_snapshot:
        return None
    seller = validate_seller(invoice.checkout_snapshot["seller"])
    if invoice.gst_rate != 0 or invoice.gst_amount != 0:
        raise ValidationError("The invoice seller and recorded tax conflict; review the saved evidence.")
    return seller
