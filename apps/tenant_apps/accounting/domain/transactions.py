"""Database-free contracts for atomic paired accounting transactions.

The model follows the proposed standalone accounting ADR: a transaction is
either internal-ledger to internal-ledger or internal-ledger to external
account.  Compound economic events are ordered batches of those atomic facts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import TypeAlias


class DomainValidationError(ValueError):
    """Raised when a proposed accounting fact violates a kernel invariant."""


class TransactionKind(str, Enum):
    LEDGER = "LEDGER"
    ACCOUNT = "ACCOUNT"


class LedgerSide(str, Enum):
    DEBIT = "DEBIT"
    CREDIT = "CREDIT"

    @property
    def opposite(self) -> "LedgerSide":
        return LedgerSide.CREDIT if self is LedgerSide.DEBIT else LedgerSide.DEBIT


class AccountPurpose(str, Enum):
    CUSTOMER_RECEIVABLE = "CUSTOMER_RECEIVABLE"
    SUPPLIER_PAYABLE = "SUPPLIER_PAYABLE"
    BORROWER_LOAN_RECEIVABLE = "BORROWER_LOAN_RECEIVABLE"
    LENDER_LOAN_PAYABLE = "LENDER_LOAN_PAYABLE"
    CUSTOMER_ADVANCE = "CUSTOMER_ADVANCE"
    SUPPLIER_ADVANCE = "SUPPLIER_ADVANCE"


class ReportingClass(str, Enum):
    ASSET = "ASSET"
    LIABILITY = "LIABILITY"
    EQUITY = "EQUITY"
    REVENUE = "REVENUE"
    EXPENSE = "EXPENSE"
    GAIN = "GAIN"
    LOSS = "LOSS"


def _required_key(value: str, field_name: str) -> str:
    normalized = str(value).strip()
    if not normalized:
        raise DomainValidationError(f"{field_name} is required")
    return normalized


def _positive_decimal(value: Decimal | str | int, field_name: str) -> Decimal:
    try:
        normalized = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise DomainValidationError(f"{field_name} must be a decimal") from exc
    if not normalized.is_finite() or normalized <= 0:
        raise DomainValidationError(f"{field_name} must be finite and greater than zero")
    return normalized


def _currency_code(value: str, field_name: str) -> str:
    normalized = str(value).strip().upper()
    if len(normalized) != 3 or not normalized.isalpha():
        raise DomainValidationError(f"{field_name} must be a three-letter monetary code")
    return normalized


@dataclass(frozen=True, slots=True)
class MonetaryAmount:
    """Transaction and base values frozen with their conversion provenance."""

    amount: Decimal
    currency: str
    base_amount: Decimal
    base_currency: str
    exchange_rate: Decimal
    rate_source: str

    def __post_init__(self) -> None:
        amount = _positive_decimal(self.amount, "amount")
        base_amount = _positive_decimal(self.base_amount, "base_amount")
        rate = _positive_decimal(self.exchange_rate, "exchange_rate")
        currency = _currency_code(self.currency, "currency")
        base_currency = _currency_code(self.base_currency, "base_currency")
        rate_source = _required_key(self.rate_source, "rate_source")
        if currency == base_currency and (rate != Decimal("1") or amount != base_amount):
            raise DomainValidationError(
                "same-currency amounts require exchange_rate=1 and equal base_amount"
            )
        object.__setattr__(self, "amount", amount)
        object.__setattr__(self, "base_amount", base_amount)
        object.__setattr__(self, "exchange_rate", rate)
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "base_currency", base_currency)
        object.__setattr__(self, "rate_source", rate_source)


@dataclass(frozen=True, slots=True)
class AccountClassificationSnapshot:
    """Historically stable financial-statement meaning of an external account."""

    version_key: str
    purpose: AccountPurpose
    reporting_class: ReportingClass
    reporting_ledger_key: str
    normal_side: LedgerSide

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "version_key", _required_key(self.version_key, "version_key")
        )
        object.__setattr__(
            self,
            "reporting_ledger_key",
            _required_key(self.reporting_ledger_key, "reporting_ledger_key"),
        )
        if not isinstance(self.purpose, AccountPurpose):
            raise DomainValidationError("purpose must be an AccountPurpose")
        if not isinstance(self.reporting_class, ReportingClass):
            raise DomainValidationError("reporting_class must be a ReportingClass")
        if not isinstance(self.normal_side, LedgerSide):
            raise DomainValidationError("normal_side must be a LedgerSide")


@dataclass(frozen=True, slots=True)
class LedgerTransaction:
    """One atomic movement between two distinct internal ledgers."""

    transaction_key: str
    debit_ledger_key: str
    credit_ledger_key: str
    money: MonetaryAmount
    narration: str = ""
    kind: TransactionKind = TransactionKind.LEDGER

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "transaction_key", _required_key(self.transaction_key, "transaction_key")
        )
        debit = _required_key(self.debit_ledger_key, "debit_ledger_key")
        credit = _required_key(self.credit_ledger_key, "credit_ledger_key")
        if debit == credit:
            raise DomainValidationError("debit and credit ledgers must be distinct")
        if not isinstance(self.money, MonetaryAmount):
            raise DomainValidationError("money must be a MonetaryAmount")
        if self.kind is not TransactionKind.LEDGER:
            raise DomainValidationError("LedgerTransaction kind must be LEDGER")
        object.__setattr__(self, "debit_ledger_key", debit)
        object.__setattr__(self, "credit_ledger_key", credit)
        object.__setattr__(self, "narration", str(self.narration).strip())

    def reversed(self, *, transaction_key: str) -> "LedgerTransaction":
        return LedgerTransaction(
            transaction_key=transaction_key,
            debit_ledger_key=self.credit_ledger_key,
            credit_ledger_key=self.debit_ledger_key,
            money=self.money,
            narration=f"Reversal: {self.narration}".strip(),
        )


@dataclass(frozen=True, slots=True)
class AccountTransaction:
    """One atomic movement between an internal ledger and external account."""

    transaction_key: str
    ledger_key: str
    external_account_key: str
    ledger_side: LedgerSide
    classification: AccountClassificationSnapshot
    money: MonetaryAmount
    narration: str = ""
    kind: TransactionKind = TransactionKind.ACCOUNT

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "transaction_key", _required_key(self.transaction_key, "transaction_key")
        )
        object.__setattr__(self, "ledger_key", _required_key(self.ledger_key, "ledger_key"))
        object.__setattr__(
            self,
            "external_account_key",
            _required_key(self.external_account_key, "external_account_key"),
        )
        if not isinstance(self.ledger_side, LedgerSide):
            raise DomainValidationError("ledger_side must be a LedgerSide")
        if not isinstance(self.classification, AccountClassificationSnapshot):
            raise DomainValidationError(
                "classification must be an AccountClassificationSnapshot"
            )
        if not isinstance(self.money, MonetaryAmount):
            raise DomainValidationError("money must be a MonetaryAmount")
        if self.kind is not TransactionKind.ACCOUNT:
            raise DomainValidationError("AccountTransaction kind must be ACCOUNT")
        object.__setattr__(self, "narration", str(self.narration).strip())

    @property
    def external_account_side(self) -> LedgerSide:
        return self.ledger_side.opposite

    def reversed(self, *, transaction_key: str) -> "AccountTransaction":
        return AccountTransaction(
            transaction_key=transaction_key,
            ledger_key=self.ledger_key,
            external_account_key=self.external_account_key,
            ledger_side=self.ledger_side.opposite,
            classification=self.classification,
            money=self.money,
            narration=f"Reversal: {self.narration}".strip(),
        )


AtomicTransaction: TypeAlias = LedgerTransaction | AccountTransaction


@dataclass(frozen=True, slots=True)
class TransactionBatch:
    """An ordered, atomic set of paired transactions for one economic event."""

    batch_key: str
    book_key: str
    idempotency_key: str
    effective_date: date
    transactions: tuple[AtomicTransaction, ...]
    reversal_of_batch_key: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "batch_key", _required_key(self.batch_key, "batch_key"))
        object.__setattr__(self, "book_key", _required_key(self.book_key, "book_key"))
        object.__setattr__(
            self,
            "idempotency_key",
            _required_key(self.idempotency_key, "idempotency_key"),
        )
        if not isinstance(self.effective_date, date):
            raise DomainValidationError("effective_date must be a date")
        transactions = tuple(self.transactions)
        if not transactions:
            raise DomainValidationError("a transaction batch must not be empty")
        if not all(isinstance(item, (LedgerTransaction, AccountTransaction)) for item in transactions):
            raise DomainValidationError("batch contains an unsupported transaction form")
        keys = [item.transaction_key for item in transactions]
        if len(keys) != len(set(keys)):
            raise DomainValidationError("transaction keys must be unique within a batch")
        object.__setattr__(self, "transactions", transactions)
        if self.reversal_of_batch_key is not None:
            object.__setattr__(
                self,
                "reversal_of_batch_key",
                _required_key(self.reversal_of_batch_key, "reversal_of_batch_key"),
            )

    def reversed(
        self,
        *,
        batch_key: str,
        idempotency_key: str,
        effective_date: date,
    ) -> "TransactionBatch":
        reversed_transactions = tuple(
            transaction.reversed(transaction_key=f"{transaction.transaction_key}:REV")
            for transaction in reversed(self.transactions)
        )
        return TransactionBatch(
            batch_key=batch_key,
            book_key=self.book_key,
            idempotency_key=idempotency_key,
            effective_date=effective_date,
            transactions=reversed_transactions,
            reversal_of_batch_key=self.batch_key,
        )
