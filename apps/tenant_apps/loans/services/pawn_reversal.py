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
    PawnCollateralCustodyEvent,
    PawnCollateralItem,
    PawnLoanReleaseReversal,
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
        TransactionKind.RELEASE_RECEIPT.value,
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
    release_reversal: PawnLoanReleaseReversal | None = None
    catch_up_reversal_event: PawnLoanAccountingEvent | None = None


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
        release_reversal = _optional_release_reversal(existing)
        return PawnReversalResult(
            original,
            existing,
            existing.outbox,
            True,
            release_reversal,
            (
                release_reversal.catch_up_reversal_event
                if release_reversal
                else None
            ),
        )
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

    release = None
    custody_transitions = ()
    if original.event_kind == TransactionKind.RELEASE_RECEIPT.value:
        release, custody_transitions = _validate_release_reversal(original)

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

    release_reversal = None
    catch_up_reversal = None
    if release is not None:
        catch_up_reversal = _reverse_release_catch_up(
            release,
            effective_date=effective_date,
            reason=reason,
            actor=actor,
            delivery_handler=delivery_handler,
        )
        release_reversal = PawnLoanReleaseReversal.objects.create(
            release=release,
            accounting_event=reversal,
            catch_up_reversal_event=catch_up_reversal,
            reason=reason,
            created_by=actor,
        )
        _restore_release_custody(
            release,
            release_reversal=release_reversal,
            transitions=custody_transitions,
            effective_date=effective_date,
            actor=actor,
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
    elif release is not None and release.is_full_release:
        to_state = PawnLoanState.ACTIVE.value
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
            "release_id": release.pk if release else None,
            "release_reversal_id": (
                release_reversal.pk if release_reversal else None
            ),
            "catch_up_reversal_event_id": (
                catch_up_reversal.pk if catch_up_reversal else None
            ),
        },
    )
    return PawnReversalResult(
        original,
        reversal,
        outbox,
        False,
        release_reversal,
        catch_up_reversal,
    )


def _validate_release_reversal(original):
    try:
        release = original.release
    except ObjectDoesNotExist as exc:
        raise PawnReversalError(
            "Release accounting event is missing its immutable release document."
        ) from exc
    expected_state = (
        PawnLoanState.CLOSED.value
        if release.is_full_release
        else PawnLoanState.ACTIVE.value
    )
    if original.loan.state != expected_state:
        raise PawnReversalError(
            "PawnLoan lifecycle is incompatible with this release reversal."
        )
    original_transitions = tuple(
        release.custody_events.filter(release_reversal__isnull=True)
        .select_related("collateral_item")
        .order_by("pk")
    )
    if not original_transitions:
        raise PawnReversalError("Release has no custody handoff to reverse.")
    item_ids = [event.collateral_item_id for event in original_transitions]
    locked_items = {
        item.pk: item
        for item in PawnCollateralItem.objects.select_for_update().filter(pk__in=item_ids)
    }
    for event in original_transitions:
        item = locked_items.get(event.collateral_item_id)
        if item is None or item.loan_id != original.loan_id:
            raise PawnReversalError("Release custody history does not match its loan.")
        if item.custody_state != event.to_state:
            raise PawnReversalError(
                "Collateral custody changed after release and cannot be restored safely."
            )
    catch_up = release.catch_up_accrual
    if catch_up and catch_up.accounting_event:
        if catch_up.accounting_event.outbox.status != LoanOutboxStatus.POSTED.value:
            raise PawnReversalError(
                "Release catch-up accrual must be delivered before reversal."
            )
        if _existing_reversal(catch_up.accounting_event):
            raise PawnReversalError(
                "Release catch-up accrual was already reversed independently."
            )
    return release, tuple(
        (locked_items[event.collateral_item_id], event) for event in original_transitions
    )


def _reverse_release_catch_up(
    release,
    *,
    effective_date,
    reason,
    actor,
    delivery_handler,
):
    accrual = release.catch_up_accrual
    if not accrual or not accrual.accounting_event:
        return None
    original = accrual.accounting_event
    payload = reversal_payload(
        release.loan,
        effective_date=effective_date,
        original_event_id=original.pk,
        original_event_kind=original.event_kind,
        values=original.payload.get("values") or {},
        reason=reason,
    ).to_dict()
    payload["reversal"]["release_id"] = release.pk
    reversal, _outbox = record_loan_accounting_event(
        release.loan_id,
        event_kind=TransactionKind.REVERSAL,
        effective_date=effective_date,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
        reversal_of=original,
    )
    return reversal


def _restore_release_custody(
    release,
    *,
    release_reversal,
    transitions,
    effective_date,
    actor,
):
    for item, original in transitions:
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=item,
            release=release,
            release_reversal=release_reversal,
            from_state=original.to_state,
            to_state=original.from_state,
            effective_date=effective_date,
            actor=actor,
        )
        item.custody_state = original.from_state
        item.save(update_fields=["custody_state", "updated_at"])


def _optional_release_reversal(event):
    try:
        return event.release_reversal
    except ObjectDoesNotExist:
        return None


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
