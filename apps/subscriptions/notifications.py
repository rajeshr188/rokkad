"""Persist independent receipt intents inside the payment transaction."""
from django.db import transaction
from .models import Invoice


@transaction.atomic
def send_checkout_receipt(invoice_id, *, capture_whatsapp=False):
    from apps.platform_mail.services import enqueue_receipt
    invoice = Invoice.objects.select_related("subscription__company").get(pk=invoice_id)
    email = enqueue_receipt(invoice)
    if capture_whatsapp:
        from apps.platform_whatsapp.intents import _capture_paid_invoice
        _capture_paid_invoice(invoice)
    return email
