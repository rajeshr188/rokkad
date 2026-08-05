"""PawnLoan auction/recovery commands with custody and accounting evidence."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Max
from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone

from apps.orgs.permissions import get_workspace_role_name, is_platform_admin
from apps.tenant_apps.loans.domain import (
    AccountingRecognition,
    CollateralCustodyState,
    PawnLoanAuctionState,
    PawnLoanEventKind,
    PawnLoanNoticeChannel,
    PawnLoanNoticeKind,
    PawnLoanNoticeStatus,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.integrations import (
    accrual_payload,
    auction_recovery_payload,
    reversal_payload,
)
from apps.tenant_apps.loans.integrations.notice_delivery import get_pawn_notice_delivery_states
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    PawnCollateralCustodyEvent,
    PawnCollateralItem,
    PawnLoan,
    PawnLoanAccountingEvent,
    PawnLoanAccountingOutbox,
    PawnLoanAuction,
    PawnLoanAuctionItem,
    PawnLoanAuctionReversal,
    PawnLoanInterestAccrual,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.loans.services.accounting_outbox import DeliveryHandler, record_loan_accounting_event
from apps.tenant_apps.loans.services.accounting_readiness import require_pawn_loan_accounting_readiness
from apps.tenant_apps.loans.services.pawn_disbursal import assert_pawn_loan_financial_actions_allowed
from apps.tenant_apps.loans.services.pawn_interest import (
    build_pawn_accrual_detail,
    persist_pawn_accrual_lines,
    preview_pawn_loan_accruals,
    should_record_pawn_accrual_event,
)
from apps.tenant_apps.loans.services.pawn_notices import create_pawn_loan_notice


class PawnAuctionError(ValueError):
    pass


@dataclass(frozen=True)
class PawnAuctionCompletionResult:
    loan: PawnLoan
    auction: PawnLoanAuction
    accounting_event: PawnLoanAccountingEvent
    outbox: PawnLoanAccountingOutbox
    already_completed: bool = False


@dataclass(frozen=True)
class PawnAuctionReversalResult:
    auction: PawnLoanAuction
    reversal: PawnLoanAuctionReversal
    recovery_reversal_event: PawnLoanAccountingEvent
    catch_up_reversal_event: PawnLoanAccountingEvent | None
    already_reversed: bool = False


@transaction.atomic
def initiate_pawn_loan_auction(
    loan_id: int,
    *,
    scheduled_date: date,
    channel=PawnLoanNoticeChannel.SMS,
    request_key: str,
    actor,
) -> PawnLoanAuction:
    loan = _locked_loan(loan_id)
    _require_administrator(actor, loan.workspace)
    request_key = _request_key(request_key)
    existing = loan.auctions.filter(request_key=request_key).first()
    if existing:
        if existing.scheduled_date != scheduled_date:
            raise PawnAuctionError("Auction request key was reused with a different date.")
        return existing
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnAuctionError("Only an active PawnLoan can enter auction recovery.")
    notice_date = timezone.localdate()
    if scheduled_date <= notice_date:
        raise PawnAuctionError("Auction date must be after the notice date.")
    try:
        assert_pawn_loan_financial_actions_allowed(loan.pk)
        balance = get_pawn_loan_balance(loan.pk, as_of_date=notice_date)
    except ObjectDoesNotExist as exc:
        raise PawnAuctionError(str(exc)) from exc
    if not balance.is_overdue:
        raise PawnAuctionError("Only an overdue PawnLoan can enter auction recovery.")
    if loan.auctions.filter(
        state__in=(
            PawnLoanAuctionState.INITIATED.value,
            PawnLoanAuctionState.IN_PROGRESS.value,
        )
    ).exists():
        raise PawnAuctionError("This PawnLoan already has an active auction process.")
    collateral = tuple(PawnCollateralItem.objects.select_for_update().filter(loan=loan))
    if not collateral or any(
        item.custody_state != CollateralCustodyState.IN_VAULT.value
        for item in collateral
    ):
        raise PawnAuctionError("Every collateral item must be in the vault before auction.")
    attempt = (
        loan.auctions.aggregate(value=Max("attempt_number"))["value"] or 0
    ) + 1
    auction = PawnLoanAuction.objects.create(
        workspace=loan.workspace,
        loan=loan,
        auction_number=f"AUC-{loan.loan_number}-{attempt:02d}",
        attempt_number=attempt,
        request_key=request_key,
        notice_date=notice_date,
        scheduled_date=scheduled_date,
        created_by=actor,
    )
    create_pawn_loan_notice(
        loan.pk,
        notice_kind=PawnLoanNoticeKind.AUCTION_NOTICE,
        channel=channel,
        request_key=f"auction-notice:{auction.pk}",
        actor=actor,
        source_auction_id=auction.pk,
    )
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.AUCTION_INITIATED.value,
        from_state=loan.state,
        to_state=loan.state,
        actor=actor,
        metadata={
            "auction_id": auction.pk,
            "auction_number": auction.auction_number,
            "scheduled_date": scheduled_date.isoformat(),
        },
    )
    return auction


@transaction.atomic
def start_pawn_loan_auction(auction_id: int, *, actor) -> PawnLoanAuction:
    auction = _locked_auction(auction_id)
    _require_administrator(actor, auction.workspace)
    if auction.state == PawnLoanAuctionState.IN_PROGRESS.value:
        return auction
    if auction.state != PawnLoanAuctionState.INITIATED.value:
        raise PawnAuctionError("Only an initiated auction can be started.")
    if timezone.localdate() < auction.scheduled_date:
        raise PawnAuctionError("Auction cannot start before its scheduled date.")
    try:
        notice = auction.notice
    except Exception as exc:
        raise PawnAuctionError("Auction notice evidence is missing.") from exc
    delivery = get_pawn_notice_delivery_states([notice.notification_job_id]).get(
        notice.notification_job_id
    )
    if delivery is None or delivery.status != PawnLoanNoticeStatus.SENT.value:
        raise PawnAuctionError("Auction notice must be sent before the auction starts.")
    auction.state = PawnLoanAuctionState.IN_PROGRESS.value
    auction.started_at = timezone.now()
    auction.save(update_fields=["state", "started_at", "updated_at"])
    _audit(auction, PawnLoanEventKind.AUCTION_STARTED, actor)
    return auction


@transaction.atomic
def cancel_pawn_loan_auction(auction_id: int, *, reason: str, actor) -> PawnLoanAuction:
    auction = _locked_auction(auction_id)
    _require_administrator(actor, auction.workspace)
    reason = str(reason or "").strip()
    if not reason:
        raise PawnAuctionError("Auction cancellation requires a reason.")
    if auction.state == PawnLoanAuctionState.CANCELLED.value:
        if auction.cancellation_reason != reason:
            raise PawnAuctionError("Auction was already cancelled with a different reason.")
        return auction
    if auction.state not in {
        PawnLoanAuctionState.INITIATED.value,
        PawnLoanAuctionState.IN_PROGRESS.value,
    }:
        raise PawnAuctionError("Only an open auction can be cancelled.")
    auction.state = PawnLoanAuctionState.CANCELLED.value
    auction.cancelled_at = timezone.now()
    auction.cancellation_reason = reason
    auction.save(update_fields=["state", "cancelled_at", "cancellation_reason", "updated_at"])
    _audit(auction, PawnLoanEventKind.AUCTION_CANCELLED, actor, reason=reason)
    return auction


@transaction.atomic
def complete_pawn_loan_auction(
    auction_id: int,
    *,
    recovery_amount,
    buyer_name: str,
    buyer_reference: str = "",
    actor,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnAuctionCompletionResult:
    auction = _locked_auction(auction_id)
    loan = auction.loan
    _require_administrator(actor, auction.workspace)
    amount = _money(recovery_amount, loan)
    buyer_name = str(buyer_name or "").strip()
    if not buyer_name:
        raise PawnAuctionError("Auction completion requires the buyer name.")
    if auction.state == PawnLoanAuctionState.COMPLETED.value:
        if auction.recovery_amount != amount or auction.buyer_name != buyer_name:
            raise PawnAuctionError("Completed auction instructions do not match recorded evidence.")
        return PawnAuctionCompletionResult(
            loan, auction, auction.accounting_event, auction.accounting_event.outbox, True
        )
    if auction.state != PawnLoanAuctionState.IN_PROGRESS.value:
        raise PawnAuctionError("Only an auction in progress can be completed.")
    effective_date = timezone.localdate()
    collateral = tuple(PawnCollateralItem.objects.select_for_update().filter(loan=loan))
    if not collateral or any(item.custody_state != CollateralCustodyState.IN_VAULT.value for item in collateral):
        raise PawnAuctionError("Every collateral item must remain in the vault until completion.")
    try:
        assert_pawn_loan_financial_actions_allowed(loan.pk)
        missing = preview_pawn_loan_accruals(loan.pk, as_of_date=effective_date, include_partial=False)
        if missing:
            raise PawnAuctionError("Finalize every completed interest period before auction completion.")
        partials = preview_pawn_loan_accruals(loan.pk, as_of_date=effective_date, include_partial=True)
        partial = partials[0] if partials and partials[0].is_partial else None
        catch_up = _record_auction_accrual(
            loan,
            preview=partial,
            actor=actor,
            delivery_handler=delivery_handler,
        ) if partial else None
        balance = get_pawn_loan_balance(loan.pk, as_of_date=effective_date)
        if amount != balance.total_due:
            raise PawnAuctionError(
                "Auction recovery must exactly clear the current debt of "
                f"{balance.total_due}; shortfall write-off and surplus distribution are not supported yet."
            )
        require_pawn_loan_accounting_readiness(
            loan,
            effective_date=effective_date,
            requires_fee_income=balance.fees_outstanding > 0,
            requires_interest_receivable=(
                loan.policy_snapshot.accounting_recognition == AccountingRecognition.ACCRUAL.value
                and balance.interest_outstanding > 0
            ),
            requires_unearned_interest=(
                loan.policy_snapshot.accounting_recognition
                == AccountingRecognition.ACCRUAL.value
                and partial is not None
                and partial.advance_interest_applied > 0
            ),
        )
    except PawnAuctionError:
        raise
    except Exception as exc:
        raise PawnAuctionError(str(exc)) from exc
    capitalized = min(
        balance.principal_outstanding,
        balance.capitalized_interest_principal_outstanding,
    )
    payload = auction_recovery_payload(
        loan,
        effective_date=effective_date,
        principal_amount=balance.principal_outstanding,
        interest_amount=balance.interest_outstanding,
        fee_amount=balance.fees_outstanding,
        original_principal_amount=balance.principal_outstanding - capitalized,
        capitalized_interest_principal_amount=capitalized,
    ).to_dict()
    payload["auction"] = {
        "auction_id": auction.pk,
        "auction_number": auction.auction_number,
        "buyer_name": buyer_name,
        "buyer_reference": str(buyer_reference or "").strip(),
        "accounting_recognition": loan.policy_snapshot.accounting_recognition,
        "full_debt_recovery": True,
    }
    event, outbox = record_loan_accounting_event(
        loan.pk,
        event_kind=TransactionKind.AUCTION_RECOVERY,
        effective_date=effective_date,
        payload=payload,
        actor=actor,
        delivery_handler=delivery_handler,
    )
    now = timezone.now()
    auction.state = PawnLoanAuctionState.COMPLETED.value
    auction.completed_at = now
    auction.buyer_name = buyer_name
    auction.buyer_reference = str(buyer_reference or "").strip()
    auction.recovery_amount = amount
    auction.principal_amount = balance.principal_outstanding
    auction.interest_amount = balance.interest_outstanding
    auction.fee_amount = balance.fees_outstanding
    auction.accounting_event = event
    auction.catch_up_accrual = catch_up
    auction.save()
    for item in collateral:
        PawnLoanAuctionItem.objects.create(
            auction=auction,
            collateral_item=item,
            snapshot={
                "description": item.description,
                "metal": item.metal,
                "gross_weight": str(item.gross_weight),
                "net_weight": str(item.net_weight),
                "purity_percentage": str(item.purity_percentage),
                "latest_appraised_value": str(item.latest_appraised_value) if item.latest_appraised_value is not None else None,
            },
            disposed_at=now,
        )
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=item,
            auction=auction,
            from_state=CollateralCustodyState.IN_VAULT.value,
            to_state=CollateralCustodyState.AUCTION_DISPOSED.value,
            effective_date=effective_date,
            actor=actor,
        )
        item.custody_state = CollateralCustodyState.AUCTION_DISPOSED.value
        item.save(update_fields=["custody_state", "updated_at"])
    loan.state = PawnLoanState.CLOSED.value
    loan.updated_by = actor
    loan.save(update_fields=["state", "updated_by", "updated_at"])
    _audit(
        auction,
        PawnLoanEventKind.AUCTION_COMPLETED,
        actor,
        from_state=PawnLoanState.ACTIVE.value,
        to_state=PawnLoanState.CLOSED.value,
        metadata={"accounting_event_id": event.pk, "outbox_id": outbox.pk},
    )
    return PawnAuctionCompletionResult(loan, auction, event, outbox)


@transaction.atomic
def reverse_pawn_loan_auction(
    auction_id: int,
    *,
    reason: str,
    actor,
    delivery_handler: DeliveryHandler | None = None,
) -> PawnAuctionReversalResult:
    auction = _locked_auction(auction_id)
    _require_administrator(actor, auction.workspace)
    reason = str(reason or "").strip()
    if not reason:
        raise PawnAuctionError("Auction reversal requires a reason.")
    try:
        existing = auction.reversal
    except ObjectDoesNotExist:
        existing = None
    if existing:
        if existing.reason != reason:
            raise PawnAuctionError("Auction was already reversed with a different reason.")
        return PawnAuctionReversalResult(
            auction,
            existing,
            existing.accounting_event,
            existing.catch_up_reversal_event,
            True,
        )
    if auction.state != PawnLoanAuctionState.COMPLETED.value or not auction.accounting_event_id:
        raise PawnAuctionError("Only a completed auction can be reversed.")
    if auction.loan.state != PawnLoanState.CLOSED.value:
        raise PawnAuctionError("Auction reversal requires the loan to remain closed.")
    items = tuple(
        PawnCollateralItem.objects.select_for_update().filter(
            auction_items__auction=auction
        )
    )
    if not items or any(
        item.custody_state != CollateralCustodyState.AUCTION_DISPOSED.value
        for item in items
    ):
        raise PawnAuctionError("Collateral custody changed after auction and cannot be restored safely.")
    from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event

    recovery_result = reverse_pawn_loan_event(
        auction.accounting_event_id,
        reason=reason,
        actor=actor,
        delivery_handler=delivery_handler,
        allow_auction_recovery=True,
    )
    catch_up_reversal_event = None
    if auction.catch_up_accrual_id and auction.catch_up_accrual.accounting_event_id:
        original = auction.catch_up_accrual.accounting_event
        payload = reversal_payload(
            auction.loan,
            effective_date=timezone.localdate(),
            original_event_id=original.pk,
            original_event_kind=original.event_kind,
            values=original.payload.get("values") or {},
            reason=reason,
        ).to_dict()
        payload["reversal"]["auction_id"] = auction.pk
        catch_up_reversal_event, _ = record_loan_accounting_event(
            auction.loan_id,
            event_kind=TransactionKind.REVERSAL,
            effective_date=timezone.localdate(),
            payload=payload,
            actor=actor,
            delivery_handler=delivery_handler,
            reversal_of=original,
        )
    reversal = PawnLoanAuctionReversal.objects.create(
        auction=auction,
        accounting_event=recovery_result.reversal_event,
        catch_up_reversal_event=(
            catch_up_reversal_event
        ),
        reason=reason,
        created_by=actor,
    )
    effective_date = timezone.localdate()
    for item in items:
        PawnCollateralCustodyEvent.objects.create(
            collateral_item=item,
            auction=auction,
            auction_reversal=reversal,
            from_state=CollateralCustodyState.AUCTION_DISPOSED.value,
            to_state=CollateralCustodyState.IN_VAULT.value,
            effective_date=effective_date,
            actor=actor,
        )
        item.custody_state = CollateralCustodyState.IN_VAULT.value
        item.save(update_fields=["custody_state", "updated_at"])
    auction.loan.state = PawnLoanState.ACTIVE.value
    auction.loan.updated_by = actor
    auction.loan.save(update_fields=["state", "updated_by", "updated_at"])
    _audit(
        auction,
        PawnLoanEventKind.AUCTION_REVERSED,
        actor,
        reason=reason,
        from_state=PawnLoanState.CLOSED.value,
        to_state=PawnLoanState.ACTIVE.value,
        metadata={"auction_reversal_id": reversal.pk},
    )
    return PawnAuctionReversalResult(
        auction,
        reversal,
        recovery_result.reversal_event,
        catch_up_reversal_event,
    )


def _record_auction_accrual(loan, *, preview, actor, delivery_handler):
    policy = loan.policy_snapshot
    event = None
    outbox = None
    if should_record_pawn_accrual_event(preview, policy):
        payload = accrual_payload(
            loan,
            effective_date=preview.period_end,
            interest_amount=preview.recognized_interest,
            advance_interest_applied=preview.advance_interest_applied,
        ).to_dict()
        payload["accrual"] = build_pawn_accrual_detail(preview, policy)
        payload["accrual"]["auction_catch_up"] = True
        event, outbox = record_loan_accounting_event(
            loan.pk,
            event_kind=TransactionKind.INTEREST_ACCRUAL,
            effective_date=preview.period_end,
            payload=payload,
            actor=actor,
            delivery_handler=delivery_handler,
        )
    accrual = PawnLoanInterestAccrual.objects.create(
        loan=loan,
        period_number=preview.period_number,
        period_start=preview.period_start,
        period_end=preview.period_end,
        period_fraction=preview.period_fraction,
        calculation_base=preview.calculation_base,
        unrounded_interest=preview.unrounded_interest,
        recognized_interest=preview.recognized_interest,
        accounting_event=event,
        finalized_by=actor,
    )
    persist_pawn_accrual_lines(accrual, preview)
    LoanChangeLog.objects.create(
        loan=loan,
        event_kind=PawnLoanEventKind.ACCRUAL_FINALIZED.value,
        from_state=loan.state,
        to_state=loan.state,
        actor=actor,
        metadata={
            "period_number": preview.period_number,
            "recognized_interest": str(preview.recognized_interest),
            "auction_catch_up": True,
            "accounting_event_id": event.pk if event else None,
            "outbox_id": outbox.pk if outbox else None,
        },
    )
    return accrual


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnAuctionError("PawnLoan auction requires an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_for_update(of=("self",))
            .select_related("workspace", "borrower", "policy_snapshot")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnAuctionError("PawnLoan was not found in the active workspace.") from exc


def _locked_auction(auction_id):
    workspace_id = current_tenant_workspace_id()
    try:
        return (
            PawnLoanAuction.objects.select_for_update(of=("self",))
            .select_related("workspace", "loan", "loan__policy_snapshot", "loan__borrower")
            .get(pk=auction_id, workspace_id=workspace_id)
        )
    except PawnLoanAuction.DoesNotExist as exc:
        raise PawnAuctionError("PawnLoan auction was not found in the active workspace.") from exc


def _request_key(value):
    value = str(value or "").strip()
    if not value or len(value) > 120:
        raise PawnAuctionError("An auction request key of at most 120 characters is required.")
    return value


def _money(value, loan):
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise PawnAuctionError("Recovery amount must be a valid number.") from exc
    quantum = Decimal(str(loan.policy_snapshot.currency_quantum))
    if amount <= 0 or amount != amount.quantize(quantum):
        raise PawnAuctionError(f"Recovery amount must be positive and use precision {quantum}.")
    return amount


def _require_administrator(actor, workspace):
    if actor is None or not getattr(actor, "is_authenticated", False):
        raise PawnAuctionError("PawnLoan auction requires an administrator.")
    if is_platform_admin(actor) or workspace.owner_id == actor.pk or get_workspace_role_name(actor, workspace) in {"Owner", "Admin"}:
        return
    raise PawnAuctionError("PawnLoan auction requires an administrator.")


def _audit(auction, event_kind, actor, *, reason="", from_state=None, to_state=None, metadata=None):
    LoanChangeLog.objects.create(
        loan=auction.loan,
        event_kind=event_kind.value,
        from_state=from_state or auction.loan.state,
        to_state=to_state or auction.loan.state,
        reason=reason,
        actor=actor,
        metadata={"auction_id": auction.pk, "auction_number": auction.auction_number, **(metadata or {})},
    )


__all__ = [
    "PawnAuctionCompletionResult",
    "PawnAuctionError",
    "PawnAuctionReversalResult",
    "cancel_pawn_loan_auction",
    "complete_pawn_loan_auction",
    "initiate_pawn_loan_auction",
    "reverse_pawn_loan_auction",
    "start_pawn_loan_auction",
]
