"""Strict newest-first PawnLoan accounting-event reversal workflow."""

from dataclasses import dataclass
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.utils import timezone

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.tenant_apps.loans.domain import (
    LoanOutboxStatus,
    PawnLoanEventKind,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations import reversal_payload
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    PawnLoanAccountingEvent,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.services.accounting_outbox import (
    DeliveryHandler,
    record_loan_accounting_event,
)
from apps.tenant_apps.loans.services.pawn_disbursal import (
    assert_pawn_loan_financial_actions_allowed,
)


REVERSIBLE_EVENT_KINDS = frozenset(
    {
        TransactionKind.DISBURSAL.value,
        TransactionKind.REPAYMENT.value,
        TransactionKind.INTEREST_ACCRUAL.value,
        TransactionKind.INTEREST_CAPITALIZATION.value,
    }
)


class PawnReversalError(ValueError):
    pass


@dataclass(frozen=True)
class PawnReversalResult:
    original_event: PawnLoanAccountingEvent
    reversal_event: PawnLoanAccountingEvent
    outbox: object
    already_reversed: bool = False


@transaction.atomic
def reverse_pawn_loan_event(
    original_event_id: int,
    *,
    reason: str,
    actor,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnReversalResult:
    original = _locked_original_event(original_event_id)
    _require_administrator(actor, original.loan.workspace)
    reason = str(reason or "").strip()
    if not reason:
        raise PawnReversalError("A reversal reason is required.")
    if original.event_kind not in REVERSIBLE_EVENT_KINDS:
        raise PawnReversalError("This PawnLoan event kind cannot be reversed.")

    existing = _existing_reversal(original)
    if existing:
        recorded_reason = (existing.payload.get("reversal") or {}).get("reason", "")
        if recorded_reason != reason:
            raise PawnReversalError(
                "This event is already reversed with a different reason."
            )
        return PawnReversalResult(original, existing, existing.outbox, True)
    if original.outbox.status != LoanOutboxStatus.POSTED.value:
        raise PawnReversalError(
            "Only a successfully delivered PawnLoan event can be reversed."
        )

    try:
        assert_pawn_loan_financial_actions_allowed(original.loan_id)
    except Exception as exc:
        raise PawnReversalError(str(exc)) from exc
    latest = (
        original.loan.accounting_events.exclude(
            event_kind=TransactionKind.REVERSAL.value
        )
        .filter(reversed_by_event__isnull=True)
        .order_by("-effective_date", "-pk")
        .first()
    )
    if latest is None or latest.pk != original.pk:
        raise PawnReversalError(
            "Later dependent events must be reversed first in reverse chronological order."
        )

    effective_date = timezone.localdate()
    payload = reversal_payload(
        original.loan,
        effective_date=effective_date,
        original_event_id=original.pk,
        original_event_kind=original.event_kind,
        values=original.payload.get("values") or {},
        reason=reason,
    ).to_dict()
    payload["reversal"]["original_idempotency_key"] = original.idempotency_key
    payload["reversal"]["original_effective_date"] = (
        original.effective_date.isoformat()
    )
    reversal, outbox = record_loan_accounting_event(
        original.loan_id,
        event_kind=TransactionKind.REVERSAL,
        effective_date=effective_date,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
        reversal_of=original,
    )

    from_state = original.loan.state
    to_state = from_state
    if original.event_kind == TransactionKind.DISBURSAL.value:
        if from_state != PawnLoanState.ACTIVE.value:
            raise PawnReversalError(
                "Disbursal reversal requires the PawnLoan to remain active."
            )
        to_state = PawnLoanState.APPROVED.value
        original.loan.state = to_state
        original.loan.updated_by = actor
        original.loan.save(update_fields=["state", "updated_by", "updated_at"])

    LoanChangeLog.objects.create(
        loan=original.loan,
        event_kind=PawnLoanEventKind.REVERSAL_RECORDED.value,
        from_state=from_state,
        to_state=to_state,
        reason=reason,
        actor=actor,
        metadata={
            "original_event_id": original.pk,
            "original_event_kind": original.event_kind,
            "reversal_event_id": reversal.pk,
            "outbox_id": outbox.pk,
            "effective_date": effective_date.isoformat(),
        },
    )
    return PawnReversalResult(original, reversal, outbox)


def _locked_original_event(event_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnReversalError("PawnLoan reversal requires an active tenant schema.")
    try:
        return (
            PawnLoanAccountingEvent.objects.select_for_update()
            .select_related("loan", "loan__workspace")
            .get(pk=event_id, loan__workspace_id=workspace_id)
        )
    except PawnLoanAccountingEvent.DoesNotExist as exc:
        raise PawnReversalError(
            "PawnLoan accounting event was not found in the active workspace."
        ) from exc


def _existing_reversal(original):
    try:
        return original.reversed_by_event
    except ObjectDoesNotExist:
        return None


def _require_administrator(actor, workspace):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PawnReversalError("PawnLoan reversal requires an administrator.")
    if (
        is_platform_admin(actor)
        or workspace.owner_id == actor.pk
        or get_workspace_role_name(actor, workspace) in {"Owner", "Admin"}
    ):
        return
    raise PawnReversalError("PawnLoan reversal requires an administrator.")
