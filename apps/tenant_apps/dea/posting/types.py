from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import List, Optional, Protocol, Literal, Any, runtime_checkable

Side = Literal["Dr", "Cr"]


class VoucherStatus(str, Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    CORRECTED = "CORRECTED"
    REVERSED = "REVERSED"


@dataclass(frozen=True)
class LedgerLine:
    """Single-leg representation (for validation/rule logic)"""

    ledger_id: int
    side: Side
    currency: str
    amount: Decimal
    amount_base: Decimal


@dataclass(frozen=True)
class DualLedgerLine:
    """
    Dual-leg representation matching your LedgerTransaction model.
    One row = one complete double-entry pair.
    """

    debit_ledger_id: int  # Maps to ledgerno_dr
    credit_ledger_id: int  # Maps to ledgerno
    currency: str
    amount: Decimal
    amount_base: Decimal


@dataclass(frozen=True)
class AccountLine:
    ledger_id: int
    account_id: int
    side: Side
    currency: str
    amount: Decimal
    amount_base: Decimal
    xact_type_ext: str = "TXN"  # Default transaction extension type


@dataclass(frozen=True)
class PostingBundle:
    ledger_lines: List[DualLedgerLine]
    account_lines: List[AccountLine]
    # Optional: keep single legs for validation
    _validation_legs: Optional[List[LedgerLine]] = None


@runtime_checkable
class PostingRule(Protocol):
    """
    Contract for building a PostingBundle from a given context.

    Requirements:
    - rule_version: bump when logic affecting fingerprints changes.
    - voucher_type: string key used for registry lookup.
    - build_posting(ctx): pure/deterministic; returns balanced bundle.
    - fingerprint_payload(ctx): returns a JSON-serializable payload that
      uniquely represents the "economic intent" of the voucher for idempotency.
    """

    rule_version: str
    voucher_type: str

    def build_posting(self, ctx: Any) -> PostingBundle:
        ...

    def fingerprint_payload(self, ctx: Any) -> Any:
        ...


# domain errors


class PostingError(Exception):
    """Base domain error for posting subsystem."""

    def __init__(
        self, message: str, *, code: str | None = None, payload: Any | None = None
    ):
        self.code = code
        self.payload = payload
        super().__init__(message)

    def __repr__(self):
        return f"{self.__class__.__name__}(message={self.args[0]!r}, code={self.code!r}, payload={self.payload!r})"


class RuleNotFoundError(PostingError):
    """Raised when no PostingRule is registered for a voucher_type."""


class UnbalancedError(PostingError):
    """Raised when debits and credits do not net to zero per currency."""


class InvalidBundleError(PostingError):
    """Raised when the PostingBundle structure or values are invalid."""
