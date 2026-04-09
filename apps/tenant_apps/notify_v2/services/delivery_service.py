from __future__ import annotations

import logging
from dataclasses import dataclass, field

import requests
from django.conf import settings
from django.core.mail import send_mail
from django.template import Context, Template
from django.utils import timezone

from apps.tenant_apps.notify_v2.models import NotificationArtifact, NotificationAttemptLog, NotificationJob

try:
	from twilio.rest import Client
except Exception:  # pragma: no cover - handled at runtime when integration is enabled
	Client = None

logger = logging.getLogger(__name__)

DIGITAL_CHANNELS = {
	NotificationJob.Channel.EMAIL,
	NotificationJob.Channel.SMS,
	NotificationJob.Channel.WHATSAPP,
}


def _normalize_phone(value: str) -> str:
	phone = (value or "").strip()
	if not phone:
		return ""
	if phone.startswith("+"):
		return "+" + "".join(ch for ch in phone[1:] if ch.isdigit())
	digits = "".join(ch for ch in phone if ch.isdigit())
	return f"+{digits}" if digits else ""


def _as_whatsapp_address(value: str) -> str:
	normalized = value.strip()
	if normalized.startswith("whatsapp:"):
		return normalized
	return f"whatsapp:{normalized}"


def _twilio_settings() -> dict:
	return {
		"sid": (getattr(settings, "TWILIO_ACCOUNT_SID", "") or "").strip(),
		"token": (getattr(settings, "TWILIO_AUTH_TOKEN", "") or "").strip(),
		"from_number": (getattr(settings, "TWILIO_FROM_NUMBER", "") or "").strip(),
		"whatsapp_from": (getattr(settings, "TWILIO_WHATSAPP_FROM_NUMBER", "") or "").strip(),
		"stub_fallback": bool(getattr(settings, "NOTIFY_V2_TWILIO_STUB_FALLBACK", True)),
	}


def _whatsapp_provider() -> str:
	provider = (getattr(settings, "NOTIFY_V2_WHATSAPP_PROVIDER", "twilio") or "twilio").strip().lower()
	return provider if provider in {"twilio", "cloud"} else "twilio"


def _whatsapp_cloud_settings() -> dict:
	return {
		"api_version": (getattr(settings, "WHATSAPP_CLOUD_API_VERSION", "v20.0") or "v20.0").strip(),
		"phone_number_id": (getattr(settings, "WHATSAPP_CLOUD_PHONE_NUMBER_ID", "") or "").strip(),
		"access_token": (getattr(settings, "WHATSAPP_CLOUD_ACCESS_TOKEN", "") or "").strip(),
	}


def _render_structured_value(value, context: dict):
	if isinstance(value, str):
		return _render_template(value, context, fallback=value)
	if isinstance(value, list):
		return [_render_structured_value(item, context) for item in value]
	if isinstance(value, dict):
		return {key: _render_structured_value(val, context) for key, val in value.items()}
	return value


def _build_whatsapp_cloud_payload(*, job: NotificationJob, recipient_phone: str, body: str) -> tuple[dict, str]:
	normalized_to = _normalize_phone(recipient_phone)
	if not normalized_to:
		raise RuntimeError("Recipient phone is invalid.")

	context = _build_context(job)
	template = getattr(job, "template", None)
	event_payload = getattr(getattr(job, "event", None), "payload", {}) or {}
	template_config = {}
	if isinstance(getattr(template, "sample_payload", None), dict):
		template_config = template.sample_payload.get("whatsapp_template") or {}
	if isinstance(event_payload, dict) and event_payload.get("whatsapp_template"):
		template_config = event_payload.get("whatsapp_template") or template_config

	rendered_template_config = (
		_render_structured_value(template_config, context)
		if isinstance(template_config, dict) and template_config
		else {}
	)
	template_name = ""
	if isinstance(rendered_template_config, dict):
		template_name = (rendered_template_config.get("name") or "").strip()
	if not template_name:
		template_name = (getattr(template, "layout_key", "") or "").strip()

	payload = {
		"messaging_product": "whatsapp",
		"to": normalized_to,
	}
	if template_name:
		language = rendered_template_config.get("language") if isinstance(rendered_template_config, dict) else {}
		if not isinstance(language, dict):
			language = {}
		template_payload = {
			"name": template_name,
			"language": {"code": (language.get("code") or getattr(template, "locale", "en") or "en").strip()},
		}
		components = rendered_template_config.get("components") if isinstance(rendered_template_config, dict) else None
		if components:
			template_payload["components"] = components
		payload.update({
			"type": "template",
			"template": template_payload,
		})
		return payload, "template"

	payload.update({
		"type": "text",
		"text": {"preview_url": False, "body": body},
	})
	return payload, "text"


def _send_via_whatsapp_cloud(*, job: NotificationJob, recipient_phone: str, body: str) -> tuple[str, str]:
	config = _whatsapp_cloud_settings()
	if not config["phone_number_id"] or not config["access_token"]:
		raise RuntimeError(
			"WhatsApp Cloud API is not configured (WHATSAPP_CLOUD_PHONE_NUMBER_ID / WHATSAPP_CLOUD_ACCESS_TOKEN)."
		)

	request_payload, message_mode = _build_whatsapp_cloud_payload(job=job, recipient_phone=recipient_phone, body=body)
	url = f"https://graph.facebook.com/{config['api_version']}/{config['phone_number_id']}/messages"
	response = requests.post(
		url,
		headers={
			"Authorization": f"Bearer {config['access_token']}",
			"Content-Type": "application/json",
		},
		json=request_payload,
		timeout=20,
	)
	try:
		payload = response.json()
	except ValueError:
		payload = {}

	status_code = getattr(response, "status_code", 200)
	if status_code >= 400:
		error_message = payload.get("error", {}).get("message") or getattr(response, "text", "") or "Unknown error"
		raise RuntimeError(f"WhatsApp Cloud API error: {error_message}")

	messages = payload.get("messages") or []
	message_id = messages[0].get("id") if messages and isinstance(messages[0], dict) else ""
	return str(message_id or ""), message_mode


def _get_twilio_client():
	if Client is None:
		raise RuntimeError("Twilio SDK is not installed. Add the 'twilio' package to enable SMS/WhatsApp delivery.")

	config = _twilio_settings()
	if not config["sid"] or not config["token"]:
		raise RuntimeError("Twilio credentials are missing (TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN).")

	return Client(config["sid"], config["token"])


def _send_via_twilio(*, channel: str, recipient_phone: str, body: str) -> str:
	config = _twilio_settings()
	from_number = config["from_number"]
	if not from_number:
		raise RuntimeError("TWILIO_FROM_NUMBER is not configured.")

	normalized_to = _normalize_phone(recipient_phone)
	if not normalized_to:
		raise RuntimeError("Recipient phone is invalid.")

	client = _get_twilio_client()
	if channel == NotificationJob.Channel.WHATSAPP:
		whatsapp_from = config["whatsapp_from"] or from_number
		message = client.messages.create(
			body=body,
			from_=_as_whatsapp_address(whatsapp_from),
			to=_as_whatsapp_address(normalized_to),
		)
	else:
		message = client.messages.create(
			body=body,
			from_=from_number,
			to=normalized_to,
		)

	return str(getattr(message, "sid", "") or "")


@dataclass(slots=True)
class BatchDispatchResult:
	sent_count: int = 0
	failed_count: int = 0
	skipped_count: int = 0
	jobs: list[NotificationJob] = field(default_factory=list)


def _build_context(job: NotificationJob) -> dict:
	payload = getattr(getattr(job, "event", None), "payload", {}) or {}
	recipient = getattr(getattr(job, "event", None), "recipient", None)
	customer_payload = payload.get("customer") or {}
	if not isinstance(customer_payload, dict):
		customer_payload = {"name": str(customer_payload)}

	customer = {
		"name": customer_payload.get("name") or getattr(recipient, "name_snapshot", "Customer"),
		"email": customer_payload.get("email") or getattr(recipient, "email", ""),
		"phone": customer_payload.get("phone") or getattr(recipient, "phone", ""),
	}

	return {
		"payload": payload,
		"customer": customer,
		"recipient": recipient,
		"event": getattr(job, "event", None),
		"batch": getattr(job, "batch", None),
		"loans": payload.get("loans") or [],
		"loan_count": payload.get("loan_count") or len(payload.get("loans") or []),
		"total_amount": payload.get("total_amount") or "0",
		"generated_at": payload.get("generated_at") or timezone.now().isoformat(),
	}


def _render_template(template_text: str, context: dict, *, fallback: str = "") -> str:
	text = (template_text or "").strip()
	if not text:
		return fallback
	try:
		rendered = Template(text).render(Context(context)).strip()
	except Exception:
		logger.exception("notify_v2 template rendering failed")
		return fallback or text
	return rendered or fallback or text


def render_job_message(job: NotificationJob) -> tuple[str, str]:
	context = _build_context(job)
	template = getattr(job, "template", None)
	event_name = getattr(getattr(job, "event", None), "event_type", None)
	default_subject = getattr(event_name, "name", None) or "Notification"
	subject = _render_template(
		getattr(template, "subject_template", ""),
		context,
		fallback=default_subject,
	)
	body = _render_template(
		getattr(template, "body_template", ""),
		context,
		fallback=(
			"Dear {{ customer.name }}, this is an update regarding your account."
			if template is not None
			else f"Dear {context['customer']['name']}, this is a notification from us."
		),
	)
	return subject, body


def _persist_digital_artifact(job: NotificationJob, *, subject: str, body: str):
	if not getattr(job, "pk", None):
		return None
	artifact_type = (
		NotificationArtifact.ArtifactType.HTML
		if job.channel == NotificationJob.Channel.EMAIL
		else NotificationArtifact.ArtifactType.TEXT
	)
	return NotificationArtifact.objects.create(
		job=job,
		artifact_type=artifact_type,
		rendered_text=f"Subject: {subject}\n\n{body}".strip(),
		metadata={
			"channel": job.channel,
			"delivery": "digital",
		},
	)


def _record_webhook_status(job: NotificationJob, *, provider: str, external_status: str, raw_payload: dict, error_message: str = ""):
	normalized_status = (external_status or "unknown").strip().lower()
	provider_payload = {
		"provider": provider,
		"status": normalized_status,
		"raw": raw_payload or {},
	}
	if error_message:
		provider_payload["error_message"] = error_message

	previous_status = job.status
	now = timezone.now()
	if normalized_status == "failed":
		job.status = NotificationJob.Status.FAILED
		job.failure_reason = error_message or f"{provider} delivery failed."
	elif normalized_status in {"sent", "delivered", "read"} and job.status != NotificationJob.Status.CANCELLED:
		job.status = NotificationJob.Status.SENT
		job.failure_reason = ""
		if not job.sent_at:
			job.sent_at = now

	job.attempt_count += 1
	job.last_attempt_at = now
	if getattr(job, "pk", None):
		job.save(
			update_fields=[
				"status",
				"attempt_count",
				"last_attempt_at",
				"sent_at",
				"failure_reason",
				"modified",
			]
		)
		NotificationAttemptLog.objects.create(
			job=job,
			attempt_number=job.attempt_count,
			status_before=previous_status,
			status_after=job.status,
			message=f"{provider} webhook reported '{normalized_status}'.",
			provider_payload=provider_payload,
		)
	return job


def process_whatsapp_cloud_webhook(payload: dict) -> dict:
	summary = {
		"received_statuses": 0,
		"matched_jobs": 0,
		"failed_jobs": 0,
		"unknown_message_ids": [],
	}
	if not isinstance(payload, dict):
		return summary

	for entry in payload.get("entry") or []:
		for change in (entry or {}).get("changes") or []:
			value = (change or {}).get("value") or {}
			for status_event in value.get("statuses") or []:
				summary["received_statuses"] += 1
				message_id = ((status_event or {}).get("id") or "").strip()
				if not message_id:
					continue
				job = NotificationJob.objects.filter(provider_message_id=message_id).first()
				if job is None:
					summary["unknown_message_ids"].append(message_id)
					continue

				error_messages = []
				for error in status_event.get("errors") or []:
					if isinstance(error, dict) and error.get("message"):
						error_messages.append(str(error["message"]))
				error_text = "; ".join(error_messages)
				_record_webhook_status(
					job,
					provider="whatsapp_cloud",
					external_status=status_event.get("status", "unknown"),
					raw_payload=status_event,
					error_message=error_text,
				)
				summary["matched_jobs"] += 1
				if (status_event.get("status") or "").strip().lower() == "failed":
					summary["failed_jobs"] += 1

	return summary


def dispatch_job(job: NotificationJob) -> bool:
	if job.channel not in DIGITAL_CHANNELS:
		return False

	subject, body = render_job_message(job)
	recipient = getattr(getattr(job, "event", None), "recipient", None)

	if job.channel == NotificationJob.Channel.EMAIL:
		email = (getattr(recipient, "email", None) or "").strip()
		if not email:
			job.mark_failed(reason="Recipient email is missing.")
			return False
		try:
			send_mail(
				subject,
				body,
				getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@example.com"),
				[email],
				fail_silently=False,
			)
		except Exception as exc:
			logger.exception("notify_v2 email delivery failed for job=%s", getattr(job, "pk", None))
			job.mark_failed(reason=f"Email delivery failed: {exc}")
			return False

		job.provider_message_id = f"email:{getattr(job, 'pk', 'preview')}:{timezone.now():%Y%m%d%H%M%S}"
		_persist_digital_artifact(job, subject=subject, body=body)
		job.mark_sent(
			message=f"Email sent to {email}.",
			provider_payload={"provider": "django_send_mail", "recipient": email, "channel": job.channel},
		)
		return True

	phone = (getattr(recipient, "phone", None) or "").strip()
	if not phone:
		job.mark_failed(reason=f"Recipient phone is missing for {job.channel.lower()} delivery.")
		return False

	provider_name = "twilio"
	provider_payload = {
		"recipient": phone,
		"channel": job.channel,
		"preview": body[:160],
	}
	try:
		if job.channel == NotificationJob.Channel.WHATSAPP and _whatsapp_provider() == "cloud":
			sid, delivery_mode = _send_via_whatsapp_cloud(job=job, recipient_phone=phone, body=body)
			provider_name = "whatsapp_cloud"
			job.provider_message_id = sid or f"whatsapp_cloud:{job.channel.lower()}:{getattr(job, 'pk', 'preview')}"
			provider_payload["delivery_mode"] = delivery_mode
		else:
			sid = _send_via_twilio(channel=job.channel, recipient_phone=phone, body=body)
			provider_name = "twilio"
			job.provider_message_id = sid or f"twilio:{job.channel.lower()}:{getattr(job, 'pk', 'preview')}"
		provider_payload["provider"] = provider_name
	except Exception as exc:
		if not _twilio_settings()["stub_fallback"]:
			job.mark_failed(reason=f"{job.get_channel_display()} delivery failed: {exc}")
			return False

		provider_name = "stub_adapter"
		job.provider_message_id = f"stub:{job.channel.lower()}:{getattr(job, 'pk', 'preview')}"
		provider_payload["provider"] = provider_name
		provider_payload["fallback_reason"] = str(exc)

	_persist_digital_artifact(job, subject=subject, body=body)
	job.mark_sent(
		message=f"{job.get_channel_display()} dispatched via {provider_name} to {phone}.",
		provider_payload=provider_payload,
	)
	return True


def dispatch_batch_jobs(batch, *, channels=None) -> BatchDispatchResult:
	selected_channels = set(channels or DIGITAL_CHANNELS)
	jobs = list(batch.jobs.select_related("event__recipient", "event__event_type", "template").all())
	result = BatchDispatchResult(jobs=[])

	for job in jobs:
		if job.channel not in selected_channels or job.status in {
			NotificationJob.Status.SENT,
			NotificationJob.Status.CANCELLED,
		}:
			result.skipped_count += 1
			continue

		ok = dispatch_job(job)
		result.jobs.append(job)
		if ok:
			result.sent_count += 1
		else:
			result.failed_count += 1

	if result.sent_count and not result.failed_count and hasattr(batch, "mark_posted"):
		try:
			batch.mark_posted()
		except Exception:
			logger.exception("notify_v2 batch post-mark failed for batch=%s", getattr(batch, "pk", None))

	return result
