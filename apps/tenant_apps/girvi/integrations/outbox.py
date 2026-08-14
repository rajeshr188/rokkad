"""Girvi outbox integration helpers for event-driven DEA posting cutover."""

from django.db import transaction

from apps.tenant_apps.girvi.models import GirviPostingOutboxEvent


class GirviPostingConflictError(ValueError):
    """Raised when one Girvi idempotency key is reused for different intent."""


def enqueue_posting_event(*, event_type, dedupe_key, payload, source_model, source_pk, contract_version=1):
    """Create or return a deterministic outbox row for Girvi posting events."""

    event, _created = record_posting_event(
        event_type=event_type,
        dedupe_key=dedupe_key,
        payload=payload,
        source_model=source_model,
        source_pk=source_pk,
        contract_version=contract_version,
    )
    return event


def record_posting_event(*, event_type, dedupe_key, payload, source_model, source_pk, contract_version=1):
    """Create or return a deterministic outbox row and its creation state."""

    with transaction.atomic():
        event, created = GirviPostingOutboxEvent.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "event_type": event_type,
                "payload": payload,
                "source_model": source_model,
                "source_pk": str(source_pk),
                "contract_version": contract_version,
            },
        )
        if not created:
            expected = {
                "event_type": event_type,
                "payload": payload,
                "source_model": source_model,
                "source_pk": str(source_pk),
                "contract_version": contract_version,
            }
            conflicts = [
                field_name
                for field_name, expected_value in expected.items()
                if getattr(event, field_name) != expected_value
            ]
            if conflicts:
                raise GirviPostingConflictError(
                    "Girvi posting idempotency key was reused with different "
                    f"fields: {', '.join(conflicts)}."
                )
    return event, created
