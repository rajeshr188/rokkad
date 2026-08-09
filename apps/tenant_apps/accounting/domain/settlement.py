"""Non-financial open-item allocation contracts for the accounting proof.

Allocations explain which open items an already-defined account transaction
settles.  They never create or replace a monetary transaction.
"""

from __future__ import annotations

from dataclasses import dataclass

from .transactions import (
    AccountTransaction,
    DomainValidationError,
    MonetaryAmount,
    _required_key,
)


@dataclass(frozen=True, slots=True)
class OpenItemAllocation:
    open_item_key: str
    external_account_key: str
    money: MonetaryAmount

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "open_item_key", _required_key(self.open_item_key, "open_item_key")
        )
        object.__setattr__(
            self,
            "external_account_key",
            _required_key(self.external_account_key, "external_account_key"),
        )
        if not isinstance(self.money, MonetaryAmount):
            raise DomainValidationError("allocation money must be a MonetaryAmount")


@dataclass(frozen=True, slots=True)
class AccountSettlement:
    """Allocation explanation for one external-account transaction."""

    settlement_key: str
    account_transaction: AccountTransaction
    allocations: tuple[OpenItemAllocation, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "settlement_key", _required_key(self.settlement_key, "settlement_key")
        )
        if not isinstance(self.account_transaction, AccountTransaction):
            raise DomainValidationError(
                "account_transaction must be an AccountTransaction"
            )
        allocations = tuple(self.allocations)
        if not allocations:
            raise DomainValidationError("a settlement must contain an allocation")
        if not all(isinstance(item, OpenItemAllocation) for item in allocations):
            raise DomainValidationError("settlement contains an invalid allocation")
        open_item_keys = [item.open_item_key for item in allocations]
        if len(open_item_keys) != len(set(open_item_keys)):
            raise DomainValidationError(
                "an open item may be allocated only once per settlement"
            )
        transaction_money = self.account_transaction.money
        for allocation in allocations:
            if allocation.external_account_key != self.account_transaction.external_account_key:
                raise DomainValidationError(
                    "allocation external account must match the settlement transaction"
                )
            if (
                allocation.money.currency != transaction_money.currency
                or allocation.money.base_currency != transaction_money.base_currency
            ):
                raise DomainValidationError(
                    "allocation currencies must match the settlement transaction"
                )
        if sum(item.money.amount for item in allocations) > transaction_money.amount:
            raise DomainValidationError(
                "allocated transaction amount exceeds the settlement transaction"
            )
        if sum(item.money.base_amount for item in allocations) > transaction_money.base_amount:
            raise DomainValidationError(
                "allocated base amount exceeds the settlement transaction"
            )
        object.__setattr__(self, "allocations", allocations)

    @property
    def unallocated_amount(self):
        return self.account_transaction.money.amount - sum(
            item.money.amount for item in self.allocations
        )

    @property
    def unallocated_base_amount(self):
        return self.account_transaction.money.base_amount - sum(
            item.money.base_amount for item in self.allocations
        )
