import io
import json
import hashlib
import hmac
import os
import re
import zipfile

from django.conf import settings
from django import forms
from django.core.exceptions import ImproperlyConfigured
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.tenancy.context import current_workspace_id

from .access import notify_v2_action_required, notify_v2_admin_required

from .models import (
    NotificationBatch,
    NotificationEventType,
    NotificationPolicy,
    NotificationRecipient,
    NotificationTemplate,
    WhatsAppCloudWebhookReceipt,
)
from .services.delivery_service import DIGITAL_CHANNELS, dispatch_batch_jobs, process_whatsapp_cloud_webhook
from .services.whatsapp_readiness import assess_whatsapp_cloud_readiness
from .services.whatsapp_integration import (
    WhatsAppIntegrationError, get_whatsapp_cloud_credentials,
    get_whatsapp_cloud_integration, set_whatsapp_cloud_integration,
)


class WhatsAppCloudIntegrationForm(forms.Form):
    api_version = forms.CharField(max_length=16, initial="v20.0")
    phone_number_id = forms.CharField(max_length=64)
    access_token = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    webhook_verify_token = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    app_secret = forms.CharField(required=False, widget=forms.PasswordInput(render_value=False))
    is_enabled = forms.BooleanField(required=False)

    def __init__(self, *args, integration=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.integration = integration
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"
        if integration:
            for name in ("access_token", "webhook_verify_token", "app_secret"):
                self.fields[name].help_text = "Leave blank to keep the stored secret."

    def clean(self):
        cleaned = super().clean()
        if self.integration is None and not all(cleaned.get(name) for name in ("access_token", "webhook_verify_token", "app_secret")):
            raise forms.ValidationError("All three secrets are required for initial setup.")
        return cleaned


def _flash(request, level, message):
    try:
        messages.add_message(request, level, message)
    except Exception:
        pass


def _collect_artifacts(jobs):
    artifacts = []
    for job in jobs:
        related = getattr(job, "artifacts", None)
        if related is None:
            continue
        try:
            job_artifacts = list(related.all())
        except Exception:
            try:
                job_artifacts = list(related)
            except Exception:
                job_artifacts = []
        for artifact in job_artifacts:
            if getattr(artifact, "job", None) is None:
                artifact.job = job
        artifacts.extend(job_artifacts)
    return artifacts


def _safe_filename(value, fallback="artifact"):
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value or "")).strip("._")
    return cleaned or fallback


def _read_artifact_bytes(artifact):
    file_obj = getattr(artifact, "file", None)
    if not file_obj:
        return None

    should_close = False
    try:
        if hasattr(file_obj, "open"):
            file_obj.open("rb")
            should_close = hasattr(file_obj, "close")
        if hasattr(file_obj, "read"):
            data = file_obj.read()
            if isinstance(data, (bytes, bytearray)):
                return bytes(data)
    except Exception:
        return None
    finally:
        if should_close:
            try:
                file_obj.close()
            except Exception:
                pass
    return None


def _notify_settings_summary():
    workspace_id = current_workspace_id()
    integration = get_whatsapp_cloud_integration(workspace_id) if workspace_id else None
    return {
        "whatsapp_provider": "cloud",
        "integration": integration,
        "has_whatsapp_cloud_phone_id": bool(integration and integration.phone_number_id),
        "has_whatsapp_cloud_access_token": bool(integration and integration.access_token_ciphertext),
        "has_whatsapp_cloud_verify_token": bool(integration and integration.webhook_verify_token_ciphertext),
        "has_whatsapp_cloud_app_secret": bool(integration and integration.app_secret_ciphertext),
        "webhook_receipt_count": WhatsAppCloudWebhookReceipt.objects.count(),
        "webhook_unknown_count": WhatsAppCloudWebhookReceipt.objects.filter(
            processing_status=WhatsAppCloudWebhookReceipt.ProcessingStatus.UNKNOWN_JOB
        ).count(),
        "webhook_url": reverse("notify_v2_whatsapp_cloud_webhook"),
    }


@notify_v2_action_required("view")
def index(_request):
    return redirect("notify_v2_batch_list")


@notify_v2_action_required("view")
def settings_overview(request):
    settings_summary = _notify_settings_summary()
    whatsapp_readiness = assess_whatsapp_cloud_readiness()
    workspace = getattr(request, "workspace", None)
    can_manage_admin_models = bool(
        request.user.is_staff and workspace
    )
    context = {
        "notify_settings": settings_summary,
        "whatsapp_readiness": whatsapp_readiness,
        "can_manage_admin_models": can_manage_admin_models,
        "can_manage_whatsapp": bool(
            workspace and (is_platform_admin(request.user) or workspace.owner_id == request.user.pk or
                        get_workspace_role_name(request.user, workspace) in {"Owner", "Admin"})
        ),
        "counts": {
            "event_types": NotificationEventType.objects.filter(is_active=True).count(),
            "policies": NotificationPolicy.objects.filter(is_active=True).count(),
            "templates": NotificationTemplate.objects.filter(is_active=True).count(),
            "recipients": NotificationRecipient.objects.filter(is_active=True).count(),
        },
        "admin_urls": {
            "templates": reverse("admin:notify_v2_notificationtemplate_changelist"),
            "policies": reverse("admin:notify_v2_notificationpolicy_changelist"),
            "event_types": reverse("admin:notify_v2_notificationeventtype_changelist"),
            "recipients": reverse("admin:notify_v2_notificationrecipient_changelist"),
        },
    }
    return render(request, "notify_v2/settings.html", context)


@notify_v2_admin_required
def whatsapp_cloud_integration_setup(request):
    workspace = request.notify_workspace
    integration = get_whatsapp_cloud_integration(workspace.pk)
    initial = {
        "api_version": getattr(integration, "api_version", "v20.0"),
        "phone_number_id": getattr(integration, "phone_number_id", ""),
        "is_enabled": getattr(integration, "is_enabled", False),
    }
    form = WhatsAppCloudIntegrationForm(request.POST or None, initial=initial, integration=integration)
    if request.method == "POST" and form.is_valid():
        try:
            set_whatsapp_cloud_integration(workspace_id=workspace.pk, actor=request.user, **form.cleaned_data)
        except (WhatsAppIntegrationError, ImproperlyConfigured) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Workspace WhatsApp Cloud integration updated.")
            return redirect("notify_v2_settings")
    return render(request, "notify_v2/whatsapp_cloud_integration.html", {
        "form": form, "integration": integration,
        "webhook_url": request.build_absolute_uri(reverse("notify_v2_whatsapp_cloud_webhook")),
    })


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_cloud_webhook(request):
    workspace_id = getattr(getattr(request, "workspace", None), "pk", None)
    if not workspace_id:
        return JsonResponse({"ok": False, "error": "tenant_route_required"}, status=403)
    try:
        credentials = get_whatsapp_cloud_credentials(workspace_id, require_enabled=True)
    except (WhatsAppIntegrationError, ImproperlyConfigured):
        credentials = None
    if request.method == "GET":
        verify_token = credentials.webhook_verify_token if credentials else ""
        if (
            (request.GET.get("hub.mode") or "").strip() == "subscribe"
            and verify_token
            and (request.GET.get("hub.verify_token") or "").strip() == verify_token
        ):
            return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
        return HttpResponse("Webhook verification failed.", status=403)

    app_secret = credentials.app_secret if credentials else ""
    supplied_signature = (request.headers.get("X-Hub-Signature-256") or "").strip()
    if not app_secret:
        return JsonResponse({"ok": False, "error": "webhook_app_secret_missing"}, status=503)
    expected_signature = "sha256=" + hmac.new(
        app_secret.encode(), request.body, hashlib.sha256
    ).hexdigest()
    if not supplied_signature or not hmac.compare_digest(supplied_signature, expected_signature):
        return JsonResponse({"ok": False, "error": "invalid_signature"}, status=403)
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    if payload.get("object") != "whatsapp_business_account":
        return JsonResponse({"ok": False, "error": "invalid_object"}, status=400)
    configured_phone_id = credentials.phone_number_id if credentials else ""
    callback_phone_ids = {
        str(((change or {}).get("value") or {}).get("metadata", {}).get("phone_number_id") or "").strip()
        for entry in payload.get("entry") or []
        for change in (entry or {}).get("changes") or []
    }
    callback_phone_ids.discard("")
    if not configured_phone_id or callback_phone_ids != {configured_phone_id}:
        return JsonResponse({"ok": False, "error": "phone_number_id_mismatch"}, status=403)
    summary = process_whatsapp_cloud_webhook(
        payload,
        phone_number_id=configured_phone_id,
        signature_digest=supplied_signature.removeprefix("sha256="),
    )
    return JsonResponse({"ok": True, **summary})


@notify_v2_action_required("view")
def batch_list(request):
    batches = NotificationBatch.objects.select_related("event_type", "created_by").prefetch_related(
        "jobs"
    )
    notify_settings = _notify_settings_summary()
    return render(
        request,
        "notify_v2/batch_list.html",
        {
            "objects": batches,
            "notify_settings": notify_settings,
        },
    )


@notify_v2_action_required("view")
def batch_detail(request, pk):
    batch = get_object_or_404(
        NotificationBatch.objects.select_related("event_type", "created_by").prefetch_related(
            "jobs__event__recipient",
            "jobs__template",
            "jobs__artifacts",
        ),
        pk=pk,
    )
    jobs = list(batch.jobs.select_related("event__recipient", "template").all())
    artifacts = _collect_artifacts(jobs)
    latest_artifact = next((artifact for artifact in artifacts if getattr(artifact, "file", None)), None)
    digital_job_count = len([job for job in jobs if getattr(job, "channel", None) in DIGITAL_CHANNELS])
    selection_count = len(batch.selection_snapshot or [])
    recipient_count = len({job.event.recipient_id for job in jobs if getattr(job.event, "recipient_id", None)})
    return render(
        request,
        "notify_v2/batch_detail.html",
        {
            "object": batch,
            "jobs": jobs,
            "artifacts": artifacts,
            "artifact_count": len(artifacts),
            "latest_artifact": latest_artifact,
            "digital_job_count": digital_job_count,
            "can_send_digital": digital_job_count > 0,
            "selection_count": selection_count,
            "recipient_count": recipient_count or batch.job_count,
        },
    )


@notify_v2_action_required("send")
@require_http_methods(["POST"])
def batch_send_digital(request, pk):
    batch = get_object_or_404(NotificationBatch, pk=pk)
    result = dispatch_batch_jobs(batch)
    if result.sent_count and result.failed_count:
        _flash(
            request,
            messages.WARNING,
            f"Dispatched {result.sent_count} digital job(s); {result.failed_count} failed.",
        )
    elif result.sent_count:
        _flash(request, messages.SUCCESS, f"Dispatched {result.sent_count} digital job(s).")
    elif result.failed_count:
        _flash(request, messages.WARNING, f"No jobs were sent; {result.failed_count} failed.")
    else:
        _flash(request, messages.INFO, "No eligible digital jobs were waiting to be sent.")
    return redirect("notify_v2_batch_detail", pk=batch.pk)


@notify_v2_action_required("view")
def batch_download_artifacts(request, pk):
    batch = get_object_or_404(
        NotificationBatch.objects.prefetch_related("jobs__event__recipient", "jobs__artifacts"),
        pk=pk,
    )
    jobs = list(batch.jobs.select_related("event__recipient").all())
    artifacts = [artifact for artifact in _collect_artifacts(jobs) if getattr(artifact, "file", None)]
    if not artifacts:
        _flash(request, messages.WARNING, "No rendered artifact files are available for download yet.")
        return redirect("notify_v2_batch_detail", pk=batch.pk)

    zip_buffer = io.BytesIO()
    added_files = 0
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, artifact in enumerate(artifacts, start=1):
            payload = _read_artifact_bytes(artifact)
            if not payload:
                continue
            recipient = getattr(getattr(getattr(artifact, "job", None), "event", None), "recipient", None)
            recipient_name = _safe_filename(getattr(recipient, "name_snapshot", "recipient"), fallback="recipient")
            source_name = os.path.basename(getattr(getattr(artifact, "file", None), "name", ""))
            source_name = _safe_filename(source_name, fallback=f"artifact_{getattr(artifact, 'pk', index)}.pdf")
            archive_name = f"{index:02d}_{recipient_name}_{source_name}"
            archive.writestr(archive_name, payload)
            added_files += 1

    if not added_files:
        _flash(request, messages.WARNING, "The batch artifacts could not be read for download.")
        return redirect("notify_v2_batch_detail", pk=batch.pk)

    response = HttpResponse(zip_buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="notify_v2_batch_{batch.pk}_artifacts.zip"'
    return response


@notify_v2_action_required("edit")
@require_http_methods(["POST"])
def batch_mark_printed(request, pk):
    batch = get_object_or_404(NotificationBatch, pk=pk)
    batch.mark_printed()
    _flash(request, messages.SUCCESS, "Batch marked as printed.")
    return redirect("notify_v2_batch_detail", pk=batch.pk)


@notify_v2_action_required("edit")
@require_http_methods(["POST"])
def batch_mark_posted(request, pk):
    batch = get_object_or_404(NotificationBatch, pk=pk)
    batch.mark_posted()
    _flash(request, messages.SUCCESS, "Batch marked as posted.")
    return redirect("notify_v2_batch_detail", pk=batch.pk)
