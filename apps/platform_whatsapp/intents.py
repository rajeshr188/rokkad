"""Source transactions own immutable intents; preview history never promotes."""
import hashlib
import json
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from django.conf import settings
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company
from apps.subscriptions.models import Invoice, Payment, SubscriptionEvent
from apps.subscriptions.provider_configuration import invoice_mode
from apps.tenancy.context import current_workspace_id, workspace_context

from .configuration import configuration_fingerprint
from .models import Contact, ConsentEvent, Delivery, Preference, SetupRequest, Suppression
from .services import CONSENT_VERSION, digest, require_account_actor, require_owner

TEMPLATE_REVISION = "rokkad-owner-source-preview-1"
REVIEW_SALT = "platform-whatsapp.setup-review.v1"


def fingerprint(facts):
    return hashlib.sha256(json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _require_source_transaction():
    if not connection.in_atomic_block:
        raise ValidationError("Source intent must be captured inside its source transaction.")


def _target(workspace, category, *, at, lock=False):
    """Caller owns explicit Workspace context; consent must precede the source."""
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied("Explicit matching Workspace context required.")
    if not workspace.owner.is_active:
        return None
    try:
        require_owner(workspace.owner, workspace)
    except PermissionDenied:
        return None
    contacts = Contact.objects.select_for_update() if lock else Contact.objects
    contact = contacts.filter(user=workspace.owner).first()
    if (not contact or contact.state != Contact.State.VERIFIED or not contact.verified_at
            or contact.verified_at > at or contact.sender_fingerprint != configuration_fingerprint()
            or Suppression.objects.filter(phone_hash=digest(contact.phone)).exists()):
        return None
    preference = Preference.objects.filter(workspace=workspace, contact=contact).first()
    consent = ConsentEvent.objects.filter(workspace=workspace, contact=contact).order_by("-pk").first()
    if (not preference or not consent or preference.contact_revision != contact.revision
            or consent.contact_revision != contact.revision or consent.actor_id != workspace.owner_id
            or consent.created_at > at or consent.consent_version != CONSENT_VERSION
            or preference.consent_version != CONSENT_VERSION or preference.language != "en"
            or not getattr(preference, category) or not getattr(consent, category)
            or any(getattr(preference, key) != getattr(consent, key)
                   for key in ("setup", "subscription", "service"))):
        return None
    return contact, consent


def _trial_facts(event):
    if event.event_type != "trial.started":
        raise ValidationError("Only an explicit trial-start event can support this confirmation.")
    end = datetime.fromisoformat(event.payload["trial_end_date"])
    if timezone.is_naive(end):
        raise ValidationError("Trial end must carry its original timezone.")
    return {"event_id": event.pk, "subscription_id": event.subscription_id,
            "plan_id": event.payload["plan_id"], "trial_end": end.isoformat()}


def _paid_facts(invoice):
    mode = invoice_mode(invoice)
    payment = Payment.objects.get(invoice=invoice)
    if (invoice.status != "paid" or not invoice.paid_at or payment.status != "captured"
            or payment.refund_amount or payment.amount != invoice.total_amount
            or payment.razorpay_order_id != invoice.razorpay_order_id
            or payment.razorpay_payment_id != invoice.razorpay_payment_id
            or invoice.checkout_snapshot.get("workspace_id") != invoice.subscription.company_id
            or invoice.checkout_snapshot.get("currency") != "INR" or mode not in {"test", "live"}):
        raise ValidationError("A mode-classified, matching paid invoice/payment is required.")
    return {"invoice_id": invoice.pk, "subscription_id": invoice.subscription_id,
            "payment_id": payment.pk, "amount": str(invoice.total_amount), "currency": "INR",
            "invoice_number": invoice.invoice_number, "paid_at": invoice.paid_at.isoformat(),
            "provider_payment_id": payment.razorpay_payment_id,
            "recorded_at": payment.created_at.isoformat(), "provider_mode": mode}


def _setup_facts(request):
    return {"request_id": request.pk, "workspace_id": request.workspace_id,
            "contact_id": request.contact_id, "revision": request.contact_revision,
            "consent_id": request.consent_id, "requested_at": request.created_at.isoformat()}


def _capture(*, workspace, contact, consent, purpose, facts, source_recorded_at, expiry=None, **source):
    now = timezone.now()
    lifetime = timedelta(days=7) if purpose == Delivery.Purpose.PAID else timedelta(days=1)
    from .controls import capture_only
    return Delivery.objects.create(workspace=workspace, contact=contact, contact_revision=contact.revision,
        consent=consent, owner=workspace.owner, recipient_phone=contact.phone,
        workspace_name=workspace.name, purpose=purpose, template_revision=TEMPLATE_REVISION,
        sender_fingerprint=configuration_fingerprint(), source_fingerprint=fingerprint(facts),
        provider_mode=facts.get("provider_mode", ""), source_recorded_at=source_recorded_at,
        created_at=now, expires_at=expiry or now+lifetime,
        capture_only=capture_only(workspace, purpose, source_at=source_recorded_at, now=now), **source)


def _capture_trial_started(event):
    """Internal helper, called only at the existing trial source commit boundary."""
    _require_source_transaction()
    event = SubscriptionEvent.objects.select_related("subscription__company__owner").get(pk=event.pk)
    workspace = Company.all_objects.select_for_update().select_related("owner").get(pk=event.subscription.company_id)
    with workspace_context(workspace.pk):
        existing = Delivery.objects.filter(trial_event=event).first()
        if existing:
            return existing
        if workspace.lifecycle_state != "ACTIVE":
            return None
        target = _target(workspace, "subscription", at=event.created_at, lock=True)
        if not target:
            return None
        facts = _trial_facts(event)
        if (event.subscription.status != "trial" or not event.subscription.trial_end_date
                or event.subscription.trial_end_date.isoformat() != facts["trial_end"]
                or event.subscription.trial_end_date <= timezone.now()):
            return None
        return _capture(workspace=workspace, contact=target[0], consent=target[1],
            purpose=Delivery.Purpose.TRIAL, facts=facts, source_recorded_at=event.created_at, trial_event=event)


def _capture_paid_invoice(invoice):
    """Internal helper. Notifications calls this only for a newly recorded capture."""
    _require_source_transaction()
    invoice = Invoice.objects.select_related("subscription__company__owner").get(pk=invoice.pk)
    workspace = Company.all_objects.select_for_update().select_related("owner").get(pk=invoice.subscription.company_id)
    with workspace_context(workspace.pk):
        existing = Delivery.objects.filter(invoice=invoice).first()
        if existing:
            return existing
        payment = Payment.objects.filter(invoice=invoice).first()
        if not payment:
            return None
        target = _target(workspace, "subscription", at=payment.created_at, lock=True)
        if not target:
            return None
        try:
            facts = _paid_facts(invoice)
        except ValidationError:
            return None  # Unclassified/legacy evidence never becomes a WhatsApp receipt.
        return _capture(workspace=workspace, contact=target[0], consent=target[1],
            purpose=Delivery.Purpose.PAID, facts=facts, source_recorded_at=payment.created_at, invoice=invoice)


def _link(path):
    origin = getattr(settings, "PLATFORM_WHATSAPP_BASE_URL", "").rstrip("/")
    try:
        parsed = urlsplit(origin)
        valid = (parsed.scheme == "https" and parsed.hostname and (parsed.port is None or parsed.port > 0)
                 and not parsed.username and not parsed.password and not parsed.path and not parsed.query and not parsed.fragment)
    except ValueError:
        valid = False
    return (origin + path, "") if valid else (path, "canonical_https_origin_unavailable")


@transaction.atomic
def review_setup(*, actor, workspace_slug):
    require_account_actor(actor)
    workspace = Company.all_objects.select_for_update().select_related("owner").get(slug=workspace_slug)
    with workspace_context(workspace.pk):
        require_owner(actor, workspace)
        if workspace.lifecycle_state != "ACTIVE":
            raise ValidationError("This Workspace cannot request routine setup guidance.")
        target = _target(workspace, "setup", at=timezone.now(), lock=True)
        if not target:
            raise ValidationError("Pair your account and select setup assistance before continuing.")
        contact, consent = target
        path = reverse("workspace_slug_settings_setup", kwargs={"workspace_slug": workspace.slug})
        link, _ = _link(path)
        body = f"Open Rokkad to continue setup for {workspace.name}."
        review = {"actor_id": actor.pk, "workspace_id": workspace.pk, "contact_id": contact.pk,
            "contact_revision": contact.revision, "consent_id": consent.pk,
            "sender_fingerprint": configuration_fingerprint(), "template_revision": TEMPLATE_REVISION,
            "content": fingerprint({"body": body, "link": link})}
        return {"body": body, "link": link, "recipient": contact.masked_phone, "can_send": False,
                "workspace_slug": workspace.slug, "token": signing.dumps(review, salt=REVIEW_SALT)}


@transaction.atomic
def confirm_setup(*, actor, token):
    require_account_actor(actor)
    try:
        saved = signing.loads(token, salt=REVIEW_SALT, max_age=600)
    except signing.BadSignature as exc:
        raise ValidationError("The setup message review expired or changed. Review it again.") from exc
    if not isinstance(saved, dict) or saved.get("actor_id") != actor.pk:
        raise PermissionDenied("This review belongs to another account.")
    workspace = Company.all_objects.select_for_update().select_related("owner").get(pk=saved.get("workspace_id"))
    current = review_setup(actor=actor, workspace_slug=workspace.slug)
    fresh = signing.loads(current["token"], salt=REVIEW_SALT, max_age=600)
    if saved != fresh:
        raise ValidationError("Your workspace, contact or choices changed. Review the message again.")
    with workspace_context(workspace.pk):
        request = SetupRequest.objects.filter(workspace=workspace, contact_id=saved["contact_id"],
            contact_revision=saved["contact_revision"]).first()
        if request:
            return Delivery.objects.get(setup_request=request)
        request = SetupRequest.objects.create(workspace=workspace, contact_id=saved["contact_id"],
            contact_revision=saved["contact_revision"], consent_id=saved["consent_id"])
        return _capture(workspace=workspace, contact=request.contact, consent=request.consent,
            purpose=Delivery.Purpose.SETUP, facts=_setup_facts(request),
            source_recorded_at=request.created_at, setup_request=request)


def _render(row):
    reasons = []
    workspace = row.workspace
    if row.owner_id != workspace.owner_id:
        reasons.append("owner_changed")
    category = "setup" if row.purpose == "setup" else "service" if row.purpose == "service" else "subscription"
    target = _target(workspace, category, at=timezone.now())
    if (not target or target[0].pk != row.contact_id or target[0].revision != row.contact_revision
            or target[1].pk != row.consent_id or target[0].phone != row.recipient_phone
            or row.sender_fingerprint != configuration_fingerprint()):
        reasons.append("contact_or_consent_changed")
    if row.expires_at <= timezone.now():
        reasons.append("preview_expired")
    if row.template_revision != TEMPLATE_REVISION:
        reasons.append("template_revision_changed")
    facts = None
    try:
        if row.purpose == "setup":
            facts = _setup_facts(row.setup_request)
            body = f"Open Rokkad to continue setup for {row.workspace_name}."
            path = reverse("workspace_slug_settings_setup", kwargs={"workspace_slug": workspace.slug})
            if workspace.lifecycle_state != "ACTIVE":
                reasons.append("routine_guidance_unavailable")
        elif row.purpose == "trial":
            facts = _trial_facts(row.trial_event)
            end = datetime.fromisoformat(facts["trial_end"])
            body = f"Your Rokkad trial for {row.workspace_name} ends on {timezone.localtime(end):%d %b %Y, %H:%M %Z}."
            path = reverse("workspace_slug_settings_billing", kwargs={"workspace_slug": workspace.slug})
            sub = row.trial_event.subscription
            if (workspace.lifecycle_state != "ACTIVE" or sub.company_id != row.workspace_id
                    or sub.status != "trial" or sub.trial_end_date != end or end <= timezone.now()):
                reasons.append("trial_no_longer_current")
        elif row.purpose == "ending":
            from .reminders import reminder_current, reminder_facts
            facts = reminder_facts(row.reminder)
            end = row.reminder.trial_end
            body = f"Your Rokkad trial for {row.workspace_name} ends on {timezone.localtime(end):%d %b %Y, %H:%M %Z}. Review your subscription or contact support."
            path = reverse("workspace_slug_settings_billing", kwargs={"workspace_slug": workspace.slug})
            if not reminder_current(workspace, row.reminder.trial_event, end, at=timezone.now()):
                reasons.append("trial_reminder_no_longer_current")
        elif row.purpose == "service":
            from .announcements import announcement_current, announcement_facts
            facts = announcement_facts(row.announcement_target)
            body = f"Rokkad service update: {facts['text']}"
            path = reverse("contact")
            if not announcement_current(row.announcement_target, local_only=True):
                reasons.append("service_review_no_longer_current")
        else:
            facts = _paid_facts(row.invoice)
            prefix = "[TEST] " if row.provider_mode == "test" else ""
            body = f"{prefix}Rokkad recorded payment of INR {facts['amount']} for invoice {facts['invoice_number']}."
            path = reverse("workspace_subscriptions:invoice-detail",
                           kwargs={"workspace_slug": workspace.slug, "pk": row.invoice_id})
        if fingerprint(facts) != row.source_fingerprint:
            reasons.append("source_evidence_changed")
            body = "The saved source changed and needs review. No confirmation can be delivered."
    except (ValidationError, KeyError, TypeError, ValueError, Payment.DoesNotExist):
        reasons.append("source_evidence_unavailable")
        body, path = "The saved source needs review. No confirmation can be delivered.", ""
    link, link_problem = _link(path)
    if link_problem:
        reasons.append(link_problem)
    from .receipts import delivery_summary
    summary = delivery_summary(row)
    status_labels = {"queued": "Queued — awaiting checked dispatch", "claimed": "Sending — acceptance unconfirmed",
        "accepted": "Accepted by Meta — delivery unconfirmed", "sent": "Sent — delivery unconfirmed",
        "delivered": "Delivered", "read": "Read", "failed": "Delivery failed",
        "rejected": "Rejected by Meta", "unknown": "Acceptance unknown — needs reconciliation",
        "cancelled": "Cancelled before sending", "captured": "Saved preview only — not sent"}
    return {"id": row.pk, "purpose": row.get_purpose_display(), "created_at": row.created_at,
        "body": body, "link": link if path else "", "recipient": row.masked_phone,
        "eligible": not reasons, "blockers": reasons, "can_send": False,
        "status": status_labels[summary["status"]], "receipt_conflict": summary["conflict"]}


def preview_delivery(*, actor, workspace_slug, delivery_id):
    require_account_actor(actor)
    workspace = Company.all_objects.select_related("owner").get(slug=workspace_slug)
    with workspace_context(workspace.pk):
        require_owner(actor, workspace)
        row = Delivery.objects.select_related("workspace__owner", "setup_request", "trial_event__subscription",
            "invoice__subscription").get(pk=delivery_id, workspace=workspace, owner=actor)
        return _render(row)


def recent_previews(*, actor, workspace):
    """Only called while building an authorised owner's global account summary."""
    require_account_actor(actor)
    with workspace_context(workspace.pk):
        require_owner(actor, workspace)
        rows = Delivery.objects.select_related("workspace__owner", "setup_request", "trial_event__subscription",
            "invoice__subscription").filter(workspace=workspace, owner=actor).order_by("-pk")[:10]
        return [_render(row) for row in rows]
