import io
import json
import os
import re
import zipfile

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from .models import NotificationBatch
from .services.delivery_service import DIGITAL_CHANNELS, dispatch_batch_jobs, process_whatsapp_cloud_webhook
from .services import render_batch_pdf


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


@login_required
def index(_request):
    return redirect("notify_v2_batch_list")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp_cloud_webhook(request):
    if request.method == "GET":
        verify_token = (getattr(settings, "WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN", "") or "").strip()
        if (
            (request.GET.get("hub.mode") or "").strip() == "subscribe"
            and verify_token
            and (request.GET.get("hub.verify_token") or "").strip() == verify_token
        ):
            return HttpResponse(request.GET.get("hub.challenge", ""), content_type="text/plain")
        return HttpResponse("Webhook verification failed.", status=403)

    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"ok": False, "error": "invalid_json"}, status=400)

    summary = process_whatsapp_cloud_webhook(payload)
    return JsonResponse({"ok": True, **summary})


@login_required
def batch_list(request):
    batches = NotificationBatch.objects.select_related("event_type", "created_by").prefetch_related(
        "jobs"
    )
    return render(
        request,
        "notify_v2/batch_list.html",
        {
            "objects": batches,
            "entrypoint_url_name": "girvi:loan_list",
            "entrypoint_text": "Create a new reminder batch from selected Girvi loans.",
            "legacy_url_name": "notify_noticegroup_list",
        },
    )


@login_required
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
    loan_count = len(batch.selection_snapshot or [])
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
            "loan_count": loan_count,
            "recipient_count": recipient_count or batch.job_count,
        },
    )


@login_required
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


@login_required
def batch_print(request, pk):
    batch = get_object_or_404(NotificationBatch, pk=pk)
    pdf = render_batch_pdf(batch)
    if not pdf:
        _flash(request, messages.WARNING, "No printable content is available for this batch yet.")
        return redirect("notify_v2_batch_detail", pk=batch.pk)

    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="notify_v2_batch_{batch.pk}.pdf"'
    return response


@login_required
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


@login_required
@require_http_methods(["POST"])
def batch_mark_printed(request, pk):
    batch = get_object_or_404(NotificationBatch, pk=pk)
    batch.mark_printed()
    _flash(request, messages.SUCCESS, "Batch marked as printed.")
    return redirect("notify_v2_batch_detail", pk=batch.pk)


@login_required
@require_http_methods(["POST"])
def batch_mark_posted(request, pk):
    batch = get_object_or_404(NotificationBatch, pk=pk)
    batch.mark_posted()
    _flash(request, messages.SUCCESS, "Batch marked as posted.")
    return redirect("notify_v2_batch_detail", pk=batch.pk)
