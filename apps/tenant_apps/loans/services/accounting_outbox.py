from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Callable

from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.domain import LoanOutboxStatus, TransactionKind
from apps.tenant_apps.loans.models import (
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    current_tenant_workspace_id,
)


class LoanAccountingOutboxError(ValueError):
    """Raised for invalid accounting event or delivery operations."""


@dataclass(frozen=True)
class DeliveryReceipt:
    dea_voucher_id: int | None = None
    dea_journal_entry_id: int | None = None


DeliveryHandler = Callable[[PawnLoanAccountingEvent], DeliveryReceipt]


def record_loan_accounting_event(
    loan_id: int,
    *,
    event_kind: TransactionKind | str,
    effective_date: date,
    payload: dict,
    actor=None,
    delivery_handler: DeliveryHandler | None = None,
    reversal_of: PawnLoanAccountingEvent | None = None,
) -> tuple[PawnLoanAccountingEvent, PawnLoanAccountingOutbox]:
    """Persist source intent and outbox atomically, then attempt delivery on commit."""
    kind = TransactionKind(event_kind).value
    _require_payload(payload)
    with transaction.atomic():
        loan = _locked_loan(loan_id)
        fingerprint = _fingerprint(payload)
        idempotency_key = f"loans:{loan.pk}:{kind}:{fingerprint}"
        event, created = PawnLoanAccountingEvent.objects.get_or_create(
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
        outbox, outbox_created = PawnLoanAccountingOutbox.objects.get_or_create(
            event=event,
            defaults={
                "idempotency_key": idempotency_key,
                "payload": payload,
                "payload_fingerprint": fingerprint,
            },
        )
        if not created and not outbox_created:
            return event, outbox
        transaction.on_commit(
            lambda: deliver_outbox_event(
                outbox.pk,
                delivery_handler=delivery_handler,
            )
        )
        return event, outbox


@transaction.atomic
def deliver_outbox_event(
    outbox_id: int, *, delivery_handler: DeliveryHandler | None = None
) -> PawnLoanAccountingOutbox:
    try:
        outbox = PawnLoanAccountingOutbox.objects.select_for_update().select_related(
            "event", "event__loan"
        ).get(pk=outbox_id)
    except PawnLoanAccountingOutbox.DoesNotExist as exc:
        raise LoanAccountingOutboxError("Accounting outbox event was not found.") from exc
    if outbox.status == LoanOutboxStatus.POSTED.value:
        return outbox
    if outbox.status == LoanOutboxStatus.PROCESSING.value:
        raise LoanAccountingOutboxError("Accounting outbox event is already processing.")

    outbox.status = LoanOutboxStatus.PROCESSING.value
    outbox.claimed_at = timezone.now()
    outbox.attempt_count += 1
    outbox.save(update_fields=["status", "claimed_at", "attempt_count", "updated_at"])
    try:
        receipt = (delivery_handler or _default_delivery)(outbox.event)
    except Exception as exc:  # Delivery failures are durable, never swallowed.
        outbox.status = LoanOutboxStatus.FAILED.value
        outbox.last_error = str(exc)[:4000]
        outbox.save(update_fields=["status", "last_error", "updated_at"])
        return outbox

    outbox.status = LoanOutboxStatus.POSTED.value
    outbox.delivered_at = timezone.now()
    outbox.last_error = ""
    outbox.dea_voucher_id = receipt.dea_voucher_id
    outbox.dea_journal_entry_id = receipt.dea_journal_entry_id
    outbox.save(
        update_fields=[
            "status",
            "delivered_at",
            "last_error",
            "dea_voucher_id",
            "dea_journal_entry_id",
            "updated_at",
        ]
    )
    return outbox


@transaction.atomic
def retry_failed_outbox_event(
    outbox_id: int, *, delivery_handler: DeliveryHandler | None = None
) -> PawnLoanAccountingOutbox:
    try:
        outbox = PawnLoanAccountingOutbox.objects.select_for_update().get(pk=outbox_id)
    except PawnLoanAccountingOutbox.DoesNotExist as exc:
        raise LoanAccountingOutboxError("Accounting outbox event was not found.") from exc
    if outbox.status != LoanOutboxStatus.FAILED.value:
        raise LoanAccountingOutboxError("Only failed accounting outbox events can be retried.")
    outbox.status = LoanOutboxStatus.PENDING.value
    outbox.available_at = timezone.now()
    outbox.claimed_at = None
    outbox.last_error = ""
    outbox.save(
        update_fields=["status", "available_at", "claimed_at", "last_error", "updated_at"]
    )
    transaction.on_commit(
        lambda: deliver_outbox_event(outbox.pk, delivery_handler=delivery_handler)
    )
    return outbox


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise LoanAccountingOutboxError("Accounting events require an active tenant schema.")
    try:
        return PawnLoan.objects.select_for_update().get(pk=loan_id, workspace_id=workspace_id)
    except PawnLoan.DoesNotExist as exc:
        raise LoanAccountingOutboxError("PawnLoan was not found in the active workspace.") from exc


def _require_payload(payload):
    if not isinstance(payload, dict) or not payload:
        raise LoanAccountingOutboxError("Accounting event payload must be a non-empty object.")
    try:
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise LoanAccountingOutboxError("Accounting event payload must be JSON serializable.") from exc


def _fingerprint(payload):
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _default_delivery(event):
    from apps.tenant_apps.loans.integrations.dea_delivery import (
        deliver_loan_accounting_event,
    )

    return deliver_loan_accounting_event(event)
