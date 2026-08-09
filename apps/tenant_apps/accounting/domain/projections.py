"""Pure read projections over atomic accounting transaction batches.

These functions never create accounting effects.  They count the two sides of
each atomic transaction once and translate frozen external-account
classifications into financial-statement rows.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Iterable, Mapping

from .transactions import (
    AccountTransaction,
    DomainValidationError,
    LedgerSide,
    LedgerTransaction,
    ReportingClass,
    TransactionBatch,
    _required_key,
)


class PostingAccountKind(str, Enum):
    INTERNAL_LEDGER = "INTERNAL_LEDGER"
    EXTERNAL_ACCOUNT = "EXTERNAL_ACCOUNT"


@dataclass(frozen=True, slots=True)
class LedgerDefinition:
    ledger_key: str
    reporting_class: ReportingClass
    normal_side: LedgerSide

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "ledger_key", _required_key(self.ledger_key, "ledger_key")
        )
        if not isinstance(self.reporting_class, ReportingClass):
            raise DomainValidationError("reporting_class must be a ReportingClass")
        if not isinstance(self.normal_side, LedgerSide):
            raise DomainValidationError("normal_side must be a LedgerSide")


@dataclass(frozen=True, slots=True)
class JournalLineProjection:
    batch_key: str
    transaction_key: str
    posting_key: str
    account_kind: PostingAccountKind
    side: LedgerSide
    amount_base: Decimal
    base_currency: str
    classification_version_key: str | None = None

    @property
    def signed_base_amount(self) -> Decimal:
        return self.amount_base if self.side is LedgerSide.DEBIT else -self.amount_base


@dataclass(frozen=True, slots=True)
class BalanceProjection:
    key: str
    signed_base_amount: Decimal
    reporting_class: ReportingClass | None = None
    normal_side: LedgerSide | None = None

    @property
    def natural_base_amount(self) -> Decimal:
        if self.normal_side is LedgerSide.CREDIT:
            return -self.signed_base_amount
        return self.signed_base_amount


@dataclass(frozen=True, slots=True)
class TrialBalanceProjection:
    rows: tuple[BalanceProjection, ...]

    @property
    def signed_total(self) -> Decimal:
        return sum((row.signed_base_amount for row in self.rows), Decimal("0"))


@dataclass(frozen=True, slots=True)
class FinancialStatementProjection:
    balance_sheet_rows: tuple[BalanceProjection, ...]
    profit_and_loss_rows: tuple[BalanceProjection, ...]
    current_period_result: Decimal

    @property
    def balance_sheet_signed_total(self) -> Decimal:
        return sum(
            (row.signed_base_amount for row in self.balance_sheet_rows), Decimal("0")
        )


@dataclass(frozen=True, slots=True)
class ClassificationReconciliation:
    reporting_ledger_key: str
    external_account_total: Decimal
    direct_internal_ledger_total: Decimal
    trial_balance_total: Decimal

    @property
    def difference(self) -> Decimal:
        return self.trial_balance_total - (
            self.external_account_total + self.direct_internal_ledger_total
        )


def _all_transactions(batches: Iterable[TransactionBatch]):
    for batch in batches:
        if not isinstance(batch, TransactionBatch):
            raise DomainValidationError("projections require TransactionBatch values")
        for transaction in batch.transactions:
            yield batch, transaction


def project_journal_lines(
    batches: Iterable[TransactionBatch],
) -> tuple[JournalLineProjection, ...]:
    """Expose the paired model as conventional one-sided journal lines."""

    rows: list[JournalLineProjection] = []
    for batch, transaction in _all_transactions(batches):
        if isinstance(transaction, LedgerTransaction):
            rows.extend(
                (
                    JournalLineProjection(
                        batch_key=batch.batch_key,
                        transaction_key=transaction.transaction_key,
                        posting_key=transaction.debit_ledger_key,
                        account_kind=PostingAccountKind.INTERNAL_LEDGER,
                        side=LedgerSide.DEBIT,
                        amount_base=transaction.money.base_amount,
                        base_currency=transaction.money.base_currency,
                    ),
                    JournalLineProjection(
                        batch_key=batch.batch_key,
                        transaction_key=transaction.transaction_key,
                        posting_key=transaction.credit_ledger_key,
                        account_kind=PostingAccountKind.INTERNAL_LEDGER,
                        side=LedgerSide.CREDIT,
                        amount_base=transaction.money.base_amount,
                        base_currency=transaction.money.base_currency,
                    ),
                )
            )
        elif isinstance(transaction, AccountTransaction):
            rows.extend(
                (
                    JournalLineProjection(
                        batch_key=batch.batch_key,
                        transaction_key=transaction.transaction_key,
                        posting_key=transaction.ledger_key,
                        account_kind=PostingAccountKind.INTERNAL_LEDGER,
                        side=transaction.ledger_side,
                        amount_base=transaction.money.base_amount,
                        base_currency=transaction.money.base_currency,
                    ),
                    JournalLineProjection(
                        batch_key=batch.batch_key,
                        transaction_key=transaction.transaction_key,
                        posting_key=transaction.external_account_key,
                        account_kind=PostingAccountKind.EXTERNAL_ACCOUNT,
                        side=transaction.external_account_side,
                        amount_base=transaction.money.base_amount,
                        base_currency=transaction.money.base_currency,
                        classification_version_key=transaction.classification.version_key,
                    ),
                )
            )
    return tuple(rows)


def project_internal_ledger_balances(
    batches: Iterable[TransactionBatch],
) -> tuple[BalanceProjection, ...]:
    balances: dict[str, Decimal] = defaultdict(Decimal)
    for line in project_journal_lines(batches):
        if line.account_kind is PostingAccountKind.INTERNAL_LEDGER:
            balances[line.posting_key] += line.signed_base_amount
    return tuple(
        BalanceProjection(key=key, signed_base_amount=amount)
        for key, amount in sorted(balances.items())
        if amount
    )


def project_external_account_balances(
    batches: Iterable[TransactionBatch],
) -> tuple[BalanceProjection, ...]:
    balances: dict[str, Decimal] = defaultdict(Decimal)
    for line in project_journal_lines(batches):
        if line.account_kind is PostingAccountKind.EXTERNAL_ACCOUNT:
            balances[line.posting_key] += line.signed_base_amount
    return tuple(
        BalanceProjection(key=key, signed_base_amount=amount)
        for key, amount in sorted(balances.items())
        if amount
    )


def project_trial_balance(
    batches: Iterable[TransactionBatch],
    *,
    ledger_definitions: Mapping[str, LedgerDefinition],
) -> TrialBalanceProjection:
    """Combine internal ledgers and classified external sides exactly once."""

    materialized_batches = tuple(batches)
    balances: dict[str, Decimal] = defaultdict(Decimal)
    metadata: dict[str, tuple[ReportingClass, LedgerSide]] = {}

    for line in project_journal_lines(materialized_batches):
        if line.account_kind is not PostingAccountKind.INTERNAL_LEDGER:
            continue
        try:
            definition = ledger_definitions[line.posting_key]
        except KeyError as exc:
            raise DomainValidationError(
                f"missing ledger definition for {line.posting_key}"
            ) from exc
        if definition.ledger_key != line.posting_key:
            raise DomainValidationError("ledger definition key does not match its mapping key")
        balances[line.posting_key] += line.signed_base_amount
        metadata[line.posting_key] = (
            definition.reporting_class,
            definition.normal_side,
        )

    for _, transaction in _all_transactions(materialized_batches):
        if not isinstance(transaction, AccountTransaction):
            continue
        key = transaction.classification.reporting_ledger_key
        classification_metadata = (
            transaction.classification.reporting_class,
            transaction.classification.normal_side,
        )
        existing = metadata.get(key)
        if existing is not None and existing != classification_metadata:
            raise DomainValidationError(
                f"inconsistent reporting classification for {key}"
            )
        metadata[key] = classification_metadata
        external_sign = (
            Decimal("1")
            if transaction.external_account_side is LedgerSide.DEBIT
            else Decimal("-1")
        )
        balances[key] += external_sign * transaction.money.base_amount

    rows = tuple(
        BalanceProjection(
            key=key,
            signed_base_amount=amount,
            reporting_class=metadata[key][0],
            normal_side=metadata[key][1],
        )
        for key, amount in sorted(balances.items())
        if amount
    )
    result = TrialBalanceProjection(rows=rows)
    if result.signed_total != 0:
        raise DomainValidationError(
            f"projected trial balance is not balanced: {result.signed_total}"
        )
    return result


def project_financial_statements(
    batches: Iterable[TransactionBatch],
    *,
    ledger_definitions: Mapping[str, LedgerDefinition],
) -> FinancialStatementProjection:
    trial_balance = project_trial_balance(
        batches, ledger_definitions=ledger_definitions
    )
    balance_sheet_classes = {
        ReportingClass.ASSET,
        ReportingClass.LIABILITY,
        ReportingClass.EQUITY,
    }
    profit_and_loss_classes = {
        ReportingClass.REVENUE,
        ReportingClass.EXPENSE,
        ReportingClass.GAIN,
        ReportingClass.LOSS,
    }
    profit_and_loss_rows = tuple(
        row
        for row in trial_balance.rows
        if row.reporting_class in profit_and_loss_classes
    )
    current_period_result = -sum(
        (row.signed_base_amount for row in profit_and_loss_rows), Decimal("0")
    )
    balance_sheet_rows = [
        row for row in trial_balance.rows if row.reporting_class in balance_sheet_classes
    ]
    if current_period_result:
        balance_sheet_rows.append(
            BalanceProjection(
                key="CURRENT_PERIOD_RESULT",
                signed_base_amount=-current_period_result,
                reporting_class=ReportingClass.EQUITY,
                normal_side=LedgerSide.CREDIT,
            )
        )
    result = FinancialStatementProjection(
        balance_sheet_rows=tuple(balance_sheet_rows),
        profit_and_loss_rows=profit_and_loss_rows,
        current_period_result=current_period_result,
    )
    if result.balance_sheet_signed_total != 0:
        raise DomainValidationError(
            "projected balance sheet does not balance after current-period result"
        )
    return result


def reconcile_external_classifications(
    batches: Iterable[TransactionBatch],
    *,
    ledger_definitions: Mapping[str, LedgerDefinition],
) -> tuple[ClassificationReconciliation, ...]:
    """Reconcile external accounts to their frozen reporting classifications."""

    materialized_batches = tuple(batches)
    external_totals: dict[str, Decimal] = defaultdict(Decimal)
    for _, transaction in _all_transactions(materialized_batches):
        if not isinstance(transaction, AccountTransaction):
            continue
        amount = transaction.money.base_amount
        sign = Decimal("1") if transaction.external_account_side is LedgerSide.DEBIT else Decimal("-1")
        external_totals[transaction.classification.reporting_ledger_key] += sign * amount

    internal_by_key = {
        row.key: row.signed_base_amount
        for row in project_internal_ledger_balances(materialized_batches)
    }
    trial_by_key = {
        row.key: row.signed_base_amount
        for row in project_trial_balance(
            materialized_batches, ledger_definitions=ledger_definitions
        ).rows
    }
    return tuple(
        ClassificationReconciliation(
            reporting_ledger_key=key,
            external_account_total=external_totals[key],
            direct_internal_ledger_total=internal_by_key.get(key, Decimal("0")),
            trial_balance_total=trial_by_key.get(key, Decimal("0")),
        )
        for key in sorted(external_totals)
    )
