from decimal import Decimal
from typing import Iterable
from .types import PostingBundle, UnbalancedError, InvalidBundleError

_DECIMAL_ZERO = Decimal("0")
_TOLERANCE = Decimal("0.000001")  # to absorb tiny rounding differences


def assert_non_empty(bundle: PostingBundle) -> None:
    if not bundle.ledger_lines and not bundle.account_lines:
        raise InvalidBundleError(
            "Posting bundle is empty (no ledger or account lines)."
        )


def assert_currency_fields(bundle: PostingBundle) -> None:
    """
    Basic structural validation:
    - currency must be a non-empty string
    - amount and amount_base must be Decimal and >= 0
    - ledger_id / account_id positive ints
    """

    def _check_lines(lines: Iterable):
        for i, line in enumerate(lines):
            if not isinstance(line.currency, str) or not line.currency:
                raise InvalidBundleError(
                    f"Line {i} has invalid currency: {line.currency!r}"
                )
            if not isinstance(line.amount, Decimal):
                raise InvalidBundleError(
                    f"Line {i} amount must be Decimal, got {type(line.amount)}"
                )
            if not isinstance(line.amount_base, Decimal):
                raise InvalidBundleError(
                    f"Line {i} amount_base must be Decimal, got {type(line.amount_base)}"
                )
            if line.amount < _DECIMAL_ZERO:
                raise InvalidBundleError(f"Line {i} amount negative: {line.amount}")
            if line.amount_base < _DECIMAL_ZERO:
                raise InvalidBundleError(
                    f"Line {i} amount_base negative: {line.amount_base}"
                )
            if getattr(line, "ledger_id", None) in (None, 0):
                raise InvalidBundleError(f"Line {i} missing ledger_id.")
            # account lines only
            if hasattr(line, "account_id") and line.account_id in (None, 0):
                raise InvalidBundleError(f"Line {i} missing account_id.")
            if line.side not in ("Dr", "Cr"):
                raise InvalidBundleError(f"Line {i} invalid side {line.side!r}.")

    _check_lines(bundle.ledger_lines)
    _check_lines(bundle.account_lines)


def assert_balanced(bundle: PostingBundle) -> None:
    """
    Ensure debits == credits per currency across ALL lines (ledger + account).
    You can split into two checks if you want independent balancing; here we enforce global balance.
    """
    per_currency = {}

    def _accumulate(lines: Iterable):
        for line in lines:
            cur = line.currency
            per_currency.setdefault(cur, _DECIMAL_ZERO)
            amt = line.amount
            if line.side == "Dr":
                per_currency[cur] += amt
            else:
                per_currency[cur] -= amt

    _accumulate(bundle.ledger_lines)
    _accumulate(bundle.account_lines)

    unbalanced = {
        c: bal for c, bal in per_currency.items() if bal.copy_abs() > _TOLERANCE
    }
    if unbalanced:
        msg = "; ".join(f"{c} net={v}" for c, v in unbalanced.items())
        raise UnbalancedError(f"Bundle not balanced per currency: {msg}")
