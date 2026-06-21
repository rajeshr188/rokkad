"""Girvi outbox integration helpers for event-driven DEA posting cutover."""

from django.db import transaction

from apps.tenant_apps.girvi.models import GirviPostingOutboxEvent


def enqueue_posting_event(*, event_type, dedupe_key, payload, source_model, source_pk, contract_version=1):
    """Create or return a deterministic outbox row for Girvi posting events."""

    with transaction.atomic():
        event, _created = GirviPostingOutboxEvent.objects.get_or_create(
            dedupe_key=dedupe_key,
            defaults={
                "event_type": event_type,
                "payload": payload,
                "source_model": source_model,
                "source_pk": str(source_pk),
                "contract_version": contract_version,
            },
        )
    return event
