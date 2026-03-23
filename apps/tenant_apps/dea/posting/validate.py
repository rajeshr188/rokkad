from decimal import Decimal
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
    DualLedgerLine (ledger_lines) has debit_ledger_id + credit_ledger_id.
    AccountLine (account_lines) has ledger_id + account_id + side.
    """

    def _check_amounts(i, line):
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

    for i, line in enumerate(bundle.ledger_lines):
        _check_amounts(i, line)
        if line.debit_ledger_id in (None, 0):
            raise InvalidBundleError(f"Ledger line {i} missing debit_ledger_id.")
        if line.credit_ledger_id in (None, 0):
            raise InvalidBundleError(f"Ledger line {i} missing credit_ledger_id.")

    for i, line in enumerate(bundle.account_lines):
        _check_amounts(i, line)
        if line.ledger_id in (None, 0):
            raise InvalidBundleError(f"Account line {i} missing ledger_id.")
        if line.account_id in (None, 0):
            raise InvalidBundleError(f"Account line {i} missing account_id.")
        if line.side not in ("Dr", "Cr"):
            raise InvalidBundleError(f"Account line {i} invalid side {line.side!r}.")


def assert_balanced(bundle: PostingBundle) -> None:
    """
    Verify the bundle is balanced.

    Architecture semantics:
    - DualLedgerLine: each entry encodes ONE amount for BOTH the debit leg and the
      credit leg, so it is inherently balanced (Dr == Cr by construction).  We only
      add a sanity-check that an entry doesn't point to the same ledger on both sides.
    - AccountLine: sub-ledger detail (records ONE account's movement). These are
      intentionally one-sided and must NOT be included in the global Dr/Cr sum.
    - AccountLine-only bundles (no ledger_lines): if no DualLedgerLine is present
      the caller is expected to provide balanced Dr/Cr account_lines; we check that.
    """
    if bundle.ledger_lines:
        # Sanity-check: circular entry (Dr == Cr to same ledger) is meaningless.
        for i, line in enumerate(bundle.ledger_lines):
            if line.debit_ledger_id == line.credit_ledger_id:
                raise InvalidBundleError(
                    f"Ledger line {i} has same debit and credit ledger "
                    f"(id={line.debit_ledger_id}). Circular entry."
                )
        # Each DualLedgerLine is balanced by construction — no net sum check needed.
        return

    # AccountLine-only bundle: enforce Dr sum == Cr sum per currency.
    per_currency = {}
    for line in bundle.account_lines:
        cur = line.currency
        per_currency.setdefault(cur, _DECIMAL_ZERO)
        per_currency[cur] += line.amount if line.side == "Dr" else -line.amount

    unbalanced = {
        c: bal for c, bal in per_currency.items() if bal.copy_abs() > _TOLERANCE
    }
    if unbalanced:
        msg = "; ".join(f"{c} net={v}" for c, v in unbalanced.items())
        raise UnbalancedError(f"Bundle not balanced per currency: {msg}")
