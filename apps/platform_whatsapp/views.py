import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.orgs.models import Company
from .configuration import inbound_blockers, readiness, transport_blockers
from .forms import (EnrollmentForm, PreferenceForm, PreviewForm, SetupReviewForm,
                    SetupConfirmationForm, DeliveryPreviewForm)
from .models import Contact, Delivery
from .intents import review_setup, confirm_setup, preview_delivery, recent_previews
from .services import (account_summary, begin_enrollment, set_preferences, change_contact,
                       preview, receive_message, require_account_actor)
from .phones import normalize_phone


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def preferences(request):
    require_account_actor(request.user)
    code, result, error, setup_review = None, None, None, None
    enrollment = EnrollmentForm()
    status = 200
    try:
        if request.method == "POST":
            action = request.POST.get("action")
            if action == "enroll":
                enrollment = EnrollmentForm(request.POST)
                if enrollment.is_valid():
                    _, code = begin_enrollment(actor=request.user, phone=enrollment.cleaned_data["phone"])
                else:
                    status = 400
            elif action == "preferences":
                form = PreferenceForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Review the workspace and selected categories.")
                data = form.cleaned_data
                set_preferences(actor=request.user, workspace_slug=data["workspace_slug"],
                    categories={k: data[k] for k in ("setup", "subscription", "service")},
                    contact_revision=data["contact_revision"])
            elif action in ("pause", "disconnect"):
                change_contact(actor=request.user, action=action)
            elif action == "preview":
                form = PreviewForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Choose a workspace and message category.")
                result = preview(actor=request.user, **form.cleaned_data)
            elif action == "review_setup":
                form = SetupReviewForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Choose a workspace for setup guidance.")
                setup_review = review_setup(actor=request.user, **form.cleaned_data)
            elif action == "confirm_setup":
                form = SetupConfirmationForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Review the setup message before confirming.")
                row = confirm_setup(actor=request.user, **form.cleaned_data)
                result = preview_delivery(actor=request.user, workspace_slug=row.workspace.slug, delivery_id=row.pk)
            elif action == "delivery_preview":
                form = DeliveryPreviewForm(request.POST)
                if not form.is_valid():
                    raise ValidationError("Choose a saved message to preview.")
                result = preview_delivery(actor=request.user, **form.cleaned_data)
            else:
                raise ValidationError("Choose a supported action.")
    except (ValidationError, IntegrityError, Contact.DoesNotExist, Company.DoesNotExist, Delivery.DoesNotExist) as exc:
        error = exc.messages[0] if isinstance(exc, ValidationError) else "Review your current contact and workspace."
        status = 400
    contact, rows = account_summary(request.user)
    for row in rows:
        row["deliveries"] = recent_previews(actor=request.user, workspace=row["workspace"])
        row["form"] = PreferenceForm(auto_id=f"preference-{row['workspace'].pk}-%s", initial={"workspace_slug": row["workspace"].slug,
            "contact_revision": contact.revision if contact else 1, **row["categories"]})
    return render(request, "platform_whatsapp/preferences.html", {
        "contact": contact, "workspace_rows": rows, "enrollment": enrollment,
        "pairing_code": code, "preview": result, "setup_review": setup_review,
        "error": error, "readiness": readiness(), "dispatch_configured": not transport_blockers()}, status=status)


@csrf_exempt
@never_cache
@require_http_methods(["GET", "POST"])
def webhook(request):
    # This exact /app/ route is global. Neither session nor profile supplies scope.
    from apps.tenancy.context import current_workspace_id
    if getattr(request, "workspace", None) is not None or current_workspace_id() is not None:
        return JsonResponse({"error": "global_context_required"}, status=403)
    if inbound_blockers():
        return JsonResponse({"error": "inbound_not_enabled"}, status=503)
    if request.method == "GET":
        if (request.GET.get("hub.mode") == "subscribe" and
                hmac.compare_digest(request.GET.get("hub.verify_token", "").encode(), settings.PLATFORM_WHATSAPP_VERIFY_TOKEN.encode())):
            return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
        return JsonResponse({"error": "verification_failed"}, status=403)
    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except (TypeError, ValueError):
        return JsonResponse({"error": "invalid_payload"}, status=400)
    if content_length > 65536:
        return JsonResponse({"error": "payload_too_large"}, status=413)
    body = request.body
    if len(body) > 65536:
        return JsonResponse({"error": "payload_too_large"}, status=413)
    expected = "sha256=" + hmac.new(settings.PLATFORM_WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    supplied = request.headers.get("X-Hub-Signature-256", "")
    if not hmac.compare_digest(supplied.encode(), expected.encode()):
        return JsonResponse({"error": "invalid_signature"}, status=403)
    messages, statuses = [], []
    from .receipts import parse_status, record_receipt
    try:
        payload = json.loads(body)
        if (not isinstance(payload, dict) or payload["object"] != "whatsapp_business_account"
                or not isinstance(payload["entry"], list) or not 1 <= len(payload["entry"]) <= 5):
            raise ValueError()
        for entry in payload["entry"]:
            if (str(entry["id"]) != settings.PLATFORM_WHATSAPP_WABA_ID
                    or not isinstance(entry["changes"], list) or not 1 <= len(entry["changes"]) <= 5):
                raise ValueError()
            for change in entry["changes"]:
                value = change["value"]
                if (change["field"] != "messages" or not isinstance(value, dict)
                        or value.get("messaging_product", "whatsapp") != "whatsapp"
                        or str(value["metadata"]["phone_number_id"]) != settings.PLATFORM_WHATSAPP_PHONE_ID):
                    raise ValueError()
                if (not isinstance(value.get("messages", []), list)
                        or not isinstance(value.get("statuses", []), list)
                        or len(value.get("messages", []))+len(value.get("statuses", [])) > 20):
                    raise ValueError()
                for status in value.get("statuses", []):
                    statuses.append(parse_status(status, phone_id=settings.PLATFORM_WHATSAPP_PHONE_ID,
                                                 waba_id=settings.PLATFORM_WHATSAPP_WABA_ID))
                for message in value.get("messages", []):
                    if message.get("type") != "text":
                        continue
                    message_id = message["id"]
                    text = message["text"]["body"]
                    if not isinstance(message_id, str) or not 1 <= len(message_id) <= 255:
                        raise ValueError()
                    if not isinstance(text, str) or len(text) > 200:
                        raise ValueError()
                    at = datetime.fromtimestamp(int(message["timestamp"]), tz=dt_timezone.utc)
                    if at > timezone.now() + timedelta(minutes=5):
                        raise ValueError()
                    messages.append({"message_id": message_id, "phone": normalize_phone("+" + message["from"]),
                                     "body": text, "message_at": at})
        if len(messages)+len(statuses) > 20:
            raise ValueError()
    except (KeyError, TypeError, ValueError, OverflowError, OSError, AttributeError, ValidationError):
        return JsonResponse({"error": "invalid_payload"}, status=400)
    # Validate every sender/structure before performing any mutation.
    from django.db import transaction
    with transaction.atomic():
        outcomes = [receive_message(**message) for message in messages]
        receipts = [record_receipt(status) for status in statuses]
    return JsonResponse({"ok": True, "processed": len(outcomes), "statuses": len(receipts)})
