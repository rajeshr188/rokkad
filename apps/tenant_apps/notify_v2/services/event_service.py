from __future__ import annotations

from apps.tenant_apps.notify_v2.models import NotificationEvent, NotificationEventType


def emit_event(
    *,
    recipient,
    event_key: str | None = None,
    event_type: NotificationEventType | None = None,
    payload: dict | None = None,
    batch=None,
    source_app: str = "",
    source_model: str = "",
    source_pk: str | int | None = "",
    dedupe_key: str = "",
):
    """Create a normalized notification event record for downstream processing."""
    if event_type is None:
        if not event_key:
            raise ValueError("Either event_type or event_key is required.")
        event_type = NotificationEventType.objects.get(key=event_key, is_active=True)

    if batch is not None and batch.event_type_id != event_type.id:
        raise ValueError("Batch event type must match the emitted event type.")

    payload = payload or {}
    source_pk_value = "" if source_pk is None else str(source_pk)
    if not dedupe_key:
        dedupe_key = ":".join(
            part
            for part in [
                event_type.key,
                str(getattr(recipient, "pk", "")),
                source_app,
                source_model,
                source_pk_value,
            ]
            if part
        )

    return NotificationEvent.objects.create(
        event_type=event_type,
        recipient=recipient,
        batch=batch,
        source_app=source_app,
        source_model=source_model,
        source_pk=source_pk_value,
        payload=payload,
        dedupe_key=dedupe_key,
    )
