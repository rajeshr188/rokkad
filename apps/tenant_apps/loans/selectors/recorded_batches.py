"""Retained original batch plus its most recently reviewed collection figures."""
from copy import copy
from decimal import Decimal

from apps.tenant_apps.loans.models import PawnLoanEvent
from .recorded_settlements import restated_release


def batch_correction_event(batch):
    return PawnLoanEvent.objects.filter(workspace_id=batch.workspace_id, event_kind="RELEASE_RECEIPT",
        payload__history_correction__role="SETTLEMENT",
        payload__history_correction__batch_correction__schema="recorded-batch-correction/1",
        payload__history_correction__batch_correction__id=batch.pk).order_by("-pk").first()


def batch_financial_review(batch):
    rows = []
    for line in batch.lines.select_related("release__loan", "release__loan_event", "release__reversal").order_by("pk"):
        projected = copy(line)
        projected.release = restated_release(line.release)
        rows.append(projected)
    event = batch_correction_event(batch)
    evidence = event.payload["history_correction"]["batch_correction"] if event else None
    return dict(lines=rows, correction=event, evidence=evidence,
        total=Decimal(evidence["total_received"]) if evidence else batch.total_amount,
        reversed=any(hasattr(line.release, "reversal") for line in rows))
