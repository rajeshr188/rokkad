"""Loans-owned immutable lifecycle-event recording."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date

from django.db import transaction

from apps.tenant_apps.loans.domain import TransactionKind
from apps.tenant_apps.loans.models import (
    PawnLoan,
    PawnLoanEvent,
    current_tenant_workspace_id,
)


class LoanEventRecordingError(ValueError):
    """Raised when immutable Loans event evidence cannot be recorded."""


@dataclass(frozen=True)
class EventRecordingResult:
    """Non-persistent result retained for existing tuple-returning workflows."""

    event: PawnLoanEvent
    status: str = "RECORDED"
    pk: None = None

    @property
    def event_id(self):
        return self.event.pk

    def get_status_display(self):
        return "Recorded"


def event_recording_result(event: PawnLoanEvent) -> EventRecordingResult:
    return EventRecordingResult(event=event)


def record_loan_event(
    loan_id: int,
    *,
    event_kind: TransactionKind | str,
    effective_date: date,
    payload: dict,
    actor=None,
    reversal_of: PawnLoanEvent | None = None,
) -> tuple[PawnLoanEvent, EventRecordingResult]:
    """Persist immutable Loans evidence without an external side effect."""
    kind = TransactionKind(event_kind).value
    _require_payload(payload)
    with transaction.atomic():
        loan = _locked_loan(loan_id)
        fingerprint = _fingerprint(payload)
        idempotency_key = f"loans:{loan.pk}:{kind}:{fingerprint}"
        event, _created = PawnLoanEvent.objects.get_or_create(
            idempotency_key=idempotency_key,
            defaults={
                "loan": loan,
                "event_kind": kind,
                "effective_date": effective_date,
                "payload": payload,
                "payload_fingerprint": fingerprint,
                "created_by": actor,
                "reversal_of": reversal_of,
            },
        )
        return event, event_recording_result(event)


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise LoanEventRecordingError("Loan events require an active workspace.")
    try:
        return PawnLoan.objects.select_for_update().get(
            pk=loan_id,
            workspace_id=workspace_id,
        )
    except PawnLoan.DoesNotExist as exc:
        raise LoanEventRecordingError(
            "PawnLoan was not found in the active workspace."
        ) from exc


def _require_payload(payload):
    if not isinstance(payload, dict) or not payload:
        raise LoanEventRecordingError("Loan event payload must be a non-empty object.")
    try:
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise LoanEventRecordingError(
            "Loan event payload must be JSON serializable."
        ) from exc


def _fingerprint(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
