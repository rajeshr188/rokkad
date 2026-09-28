"""One explicitly addressed receipt in the isolated billing rehearsal only."""
import re

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import validate_email
from django.db import connection

from apps.subscriptions.provider_configuration import invoice_mode, provider_mode
from apps.tenancy.context import workspace_context
from .models import Delivery, Suppression
from .services import recipient_hash, render_delivery, source_problem


def require_rehearsal_runtime():
    if not getattr(settings, "BILLING_REHEARSAL", False) or provider_mode() != "test":
        raise PermissionDenied("An isolated Test Mode billing rehearsal is required.")
    database = getattr(settings, "REHEARSAL_DATABASE_NAME", "")
    if (not re.fullmatch(r"rokkad_baseline_rehearsal_billing_[a-z0-9_]+", database)
            or connection.settings_dict["NAME"] != database
            or connection.settings_dict["HOST"] not in {"127.0.0.1", "localhost", "::1"}):
        raise PermissionDenied("Use the dedicated loopback billing rehearsal database.")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(), rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user")
        if cursor.fetchone() != (database, False, False):
            raise PermissionDenied("The isolated receipt worker requires a restricted database role.")


def validate_test_receipt(row, *, actor, recipient, reference):
    require_rehearsal_runtime()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]{2,79}", reference or ""):
        raise ValidationError("Provide a short operator reference without contact details.")
    if not row.invoice_id or invoice_mode(row.invoice) != "test":
        raise ValidationError("Select an invoice with recorded Test Mode evidence.")
    actor = get_user_model().objects.get(pk=actor.pk, is_active=True)
    workspace = row.invoice.subscription.company
    from apps.orgs.models import Company
    from apps.subscriptions.checkout import require_billing_owner
    with workspace_context(workspace.pk):
        workspace = Company.all_objects.select_for_update().get(pk=workspace.pk)
        require_billing_owner(workspace=workspace, actor=actor)
    validate_email(recipient)
    domain = recipient.rsplit("@", 1)[-1].casefold()
    if (domain in {"example.com", "example.net", "example.org", "localhost"}
            or domain.endswith((".test", ".invalid", ".example", ".localhost"))):
        raise ValidationError("Use the chosen controlled inbox, not a fictional address.")
    expected = recipient.strip().casefold()
    if expected != row.recipient.casefold() or expected != row.invoice.billing_contact_email.casefold():
        raise ValidationError("The chosen inbox must match the immutable invoice and delivery recipient.")
    if source_problem(row) or Suppression.objects.filter(recipient_hash=recipient_hash(row.recipient)).exists():
        raise ValidationError("The receipt source or recipient is not eligible for this rehearsal.")
    if row.status == Delivery.Status.QUEUED and row.attempt_count:
        raise ValidationError("This rehearsal was already attempted; review its evidence before any further action.")


def preview_test_receipt(delivery_id, *, actor, recipient, reference):
    row = Delivery.objects.select_related("invoice__subscription__company").get(pk=delivery_id)
    validate_test_receipt(row, actor=actor, recipient=recipient, reference=reference)
    return row, render_delivery(row)


def dispatch_test_receipt(delivery_id, *, actor, recipient, reference):
    from .services import _dispatch_one
    return _dispatch_one(delivery_id, rehearsal={"actor": actor, "recipient": recipient, "reference": reference})
