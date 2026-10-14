"""Expiring administrator review of explicit targets; one message per owner."""
from datetime import datetime
import re

from django.core import signing
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company
from apps.orgs.services.platform_console import require_console_access
from apps.tenancy.context import workspace_context, current_workspace_id
from .configuration import transport_fingerprint, template_mapping
from .intents import _capture, _target, _link, fingerprint, TEMPLATE_REVISION
from .models import Announcement, AnnouncementTarget, Contact, Delivery

SALT = "platform-whatsapp.service-review.v1"


def _spec(value):
    try:
        if not isinstance(value, dict) or set(value) != {"purpose", "text", "revision", "impact_start", "impact_end", "expires_at", "urgent", "workspace_ids"}:
            raise ValueError
        if value["purpose"] not in {"maintenance", "incident"} or type(value["urgent"]) is not bool:
            raise ValueError
        if value["urgent"] and value["purpose"] != "incident":
            raise ValueError
        text = value["text"]
        if (not isinstance(text, str) or text != text.strip() or not 1 <= len(text) <= 700 or
            any(ord(c) < 32 for c in text) or re.search(r"https?://|www\.", text, re.I)):
            raise ValueError
        if not isinstance(value["revision"], str) or not re.fullmatch(r"[a-zA-Z0-9_.-]{1,64}", value["revision"]):
            raise ValueError
        first, last, expiry = (datetime.fromisoformat(value[k]) for k in ("impact_start", "impact_end", "expires_at"))
        if any(timezone.is_naive(v) for v in (first, last, expiry)) or last <= first or expiry <= timezone.now() or expiry > last:
            raise ValueError
        ids = value["workspace_ids"]
        if (not isinstance(ids, list) or not 1 <= len(ids) <= 100 or
            any(type(v) is not int or v <= 0 for v in ids) or ids != sorted(set(ids))):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise ValidationError("Review a bounded service notice, dates and explicit Workspace IDs.")
    return value


def _review(actor, spec):
    require_console_access(actor)
    spec = _spec(spec)
    rows = list(Company.all_objects.select_related("owner").filter(pk__in=spec["workspace_ids"]).exclude(slug="public").order_by("pk"))
    if len(rows) != len(spec["workspace_ids"]):
        raise ValidationError("Every affected Workspace must exist.")
    targets, seen = [], set()
    for workspace in rows:
        with workspace_context(workspace.pk):
            target = _target(workspace, "service", at=timezone.now())
            if not target:
                targets.append({"workspace_id": workspace.pk, "owner_id": workspace.owner_id,
                    "lifecycle": workspace.lifecycle_state, "name": workspace.name, "eligible": False})
                continue
            contact, consent = target
            representative = workspace.owner_id not in seen
            seen.add(workspace.owner_id)
            targets.append({"workspace_id": workspace.pk, "owner_id": workspace.owner_id,
                "lifecycle": workspace.lifecycle_state, "name": workspace.name, "eligible": True,
                "contact_id": contact.pk, "revision": contact.revision, "consent_id": consent.pk,
                "phone_hash": fingerprint(contact.phone), "representative": representative})
    from .controls import pilot, estimate, in_cohort
    try:
        value = pilot()
        estimate_total = str(estimate(value) * len(seen))
        template_mapping("service", TEMPLATE_REVISION)
        eligible_pilot = all(in_cohort(w, "service") for w in rows)
    except ValidationError:
        value, estimate_total, eligible_pilot = None, None, False
    link, link_problem = _link(reverse("contact"))
    # Template/configuration/pricing snapshots, even in capture mode, bind the review.
    return {"actor_id": actor.pk, "spec": spec, "targets": targets, "template_revision": TEMPLATE_REVISION,
        "transport": transport_fingerprint(), "estimate_inr": estimate_total,
        "pilot_eligible": eligible_pilot, "link": link, "link_problem": link_problem}


def review_announcement(*, actor, spec):
    reviewed = _review(actor, spec)
    return {**reviewed, "token": signing.dumps(reviewed, salt=SALT),
        "recipient_count": sum(t.get("representative", False) for t in reviewed["targets"])}


@transaction.atomic
def confirm_announcement(*, actor, token):
    require_console_access(actor)
    try:
        saved = signing.loads(token, salt=SALT, max_age=600)
    except signing.BadSignature as exc:
        raise ValidationError("The service review expired or changed. Review it again.") from exc
    if not isinstance(saved, dict) or saved.get("actor_id") != actor.pk:
        raise PermissionDenied("This review belongs to another administrator.")
    spec = _spec(saved.get("spec"))
    # Sorted locks make review confirmation and owner transfers serialize.
    locked = list(Company.all_objects.select_for_update().filter(pk__in=spec["workspace_ids"]).order_by("pk"))
    list(Contact.objects.select_for_update().filter(user_id__in=[w.owner_id for w in locked]).order_by("pk"))
    fresh = _review(actor, spec)
    if fresh != saved:
        raise ValidationError("Targets, consent, template, pricing or service details changed. Review again.")
    key = fingerprint(saved)
    existing = Announcement.objects.filter(review_digest=key).first()
    if existing:
        return existing
    announcement = Announcement.objects.create(creator=actor, purpose=spec["purpose"], text=spec["text"],
        revision=spec["revision"], impact_start=datetime.fromisoformat(spec["impact_start"]),
        impact_end=datetime.fromisoformat(spec["impact_end"]), expires_at=datetime.fromisoformat(spec["expires_at"]),
        urgent=spec["urgent"], affected_workspaces=saved["targets"], review_digest=key,
        configuration_fingerprint=saved["transport"])
    for target in saved["targets"]:
        if not target["eligible"]:
            continue
        with workspace_context(target["workspace_id"]):
            workspace = Company.all_objects.select_related("owner").get(pk=target["workspace_id"])
            current = _target(workspace, "service", at=announcement.created_at, lock=True)
            if not current:
                raise ValidationError("Service consent changed. Review the affected owners again.")
            contact, consent = current
            source = AnnouncementTarget.objects.create(workspace=workspace, announcement=announcement,
                owner=workspace.owner, contact=contact, contact_revision=contact.revision, consent=consent,
                representative=target["representative"])
            if source.representative:
                _capture(workspace=workspace, contact=contact, consent=consent, purpose=Delivery.Purpose.SERVICE,
                    facts=announcement_facts(source), source_recorded_at=source.created_at, announcement_target=source,
                    expiry=announcement.expires_at)
    return announcement


def announcement_facts(target):
    source = target.announcement
    return {"target_id": target.pk, "announcement_id": source.pk, "review_digest": source.review_digest,
        "revision": source.revision, "text": source.text, "impact_start": source.impact_start.isoformat(),
        "impact_end": source.impact_end.isoformat(), "expires_at": source.expires_at.isoformat(),
        "urgent": source.urgent, "owner_id": target.owner_id, "workspace_id": target.workspace_id,
        "recorded_at": target.created_at.isoformat()}


def announcement_current(target, *, local_only=False):
    if local_only:
        if current_workspace_id() != target.workspace_id:
            raise PermissionDenied("A matching Workspace is required for local preview checks.")
    elif current_workspace_id() is not None:
        raise PermissionDenied("Group checks require global context and successive explicit Workspace units.")
    source = target.announcement
    if source.expires_at <= timezone.now() or source.configuration_fingerprint != transport_fingerprint():
        return False
    # All represented Workspaces for this owner must retain their reviewed choices.
    for saved in source.affected_workspaces:
        if (not saved["eligible"] or saved["owner_id"] != target.owner_id
            or local_only and saved["workspace_id"] != target.workspace_id):
            continue
        workspace = Company.all_objects.select_related("owner").get(pk=saved["workspace_id"])
        with workspace_context(workspace.pk):
            current = _target(workspace, "service", at=timezone.now())
            if (workspace.owner_id != saved["owner_id"] or workspace.lifecycle_state != saved["lifecycle"]
                or not current or current[0].pk != saved["contact_id"] or current[0].revision != saved["revision"]
                or current[1].pk != saved["consent_id"]):
                return False
    return target.representative
