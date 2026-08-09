"""Pure posting-control contracts for the standalone accounting proof."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from hashlib import sha256
import json

from .transactions import (
    AccountTransaction,
    AtomicTransaction,
    DomainValidationError,
    LedgerTransaction,
    TransactionBatch,
    _currency_code,
    _required_key,
)


class VoucherState(str, Enum):
    DRAFT = "DRAFT"
    AUTHORIZED = "AUTHORIZED"
    CANCELLED = "CANCELLED"


class PostingPurpose(str, Enum):
    ORDINARY = "ORDINARY"
    ADJUSTMENT = "ADJUSTMENT"


class PeriodStatus(str, Enum):
    OPEN = "OPEN"
    ADJUSTMENT_ONLY = "ADJUSTMENT_ONLY"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"


@dataclass(frozen=True, slots=True)
class SourceEventIdentity:
    source_system: str
    source_type: str
    source_id: str
    source_version: str

    def __post_init__(self) -> None:
        for field_name in ("source_system", "source_type", "source_id", "source_version"):
            object.__setattr__(
                self, field_name, _required_key(getattr(self, field_name), field_name)
            )


@dataclass(frozen=True, slots=True)
class PostingRuleIdentity:
    rule_key: str
    rule_version: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "rule_key", _required_key(self.rule_key, "rule_key"))
        object.__setattr__(
            self, "rule_version", _required_key(self.rule_version, "rule_version")
        )


@dataclass(frozen=True, slots=True)
class AccountingBook:
    book_key: str
    base_currency: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "book_key", _required_key(self.book_key, "book_key"))
        object.__setattr__(
            self,
            "base_currency",
            _currency_code(self.base_currency, "base_currency"),
        )


@dataclass(frozen=True, slots=True)
class AccountingPeriod:
    period_key: str
    book_key: str
    start_date: date
    end_date: date
    status: PeriodStatus

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "period_key", _required_key(self.period_key, "period_key")
        )
        object.__setattr__(self, "book_key", _required_key(self.book_key, "book_key"))
        if not isinstance(self.start_date, date) or not isinstance(self.end_date, date):
            raise DomainValidationError("period dates must be dates")
        if self.start_date > self.end_date:
            raise DomainValidationError("period start_date must not exceed end_date")
        if not isinstance(self.status, PeriodStatus):
            raise DomainValidationError("status must be a PeriodStatus")


@dataclass(frozen=True, slots=True)
class CurrencyPolicy:
    base_currency: str
    decimal_places: int = 2
    rounding: str = ROUND_HALF_UP

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "base_currency",
            _currency_code(self.base_currency, "base_currency"),
        )
        if not isinstance(self.decimal_places, int) or not 0 <= self.decimal_places <= 8:
            raise DomainValidationError("decimal_places must be between 0 and 8")

    @property
    def quantum(self) -> Decimal:
        return Decimal("1").scaleb(-self.decimal_places)

    def expected_base_amount(self, *, amount: Decimal, exchange_rate: Decimal) -> Decimal:
        return (amount * exchange_rate).quantize(self.quantum, rounding=self.rounding)


@dataclass(frozen=True, slots=True)
class VoucherIntent:
    voucher_key: str
    book_key: str
    idempotency_key: str
    effective_date: date
    source: SourceEventIdentity
    rule: PostingRuleIdentity
    transactions: tuple[AtomicTransaction, ...]
    purpose: PostingPurpose = PostingPurpose.ORDINARY
    state: VoucherState = VoucherState.DRAFT
    authorized_by: str | None = None
    authorized_at: datetime | None = None

    def __post_init__(self) -> None:
        for field_name in ("voucher_key", "book_key", "idempotency_key"):
            object.__setattr__(
                self, field_name, _required_key(getattr(self, field_name), field_name)
            )
        if not isinstance(self.effective_date, date):
            raise DomainValidationError("effective_date must be a date")
        if not isinstance(self.source, SourceEventIdentity):
            raise DomainValidationError("source must be a SourceEventIdentity")
        if not isinstance(self.rule, PostingRuleIdentity):
            raise DomainValidationError("rule must be a PostingRuleIdentity")
        transactions = tuple(self.transactions)
        if not transactions:
            raise DomainValidationError("a voucher must contain a transaction")
        if not all(isinstance(item, (LedgerTransaction, AccountTransaction)) for item in transactions):
            raise DomainValidationError("voucher contains an unsupported transaction form")
        keys = [item.transaction_key for item in transactions]
        if len(keys) != len(set(keys)):
            raise DomainValidationError("voucher transaction keys must be unique")
        object.__setattr__(self, "transactions", transactions)
        if not isinstance(self.purpose, PostingPurpose):
            raise DomainValidationError("purpose must be a PostingPurpose")
        if not isinstance(self.state, VoucherState):
            raise DomainValidationError("state must be a VoucherState")
        if self.state is VoucherState.AUTHORIZED:
            _required_key(self.authorized_by or "", "authorized_by")
            if not isinstance(self.authorized_at, datetime):
                raise DomainValidationError("authorized_at is required for authorization")
        elif self.authorized_by is not None or self.authorized_at is not None:
            raise DomainValidationError(
                "authorization evidence is allowed only on an authorized voucher"
            )

    def authorize(self, *, actor_key: str, authorized_at: datetime) -> "VoucherIntent":
        if self.state is not VoucherState.DRAFT:
            raise DomainValidationError("only a draft voucher may be authorized")
        if not isinstance(authorized_at, datetime):
            raise DomainValidationError("authorized_at must be a datetime")
        return replace(
            self,
            state=VoucherState.AUTHORIZED,
            authorized_by=_required_key(actor_key, "actor_key"),
            authorized_at=authorized_at,
        )


@dataclass(frozen=True, slots=True)
class PostingRecord:
    voucher_key: str
    book_key: str
    idempotency_key: str
    fingerprint: str
    source: SourceEventIdentity
    rule: PostingRuleIdentity
    batch: TransactionBatch


@dataclass(frozen=True, slots=True)
class PostingResult:
    record: PostingRecord
    replayed: bool


@dataclass(frozen=True, slots=True)
class ReversalRecord:
    original: PostingRecord
    reversal_batch: TransactionBatch
    actor_key: str
    reason: str


@dataclass(frozen=True, slots=True)
class CorrectionResult:
    original: PostingRecord
    reversal: ReversalRecord
    replacement: PostingRecord


def _transaction_payload(transaction: AtomicTransaction) -> dict:
    money = transaction.money
    payload = {
        "transaction_key": transaction.transaction_key,
        "kind": transaction.kind.value,
        "amount": str(money.amount),
        "currency": money.currency,
        "base_amount": str(money.base_amount),
        "base_currency": money.base_currency,
        "exchange_rate": str(money.exchange_rate),
        "rate_source": money.rate_source,
        "narration": transaction.narration,
    }
    if isinstance(transaction, LedgerTransaction):
        payload.update(
            {
                "debit_ledger_key": transaction.debit_ledger_key,
                "credit_ledger_key": transaction.credit_ledger_key,
            }
        )
    else:
        payload.update(
            {
                "ledger_key": transaction.ledger_key,
                "external_account_key": transaction.external_account_key,
                "ledger_side": transaction.ledger_side.value,
                "classification": {
                    "version_key": transaction.classification.version_key,
                    "purpose": transaction.classification.purpose.value,
                    "reporting_class": transaction.classification.reporting_class.value,
                    "reporting_ledger_key": transaction.classification.reporting_ledger_key,
                    "normal_side": transaction.classification.normal_side.value,
                },
            }
        )
    return payload


def voucher_fingerprint(voucher: VoucherIntent) -> str:
    payload = {
        "book_key": voucher.book_key,
        "effective_date": voucher.effective_date.isoformat(),
        "purpose": voucher.purpose.value,
        "source": {
            "system": voucher.source.source_system,
            "type": voucher.source.source_type,
            "id": voucher.source.source_id,
            "version": voucher.source.source_version,
        },
        "rule": {
            "key": voucher.rule.rule_key,
            "version": voucher.rule.rule_version,
        },
        "transactions": [_transaction_payload(item) for item in voucher.transactions],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256(encoded).hexdigest()


def _validate_period(
    *,
    book: AccountingBook,
    period: AccountingPeriod,
    effective_date: date,
    purpose: PostingPurpose,
) -> None:
    if period.book_key != book.book_key:
        raise DomainValidationError("accounting period belongs to a different book")
    if not period.start_date <= effective_date <= period.end_date:
        raise DomainValidationError("effective_date is outside the accounting period")
    if period.status is PeriodStatus.OPEN:
        return
    if period.status is PeriodStatus.ADJUSTMENT_ONLY and purpose is PostingPurpose.ADJUSTMENT:
        return
    raise DomainValidationError(
        f"period {period.period_key} does not allow {purpose.value} posting"
    )


def _validate_currency(
    *, voucher: VoucherIntent, book: AccountingBook, currency_policy: CurrencyPolicy
) -> None:
    if currency_policy.base_currency != book.base_currency:
        raise DomainValidationError("currency policy does not match the accounting book")
    for transaction in voucher.transactions:
        money = transaction.money
        if money.base_currency != book.base_currency:
            raise DomainValidationError(
                f"transaction {transaction.transaction_key} uses the wrong base currency"
            )
        expected = currency_policy.expected_base_amount(
            amount=money.amount, exchange_rate=money.exchange_rate
        )
        if money.base_amount != expected:
            raise DomainValidationError(
                f"transaction {transaction.transaction_key} base amount does not match its rate"
            )


def post_voucher(
    voucher: VoucherIntent,
    *,
    book: AccountingBook,
    period: AccountingPeriod,
    currency_policy: CurrencyPolicy,
    prior_postings: tuple[PostingRecord, ...] = (),
) -> PostingResult:
    if voucher.state is not VoucherState.AUTHORIZED:
        raise DomainValidationError("voucher must be authorized before posting")
    if voucher.book_key != book.book_key:
        raise DomainValidationError("voucher belongs to a different accounting book")
    _validate_period(
        book=book,
        period=period,
        effective_date=voucher.effective_date,
        purpose=voucher.purpose,
    )
    _validate_currency(voucher=voucher, book=book, currency_policy=currency_policy)
    fingerprint = voucher_fingerprint(voucher)
    for existing in prior_postings:
        if (
            existing.book_key == voucher.book_key
            and existing.idempotency_key == voucher.idempotency_key
        ):
            if existing.fingerprint != fingerprint:
                raise DomainValidationError(
                    "book-scoped idempotency key was reused with a different economic payload"
                )
            return PostingResult(record=existing, replayed=True)
    batch = TransactionBatch(
        batch_key=f"POST:{voucher.voucher_key}",
        book_key=voucher.book_key,
        idempotency_key=voucher.idempotency_key,
        effective_date=voucher.effective_date,
        transactions=voucher.transactions,
    )
    record = PostingRecord(
        voucher_key=voucher.voucher_key,
        book_key=voucher.book_key,
        idempotency_key=voucher.idempotency_key,
        fingerprint=fingerprint,
        source=voucher.source,
        rule=voucher.rule,
        batch=batch,
    )
    return PostingResult(record=record, replayed=False)


def reverse_posting(
    original: PostingRecord,
    *,
    reversal_batch_key: str,
    reversal_idempotency_key: str,
    reversal_date: date,
    actor_key: str,
    reason: str,
    book: AccountingBook,
    period: AccountingPeriod,
) -> ReversalRecord:
    if original.book_key != book.book_key:
        raise DomainValidationError("original posting belongs to a different book")
    _validate_period(
        book=book,
        period=period,
        effective_date=reversal_date,
        purpose=PostingPurpose.ADJUSTMENT,
    )
    actor = _required_key(actor_key, "actor_key")
    reversal_reason = _required_key(reason, "reason")
    reversal_batch = original.batch.reversed(
        batch_key=reversal_batch_key,
        idempotency_key=reversal_idempotency_key,
        effective_date=reversal_date,
    )
    return ReversalRecord(
        original=original,
        reversal_batch=reversal_batch,
        actor_key=actor,
        reason=reversal_reason,
    )


def correct_posting(
    original: PostingRecord,
    corrected_voucher: VoucherIntent,
    *,
    reversal_batch_key: str,
    reversal_idempotency_key: str,
    correction_date: date,
    actor_key: str,
    reason: str,
    book: AccountingBook,
    period: AccountingPeriod,
    currency_policy: CurrencyPolicy,
    prior_postings: tuple[PostingRecord, ...] = (),
) -> CorrectionResult:
    if corrected_voucher.idempotency_key == original.idempotency_key:
        raise DomainValidationError("a correction requires a new idempotency key")
    reversal = reverse_posting(
        original,
        reversal_batch_key=reversal_batch_key,
        reversal_idempotency_key=reversal_idempotency_key,
        reversal_date=correction_date,
        actor_key=actor_key,
        reason=reason,
        book=book,
        period=period,
    )
    replacement = post_voucher(
        corrected_voucher,
        book=book,
        period=period,
        currency_policy=currency_policy,
        prior_postings=prior_postings + (original,),
    ).record
    return CorrectionResult(
        original=original,
        reversal=reversal,
        replacement=replacement,
    )
