"""Best-effort receipt delivery after the billing transaction commits."""
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from .models import Invoice


def send_checkout_receipt(invoice_id):
    invoice = Invoice.objects.select_related("subscription__company").get(pk=invoice_id)
    recipient = invoice.billing_contact_email
    if not recipient:
        return
    html = render_to_string("subscriptions/emails/subscription_confirmation.html", {"invoice": invoice})
    send_mail(
        f"Rokkad payment received: {invoice.invoice_number}", strip_tags(html),
        getattr(settings, "BILLING_EMAIL_SENDER", settings.DEFAULT_FROM_EMAIL),
        [recipient], html_message=html, fail_silently=False,
    )
