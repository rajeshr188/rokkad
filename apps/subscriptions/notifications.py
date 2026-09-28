"""Persist receipt intent inside the payment transaction; dispatch separately."""
from .models import Invoice


def send_checkout_receipt(invoice_id):
    from apps.platform_mail.services import enqueue_receipt
    invoice = Invoice.objects.select_related("subscription__company").get(pk=invoice_id)
    return enqueue_receipt(invoice)
