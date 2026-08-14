"""Canonical persisted posting boundary for the standalone accounting app."""

import hashlib
import json
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import (
    AccountingTransaction,
    AccountTransaction,
    AccountingPeriod,
    PersistedVoucherState,
    PeriodStatus,
    TransactionBatch,
    TransactionDiscriminator,
    LedgerSide,
    LedgerTransaction,
    Voucher,
    VoucherPurpose,
)
from .settlements import compensate_reversed_settlement_allocations


def _canonical_payload(voucher: Voucher) -> dict:
    rows = []
    transactions = voucher.transactions.select_related(
        "ledger_detail__debit_ledger",
        "ledger_detail__credit_ledger",
        "account_detail__ledger",
        "account_detail__external_account",
        "account_detail__classification__reporting_ledger",
    ).order_by("sequence")
    for item in transactions:
        row = {
            "sequence": item.sequence,
            "kind": item.discriminator,
            "amount": str(item.amount),
            "currency": item.currency,
            "base_amount": str(item.base_amount),
            "base_currency": item.base_currency,
            "exchange_rate": str(item.exchange_rate),
            "rate_source": item.rate_source,
            "narration": item.narration,
        }
        if item.discriminator == TransactionDiscriminator.LEDGER:
            detail = item.ledger_detail
            row.update(
                debit_ledger_key=detail.debit_ledger.ledger_key,
                credit_ledger_key=detail.credit_ledger.ledger_key,
            )
        elif item.discriminator == TransactionDiscriminator.ACCOUNT:
            detail = item.account_detail
            classification = detail.classification
            row.update(
                ledger_key=detail.ledger.ledger_key,
                external_account_key=detail.external_account.account_key,
                ledger_side=detail.ledger_side,
                classification={
                    "version_key": classification.version_key,
                    "reporting_ledger_key": classification.reporting_ledger.ledger_key,
                    "reporting_class": classification.reporting_class,
                    "normal_side": classification.normal_side,
                },
            )
        else:
            raise ValidationError("Transaction discriminator is invalid.")
        rows.append(row)
    if not rows:
        raise ValidationError("Voucher must contain at least one transaction.")
    return {
        "book_key": voucher.book.book_key,
        "effective_date": voucher.effective_date.isoformat(),
        "purpose": voucher.purpose,
        "source": {
            "system": voucher.source_system,
            "type": voucher.source_type,
            "id": voucher.source_id,
            "version": voucher.source_version,
        },
        "rule": {"key": voucher.rule_key, "version": voucher.rule_version},
        "transactions": rows,
    }


def _digest(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def voucher_fingerprint(voucher: Voucher) -> str:
    return _digest(_canonical_payload(voucher))


def _posting_period(voucher: Voucher) -> AccountingPeriod:
    periods = list(
        AccountingPeriod.objects.select_for_update().filter(
            book=voucher.book,
            start_date__lte=voucher.effective_date,
            end_date__gte=voucher.effective_date,
        )
    )
    if len(periods) != 1:
        raise ValidationError("Exactly one accounting period must cover the voucher date.")
    period = periods[0]
    allowed = period.status == PeriodStatus.OPEN or (
        period.status == PeriodStatus.ADJUSTMENT_ONLY
        and voucher.purpose == VoucherPurpose.ADJUSTMENT
    )
    if not allowed:
        raise ValidationError(
            f"Period {period.period_key} does not allow {voucher.purpose} posting."
        )
    return period


def _finalize_locked_voucher(
    *,
    locked: Voucher,
    actor_id: int,
    posted_at: datetime,
    actor_identity: str = "",
    reversal_of: TransactionBatch | None = None,
    reversal_reason: str = "",
) -> TransactionBatch:
    period = _posting_period(locked)
    fingerprint = voucher_fingerprint(locked)
    verification_payload = {
        "voucher_fingerprint": fingerprint,
        "transaction_count": locked.transactions.count(),
    }
    if reversal_of is not None:
        verification_payload["reversal_of_fingerprint"] = reversal_of.fingerprint
    verification_digest = _digest(verification_payload)
    locked.state = PersistedVoucherState.POSTED
    locked.fingerprint = fingerprint
    locked.save(update_fields=("state", "fingerprint", "updated_at"))
    return TransactionBatch.objects.create(
        voucher=locked,
        book=locked.book,
        period=period,
        posted_at=posted_at,
        posted_by_id=actor_id,
        posted_by_identity=actor_identity or f"user:{actor_id}",
        fingerprint=fingerprint,
        verification_digest=verification_digest,
        reversal_of=reversal_of,
        reversal_reason=reversal_reason,
        correction_group_key=locked.correction_group_key,
    )


@transaction.atomic
def post_authorized_voucher(
    *, voucher: Voucher, actor_id: int, posted_at: datetime, actor_identity: str = ""
) -> TransactionBatch:
    if not isinstance(voucher, Voucher):
        raise ValidationError("voucher must be a Voucher")
    if not isinstance(actor_id, int) or actor_id <= 0:
        raise ValidationError("actor_id must be a positive integer")
    if not isinstance(posted_at, datetime):
        raise ValidationError("posted_at must be a datetime")

    locked = Voucher.objects.select_for_update().select_related("book").get(pk=voucher.pk)
    if locked.state == PersistedVoucherState.POSTED:
        return TransactionBatch.objects.get(voucher=locked)
    if locked.state != PersistedVoucherState.AUTHORIZED:
        raise ValidationError("Voucher must be authorized before posting.")

    return _finalize_locked_voucher(
        locked=locked, actor_id=actor_id, posted_at=posted_at, actor_identity=actor_identity
    )


@transaction.atomic
def reverse_posted_batch(
    *,
    original: TransactionBatch,
    voucher_key: str,
    idempotency_key: str,
    reversal_date,
    actor_id: int,
    occurred_at: datetime,
    reason: str,
    correction_group_key: str = "",
    voucher_number: str = "",
    actor_identity: str = "",
) -> TransactionBatch:
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Reversal reason is required.")
    locked_original = TransactionBatch.objects.select_for_update().select_related(
        "voucher__book"
    ).get(pk=original.pk)
    if locked_original.reversal_of_id is not None:
        raise ValidationError("A reversal batch cannot itself be reversed.")
    existing = TransactionBatch.objects.filter(reversal_of=locked_original).first()
    if existing is not None:
        if existing.voucher.idempotency_key == idempotency_key:
            return existing
        raise ValidationError("The original posting already has a reversal.")

    original_rows = list(
        locked_original.voucher.transactions.select_related(
            "ledger_detail", "account_detail"
        ).order_by("-sequence")
    )
    reversal = Voucher.objects.create(
        book=locked_original.book,
        voucher_key=voucher_key,
        voucher_number=voucher_number,
        effective_date=reversal_date,
        purpose=VoucherPurpose.ADJUSTMENT,
        idempotency_key=idempotency_key,
        source_system="STANDALONE_ACCOUNTING",
        source_type="REVERSAL",
        source_id=str(locked_original.voucher_id),
        source_version=locked_original.fingerprint,
        rule_key="EXACT_BATCH_REVERSAL",
        rule_version="1",
        narration=reason,
        correction_group_key=correction_group_key,
        created_by_id=actor_id,
        created_by_identity=actor_identity or f"user:{actor_id}",
    )
    for sequence, source in enumerate(original_rows, start=1):
        base = AccountingTransaction.objects.create(
            voucher=reversal,
            sequence=sequence,
            discriminator=source.discriminator,
            amount=source.amount,
            currency=source.currency,
            base_amount=source.base_amount,
            base_currency=source.base_currency,
            exchange_rate=source.exchange_rate,
            rate_source=source.rate_source,
            narration=f"Reversal: {source.narration}".strip(),
        )
        if source.discriminator == TransactionDiscriminator.LEDGER:
            LedgerTransaction.objects.create(
                transaction=base,
                debit_ledger=source.ledger_detail.credit_ledger,
                credit_ledger=source.ledger_detail.debit_ledger,
            )
        else:
            source_detail = source.account_detail
            opposite = (
                LedgerSide.CREDIT
                if source_detail.ledger_side == LedgerSide.DEBIT
                else LedgerSide.DEBIT
            )
            AccountTransaction.objects.create(
                transaction=base,
                ledger=source_detail.ledger,
                external_account=source_detail.external_account,
                ledger_side=opposite,
                classification=source_detail.classification,
            )
    reversal.state = PersistedVoucherState.AUTHORIZED
    reversal.authorized_by_id = actor_id
    reversal.authorized_by_identity = actor_identity or f"user:{actor_id}"
    reversal.authorized_at = occurred_at
    reversal.save(update_fields=("state", "authorized_by_id", "authorized_by_identity", "authorized_at", "updated_at"))
    reversal_batch = _finalize_locked_voucher(
        locked=reversal,
        actor_id=actor_id,
        posted_at=occurred_at,
        reversal_of=locked_original,
        reversal_reason=reason,
        actor_identity=actor_identity,
    )
    compensate_reversed_settlement_allocations(
        original_batch=locked_original,
        reversal_batch=reversal_batch,
        created_by_id=actor_id,
    )
    return reversal_batch


@transaction.atomic
def correct_posted_batch(
    *,
    original: TransactionBatch,
    replacement_voucher: Voucher,
    reversal_voucher_key: str,
    reversal_idempotency_key: str,
    correction_date,
    actor_id: int,
    occurred_at: datetime,
    reason: str,
    correction_group_key: str,
    reversal_voucher_number: str = "",
    actor_identity: str = "",
) -> tuple[TransactionBatch, TransactionBatch]:
    group = (correction_group_key or "").strip()
    if not group:
        raise ValidationError("Correction group key is required.")
    replacement = Voucher.objects.select_for_update().get(pk=replacement_voucher.pk)
    if replacement.state != PersistedVoucherState.AUTHORIZED:
        raise ValidationError("Correction replacement must be authorized.")
    if replacement.book_id != original.book_id:
        raise ValidationError("Correction replacement must use the original book.")
    if replacement.correction_group_key != group:
        raise ValidationError("Replacement voucher must carry the correction group key.")
    reversal = reverse_posted_batch(
        original=original,
        voucher_key=reversal_voucher_key,
        idempotency_key=reversal_idempotency_key,
        reversal_date=correction_date,
        actor_id=actor_id,
        occurred_at=occurred_at,
        reason=reason,
        correction_group_key=group,
        voucher_number=reversal_voucher_number,
        actor_identity=actor_identity,
    )
    replacement_batch = post_authorized_voucher(
        voucher=replacement, actor_id=actor_id, posted_at=occurred_at, actor_identity=actor_identity
    )
    return reversal, replacement_batch
