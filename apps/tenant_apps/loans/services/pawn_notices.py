"""Auditable PawnLoan notice intent and scheduled delivery workflows."""

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.loans.domain import (
    PawnLoanNoticeChannel,
    PawnLoanNoticeKind,
    PawnLoanNoticeStatus,
    PawnLoanState,
    SUPPORTED_PAWN_LOAN_NOTICE_KINDS,
)
from apps.tenant_apps.loans.integrations.notice_delivery import (
    PawnNoticeDeliveryReceipt,
    create_pawn_notice_job,
    deliver_pawn_notice_job,
    get_pawn_notice_delivery_states,
)
from apps.tenant_apps.loans.models import (
    PawnLoan,
    PawnLoanNotice,
    current_tenant_workspace_id,
)
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance


class PawnLoanNoticeError(ValueError):
    pass


@dataclass(frozen=True)
class PawnLoanNoticeDispatchSummary:
    due_count: int
    sent_count: int
    failed_count: int


@dataclass(frozen=True)
class PawnLoanNoticeDispatchResult:
    notice: PawnLoanNotice
    delivery: PawnNoticeDeliveryReceipt


@transaction.atomic
def create_pawn_loan_notice(
    loan_id: int,
    *,
    notice_kind,
    channel,
    request_key: str,
    scheduled_for: datetime | None = None,
    actor=None,
    dispatch_due: bool = True,
    source_auction_id: int | None = None,
) -> PawnLoanNotice:
    loan = _locked_loan(loan_id)
    request_key = str(request_key or "").strip()
    if not request_key or len(request_key) > 120:
        raise PawnLoanNoticeError("A notice request key of at most 120 characters is required.")
    try:
        kind = PawnLoanNoticeKind(notice_kind)
        channel = PawnLoanNoticeChannel(channel)
    except ValueError as exc:
        raise PawnLoanNoticeError("Unsupported notice kind or delivery channel.") from exc
    if kind not in SUPPORTED_PAWN_LOAN_NOTICE_KINDS:
        raise PawnLoanNoticeError("Unsupported PawnLoan notice kind.")
    source_auction = None
    if kind == PawnLoanNoticeKind.AUCTION_NOTICE:
        from apps.tenant_apps.loans.models import PawnLoanAuction

        source_auction = PawnLoanAuction.objects.filter(
            pk=source_auction_id,
            loan=loan,
            workspace_id=loan.workspace_id,
        ).first()
        if source_auction is None:
            raise PawnLoanNoticeError("Auction notice requires its Loans-owned source auction.")
    elif source_auction_id is not None:
        raise PawnLoanNoticeError("Only an auction notice can reference an auction.")

    requested_scheduled_for = scheduled_for
    scheduled_for = scheduled_for or timezone.now()
    if timezone.is_naive(scheduled_for):
        scheduled_for = timezone.make_aware(scheduled_for, timezone.get_current_timezone())

    existing = PawnLoanNotice.objects.filter(
        loan=loan,
        request_key=request_key,
    ).first()
    if existing:
        if existing.notice_kind != kind.value or existing.channel != channel.value:
            raise PawnLoanNoticeError(
                "This notice request key was already used with different instructions."
            )
        if existing.source_auction_id != getattr(source_auction, "pk", None):
            raise PawnLoanNoticeError(
                "This notice request key was already used for a different source."
            )
        if (
            requested_scheduled_for is not None
            and existing.scheduled_for != scheduled_for
        ):
            raise PawnLoanNoticeError(
                "This notice request key was already used with a different schedule."
            )
        return existing

    notice_as_of_date = timezone.localtime(scheduled_for).date()
    balance = get_pawn_loan_balance(loan.pk, as_of_date=notice_as_of_date)
    _require_notice_eligibility(loan, balance, kind)
    recipient_email = (loan.borrower.primary_email or "").strip()
    recipient_phone = (loan.borrower.primary_phone or "").strip()
    payload = _payload_snapshot(
        loan,
        balance,
        kind,
        as_of_date=notice_as_of_date,
        source_auction=source_auction,
    )
    notice = PawnLoanNotice.objects.create(
        workspace=loan.workspace,
        loan=loan,
        notice_kind=kind.value,
        channel=channel.value,
        request_key=request_key,
        scheduled_for=scheduled_for,
        recipient_name=loan.borrower.display_name,
        recipient_email=recipient_email,
        recipient_phone=recipient_phone,
        payload_snapshot=payload,
        created_by=actor,
        source_auction=source_auction,
    )
    reference = create_pawn_notice_job(notice)
    notice.notification_event_id = reference.event_id
    notice.notification_job_id = reference.job_id
    notice.save(update_fields=["notification_event_id", "notification_job_id", "updated_at"])
    if dispatch_due and scheduled_for <= timezone.now():
        transaction.on_commit(lambda: dispatch_pawn_loan_notice(notice.pk))
    return notice


def dispatch_pawn_loan_notice(
    notice_id: int,
    *,
    delivery_handler=None,
    as_of=None,
) -> PawnLoanNoticeDispatchResult:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanNoticeError("PawnLoan notice delivery requires an active tenant schema.")
    try:
        notice = PawnLoanNotice.objects.get(pk=notice_id, workspace_id=workspace_id)
    except PawnLoanNotice.DoesNotExist as exc:
        raise PawnLoanNoticeError("PawnLoan notice was not found in the active workspace.") from exc
    as_of = as_of or timezone.now()
    if notice.scheduled_for > as_of:
        raise PawnLoanNoticeError("This notice is scheduled for a future time.")
    if not notice.notification_job_id:
        raise PawnLoanNoticeError("PawnLoan notice is missing its Notify delivery job.")

    state = get_pawn_notice_delivery_states([notice.notification_job_id]).get(
        notice.notification_job_id
    )
    if state is None:
        raise PawnLoanNoticeError("PawnLoan notice delivery job was not found in Notify.")
    if state.status == PawnLoanNoticeStatus.SENT.value:
        return PawnLoanNoticeDispatchResult(notice=notice, delivery=state)
    if state.status == PawnLoanNoticeStatus.CANCELLED.value:
        raise PawnLoanNoticeError("A cancelled notice cannot be delivered.")

    receipt = (delivery_handler or deliver_pawn_notice_job)(notice.notification_job_id)
    return PawnLoanNoticeDispatchResult(notice=notice, delivery=receipt)


def dispatch_due_pawn_loan_notices(*, as_of=None, limit=100) -> PawnLoanNoticeDispatchSummary:
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanNoticeError("Scheduled notice delivery requires an active tenant schema.")
    as_of = as_of or timezone.now()
    candidates = tuple(
        PawnLoanNotice.objects.filter(
            workspace_id=workspace_id,
            scheduled_for__lte=as_of,
        )
        .order_by("scheduled_for", "pk")
        .values_list("pk", "notification_job_id")
    )
    states = get_pawn_notice_delivery_states(job_id for _, job_id in candidates)
    due_ids = tuple(
        notice_id
        for notice_id, job_id in candidates
        if states.get(job_id)
        and states[job_id].status == PawnLoanNoticeStatus.QUEUED.value
    )[:limit]
    sent = 0
    failed = 0
    for notice_id in due_ids:
        result = dispatch_pawn_loan_notice(notice_id, as_of=as_of)
        if result.delivery.status == PawnLoanNoticeStatus.SENT.value:
            sent += 1
        elif result.delivery.status == PawnLoanNoticeStatus.FAILED.value:
            failed += 1
    from .operational_notices import dispatch_due_operational_notices

    remaining = max(0, limit - len(due_ids))
    operational_due, operational_sent, operational_failed = (
        dispatch_due_operational_notices(as_of=as_of, limit=remaining)
        if remaining else (0, 0, 0)
    )
    return PawnLoanNoticeDispatchSummary(
        len(due_ids) + operational_due,
        sent + operational_sent,
        failed + operational_failed,
    )


def _locked_loan(loan_id):
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise PawnLoanNoticeError("PawnLoan notices require an active tenant schema.")
    try:
        return (
            PawnLoan.objects.select_for_update()
            .select_related("workspace", "borrower")
            .prefetch_related("collateral_items", "accounting_events__outbox", "releases")
            .get(pk=loan_id, workspace_id=workspace_id)
        )
    except PawnLoan.DoesNotExist as exc:
        raise PawnLoanNoticeError("PawnLoan was not found in the active workspace.") from exc


def _require_notice_eligibility(loan, balance, kind):
    if kind == PawnLoanNoticeKind.AUCTION_NOTICE:
        if loan.state != PawnLoanState.ACTIVE.value or not balance.is_overdue:
            raise PawnLoanNoticeError("Auction notice requires an active overdue PawnLoan.")
        return
    if kind == PawnLoanNoticeKind.RELEASE_CONFIRMATION:
        if loan.state != PawnLoanState.CLOSED.value or not loan.releases.exists():
            raise PawnLoanNoticeError("Release confirmation requires a closed, released PawnLoan.")
        return
    if loan.state != PawnLoanState.ACTIVE.value:
        raise PawnLoanNoticeError("This notice can only be sent for an active PawnLoan.")
    if kind == PawnLoanNoticeKind.INTEREST_DUE and balance.interest_outstanding <= 0:
        raise PawnLoanNoticeError("This PawnLoan has no outstanding interest.")
    if kind == PawnLoanNoticeKind.OVERDUE_NOTICE and not balance.is_overdue:
        raise PawnLoanNoticeError("This PawnLoan is not overdue.")
    if kind == PawnLoanNoticeKind.REPAYMENT_REMINDER and balance.total_due <= 0:
        raise PawnLoanNoticeError("This PawnLoan has no amount due.")


def _payload_snapshot(loan, balance, kind, *, as_of_date, source_auction=None):
    payload = {
        "event_key": kind.value,
        "customer": {
            "name": loan.borrower.display_name,
            "email": loan.borrower.primary_email,
            "phone": loan.borrower.primary_phone,
        },
        "loans": [
            {
                "pk": loan.pk,
                "loan_id": loan.loan_number,
                "as_of_date": as_of_date.isoformat(),
                "due_date": balance.due_date.isoformat(),
                "principal_due": str(balance.principal_outstanding),
                "interest_due": str(balance.interest_outstanding),
                "fees_due": str(balance.fees_outstanding),
                "total_due": str(balance.total_due),
            }
        ],
        "loan_count": 1,
        "total_amount": str(balance.total_due),
        "generated_at": timezone.now().isoformat(),
    }
    if source_auction is not None:
        payload["auction"] = {
            "id": source_auction.pk,
            "number": source_auction.auction_number,
            "notice_date": source_auction.notice_date.isoformat(),
            "scheduled_date": source_auction.scheduled_date.isoformat(),
        }
    return payload


__all__ = [
    "PawnLoanNoticeDispatchSummary",
    "PawnLoanNoticeDispatchResult",
    "PawnLoanNoticeError",
    "create_pawn_loan_notice",
    "dispatch_due_pawn_loan_notices",
    "dispatch_pawn_loan_notice",
]
