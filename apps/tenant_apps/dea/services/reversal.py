from dataclasses import dataclass

from django.db import connection, transaction

from apps.tenant_apps.dea.models import (
    AccountTransaction,
    AccountingPeriod,
    JournalEntry,
    LedgerTransaction,
    Voucher,
    VoucherStatus,
)
from apps.tenant_apps.dea.models.audit import AccountingAuditEvent
from apps.tenant_apps.dea.services.audit import AuditService


class ReversalError(Exception):
    """Base domain error for voucher reversal."""


class VoucherNotPostedError(ReversalError):
    """Raised when a voucher cannot be reversed because it is not posted."""


class ReversalPeriodError(ReversalError):
    """Raised when no writable accounting period exists for the reversal."""


class MissingOriginalJournalEntryError(ReversalError):
    """Raised when a posted voucher has no original journal entry to reverse."""


@dataclass(frozen=True)
class ReversalResult:
    original_voucher: Voucher
    reversal_journal_entry: JournalEntry | None
    original_journal_entry: JournalEntry | None
    status_before: str
    status_after: str
    already_reversed: bool = False


def reverse_posted_voucher(
    *,
    voucher,
    actor,
    reason: str,
    reversal_date=None,
    source_action: str = "manual_reversal",
) -> ReversalResult:
    if connection.schema_name == "public":
        raise RuntimeError(
            "reverse_posted_voucher() must not be called in the public schema."
        )
    if not reason or not str(reason).strip():
        raise ReversalError("A reversal reason is required.")

    with transaction.atomic():
        voucher_id = voucher.pk if isinstance(voucher, Voucher) else voucher
        locked_voucher = (
            Voucher.objects.select_for_update()
            .select_related("voucher_type", "doc_content_type")
            .get(pk=voucher_id)
        )
        status_before = locked_voucher.status

        original_je = _get_original_journal_entry(locked_voucher)
        existing_reversal = _get_existing_reversal(locked_voucher, original_je)

        if locked_voucher.status == VoucherStatus.REVERSED:
            return ReversalResult(
                original_voucher=locked_voucher,
                reversal_journal_entry=existing_reversal,
                original_journal_entry=original_je,
                status_before=status_before,
                status_after=locked_voucher.status,
                already_reversed=True,
            )

        if locked_voucher.status != VoucherStatus.POSTED:
            raise VoucherNotPostedError(
                f"Cannot reverse {locked_voucher.status} voucher. "
                "Only POSTED vouchers can be reversed."
            )

        if original_je is None:
            raise MissingOriginalJournalEntryError(
                f"Voucher {locked_voucher.pk} has no original journal entry to reverse."
            )

        if existing_reversal is not None:
            locked_voucher.status = VoucherStatus.REVERSED
            locked_voucher.save(update_fields=["status"])
            return ReversalResult(
                original_voucher=locked_voucher,
                reversal_journal_entry=existing_reversal,
                original_journal_entry=original_je,
                status_before=status_before,
                status_after=locked_voucher.status,
                already_reversed=True,
            )

        period = _resolve_reversal_period(locked_voucher, reversal_date)
        reversal_je = _create_reversal_journal_entry(
            original_je=original_je,
            actor=actor,
            period=period,
            reason=str(reason),
        )

        locked_voucher.status = VoucherStatus.REVERSED
        locked_voucher.save(update_fields=["status"])
        _log_reversal_event(
            voucher=locked_voucher,
            actor=actor,
            reason=str(reason),
            source_action=source_action,
            status_before=status_before,
            reversal_je=reversal_je,
            original_je=original_je,
            period=period,
        )

        return ReversalResult(
            original_voucher=locked_voucher,
            reversal_journal_entry=reversal_je,
            original_journal_entry=original_je,
            status_before=status_before,
            status_after=locked_voucher.status,
            already_reversed=False,
        )


def _get_original_journal_entry(voucher: Voucher) -> JournalEntry | None:
    return (
        voucher.journal_entries.filter(is_reversal_of__isnull=True)
        .order_by("id")
        .first()
    )


def _get_existing_reversal(
    voucher: Voucher, original_je: JournalEntry | None
) -> JournalEntry | None:
    if original_je is None:
        return None
    return (
        voucher.journal_entries.filter(is_reversal_of=original_je)
        .order_by("id")
        .first()
    )


def _resolve_reversal_period(voucher: Voucher, reversal_date=None):
    target_date = reversal_date or voucher.voucher_date
    period = AccountingPeriod.objects.get_period_for_date(target_date)
    if not period:
        raise ReversalPeriodError(
            f"No accounting period found for reversal date {target_date}."
        )
    if not period.can_modify_transactions():
        raise ReversalPeriodError(
            f"Cannot reverse voucher {voucher.voucher_no} dated {target_date}: "
            f"accounting period '{period.name}' is {period.status}."
        )
    return period


def _create_reversal_journal_entry(
    *,
    original_je: JournalEntry,
    actor,
    period,
    reason: str,
) -> JournalEntry:
    reversal_je = JournalEntry.objects.create(
        voucher=original_je.voucher,
        posted_by=actor,
        period=period,
        is_reversal_of=original_je,
        desc=f"Reversal of JE-{original_je.pk}: {reason}",
    )

    ledger_txns = [
        LedgerTransaction(
            journal_entry=reversal_je,
            ledgerno_dr_id=txn.ledgerno_id,
            ledgerno_id=txn.ledgerno_dr_id,
            amount=txn.amount,
            amount_base=txn.amount_base,
        )
        for txn in original_je.ltxns.all()
    ]
    if ledger_txns:
        LedgerTransaction.objects.bulk_create(ledger_txns)

    account_txns = []
    for txn in original_je.atxns.all():
        old_side = txn.XactTypeCode_id
        new_side = "Cr" if old_side == "Dr" else "Dr"
        account_txns.append(
            AccountTransaction(
                journal_entry=reversal_je,
                ledgerno_id=txn.ledgerno_id,
                Account_id=txn.Account_id,
                XactTypeCode_id=new_side,
                XactTypeCode_ext_id=txn.XactTypeCode_ext_id,
                amount=txn.amount,
            )
        )
    if account_txns:
        AccountTransaction.objects.bulk_create(account_txns)

    return reversal_je


def _log_reversal_event(
    *,
    voucher: Voucher,
    actor,
    reason: str,
    source_action: str,
    status_before: str,
    reversal_je: JournalEntry,
    original_je: JournalEntry,
    period,
) -> None:
    AuditService.log_event(
        event_type=AccountingAuditEvent.EventType.VOUCHER_REVERSED,
        actor=actor,
        obj=voucher,
        payload_before={"status": status_before},
        payload_after={
            "status": voucher.status,
            "reason": reason,
            "source_action": source_action,
            "original_journal_entry_id": original_je.pk,
            "reversal_journal_entry_id": reversal_je.pk,
            "period_id": period.pk if period else None,
        },
        description=f"Reversed voucher {voucher.voucher_no}: {reason}",
    )
