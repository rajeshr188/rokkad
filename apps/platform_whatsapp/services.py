"""No network transport. Enrollment changes never change source business state."""
import hashlib
import hmac
import secrets
from datetime import timedelta

from django.core.exceptions import PermissionDenied, ValidationError
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.subscriptions.checkout import require_billing_owner
from apps.tenancy.context import current_workspace_id, workspace_context

from .configuration import configuration_fingerprint
from .models import Contact, ContactEvent, Preference, ConsentEvent, Suppression, InboundReceipt
from .phones import normalize_phone

CONSENT_VERSION = "rokkad-owner-whatsapp-20261014"
CATEGORIES = ("setup", "subscription", "service")


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def require_account_actor(actor):
    if (not actor or not actor.is_authenticated or not actor.is_active or
            current_workspace_id() is not None):
        raise PermissionDenied("An active signed-in account in global context is required.")


def require_owner(actor, workspace):
    require_billing_owner(workspace=workspace, actor=actor)
    if workspace.owner_id != actor.pk:
        raise PermissionDenied("Only the current owner can consent to their own messages.")


def owned_workspaces(actor):
    require_account_actor(actor)
    return Company.all_objects.filter(owner=actor).exclude(slug="public").order_by("name", "pk")


@transaction.atomic
def begin_enrollment(*, actor, phone):
    require_account_actor(actor)
    workspace = owned_workspaces(actor).first()
    if workspace is None:
        raise PermissionDenied("Only a Workspace owner can enroll.")
    with workspace_context(workspace.pk):
        require_owner(actor, workspace)
    # Serialize account enrollment, including the first row.
    get_user_model().objects.select_for_update().get(pk=actor.pk)
    phone = normalize_phone(phone)
    if Contact.objects.exclude(user=actor).filter(phone=phone).exists():
        raise ValidationError("This number cannot be connected to this account.")
    now = timezone.now()
    contact, created = Contact.objects.select_for_update().get_or_create(user=actor)
    if contact.challenge_issued_at and now < contact.challenge_issued_at + timedelta(seconds=60):
        raise ValidationError("Wait a minute before requesting another pairing code.")
    if now >= contact.issue_window_at + timedelta(hours=1):
        contact.issue_window_at, contact.issue_count = now, 0
    if contact.issue_count >= 5:
        raise ValidationError("Too many enrollment requests. Try again after an hour.")
    code = "ROKKAD " + secrets.token_hex(16)
    if not created:
        contact.revision += 1
    contact.phone, contact.state = phone, Contact.State.PENDING
    contact.challenge_hash = digest(code)
    contact.challenge_expires_at = now + timedelta(minutes=15)
    contact.challenge_issued_at = now
    contact.match_failures = 0
    contact.issue_count += 1
    contact.verified_at = None
    contact.sender_fingerprint = ""
    contact.save()
    ContactEvent.objects.create(contact=contact, kind="enrollment_requested", revision=contact.revision)
    return contact, code


@transaction.atomic
def set_preferences(*, actor, workspace_slug, categories, contact_revision):
    require_account_actor(actor)
    if set(categories) - set(CATEGORIES) or any(type(v) is not bool for v in categories.values()):
        raise ValidationError("Select the supported message categories.")
    workspace = Company.all_objects.select_for_update().get(slug=workspace_slug)
    with workspace_context(workspace.pk):
        require_owner(actor, workspace)
        contact = Contact.objects.select_for_update().get(user=actor)
        if contact.revision != contact_revision or contact.state == Contact.State.DISCONNECTED:
            raise ValidationError("The connected number changed. Review your choices again.")
        values = {key: categories.get(key, False) for key in CATEGORIES}
        preference, _ = Preference.objects.update_or_create(workspace=workspace, defaults={
            "contact": contact, "contact_revision": contact.revision,
            "consent_version": CONSENT_VERSION, "language": "en", **values})
        ConsentEvent.objects.create(workspace=workspace, contact=contact, actor=actor,
                                   contact_revision=contact.revision, consent_version=CONSENT_VERSION, **values)
        return preference


@transaction.atomic
def change_contact(*, actor, action):
    require_account_actor(actor)
    contact = Contact.objects.select_for_update().get(user=actor)
    if action not in ("pause", "disconnect"):
        raise ValidationError("Choose pause or disconnect.")
    contact.revision += 1
    contact.state = Contact.State.DISCONNECTED if action == "disconnect" else Contact.State.PAUSED
    contact.challenge_hash, contact.sender_fingerprint = "", ""
    contact.challenge_expires_at, contact.verified_at = None, None
    if action == "disconnect":
        contact.phone = ""
    contact.save()
    ContactEvent.objects.create(contact=contact, kind=action, revision=contact.revision)
    return contact


def account_summary(actor):
    require_account_actor(actor)
    contact = Contact.objects.filter(user=actor).first()
    rows = []
    for workspace in owned_workspaces(actor):
        with workspace_context(workspace.pk):
            preference = Preference.objects.filter(workspace=workspace, contact=contact).first() if contact else None
            current = bool(preference and preference.contact_revision == contact.revision)
            rows.append({"workspace": workspace, "categories": {
                key: bool(current and getattr(preference, key)) for key in CATEGORIES}})
    return contact, rows


def preview(*, actor, workspace_slug, category):
    require_account_actor(actor)
    if category not in CATEGORIES:
        raise ValidationError("Choose a supported message category.")
    workspace = Company.all_objects.get(slug=workspace_slug)
    with workspace_context(workspace.pk):
        require_owner(actor, workspace)
        contact = Contact.objects.filter(user=actor).first()
        preference = Preference.objects.filter(workspace=workspace, contact=contact).first() if contact else None
        eligible = bool(contact and preference and getattr(preference, category)
            and preference.contact_revision == contact.revision
            and contact.state == Contact.State.VERIFIED
            and contact.sender_fingerprint == configuration_fingerprint()
            and not Suppression.objects.filter(phone_hash=digest(contact.phone)).exists())
    bodies = {
        "setup": f"Open Rokkad to continue setup for {workspace.name}.",
        "subscription": f"Open Billing in Rokkad to review the subscription for {workspace.name}.",
        "service": "Open Rokkad support for service information.",
    }
    return {"body": bodies[category], "eligible": eligible, "can_send": False,
            "recipient": contact.masked_phone if contact else "No number connected",
            "category": category}


@transaction.atomic
def receive_message(*, message_id, phone, body, message_at):
    """Internal boundary: call only after provider authentication and validation."""
    if current_workspace_id() is not None:
        raise PermissionDenied("Platform pairing requires global context.")
    receipt, created = InboundReceipt.objects.get_or_create(message_id=message_id)
    if not created:
        return "duplicate"
    phone = normalize_phone(phone)
    contact = Contact.objects.select_for_update().filter(phone=phone).first()
    if body.strip().casefold() in {"stop", "unsubscribe", "cancel", "opt out", "opt-out", "बंद", "நிறுத்து"}:
        Suppression.objects.get_or_create(phone_hash=digest(phone))
        if contact:
            contact.state = Contact.State.PAUSED
            contact.revision += 1
            contact.challenge_hash = ""
            contact.challenge_expires_at = None
            contact.verified_at, contact.sender_fingerprint = None, ""
            contact.save()
            ContactEvent.objects.create(contact=contact, kind="provider_opt_out", revision=contact.revision)
        outcome = "stopped"
    elif (contact and contact.state == Contact.State.PENDING and contact.challenge_hash
          and contact.challenge_expires_at and timezone.now() < contact.challenge_expires_at
          and contact.challenge_issued_at - timedelta(seconds=1) <= message_at <= timezone.now() + timedelta(minutes=5)):
        if hmac.compare_digest(contact.challenge_hash, digest(body.strip())):
            contact.state = Contact.State.VERIFIED
            contact.verified_at = timezone.now()
            contact.sender_fingerprint = configuration_fingerprint()
            contact.challenge_hash = ""
            contact.challenge_expires_at = None
            contact.save()
            # An explicit, new authenticated pairing is required to restore consent.
            Suppression.objects.filter(phone_hash=digest(phone)).delete()
            ContactEvent.objects.create(contact=contact, kind="provider_paired", revision=contact.revision)
            outcome = "paired"
        else:
            contact.match_failures += 1
            if contact.match_failures >= 5:
                contact.challenge_hash = ""
                contact.challenge_expires_at = None
            contact.save()
            outcome = "code_rejected"
    else:
        outcome = "ignored"
    receipt.outcome = outcome
    receipt.save(update_fields=["outcome"])
    return outcome
