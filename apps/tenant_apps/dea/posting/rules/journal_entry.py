"""
Journal Entry Voucher Posting Rules

JOURNAL ENTRY POSTING PATTERN:
- Simply posts the lines as entered by user
- No automatic generation - manual entry only
- All validation done at data entry time
- Supports all 7 journal entry types
"""

from django.core.exceptions import ValidationError
from ..types import DualLedgerLine, LedgerLine, PostingBundle
from .base import BasePostingRule
from ..registry import register_rule


@register_rule("JOURNAL_ENTRY_CLOSING")
@register_rule("JOURNAL_ENTRY_ACCRUAL")
@register_rule("JOURNAL_ENTRY_CORRECTION")
@register_rule("JOURNAL_ENTRY_ADJUSTMENT")
@register_rule("JOURNAL_ENTRY_INTERCORP")
@register_rule("JOURNAL_ENTRY_EXCHANGE")
@register_rule("JOURNAL_ENTRY_OTHER")
class JournalEntryRule(BasePostingRule):
    """
    Posting rule for manual journal adjustments.

    The create/update UI captures complete debit/credit pairs, and the stored
    `JournalEntryLineItem` rows are interpreted in DR/CR order to emit one
    `DualLedgerLine` per complete posting pair.
    """

    voucher_type = "JOURNAL_ENTRY"
    rule_version = "2"

    def build_posting(self, ctx) -> PostingBundle:
        """Build posting from ordered DR/CR line pairs."""
        doc = ctx.doc if hasattr(ctx, "doc") else ctx

        if not hasattr(doc, "line_items"):
            raise ValidationError("Document must have line_items")
        if not doc.is_balanced:
            raise ValidationError(
                f"Entry not balanced: Difference = {doc.balance_difference}"
            )

        ordered_lines = list(doc.line_items.all().order_by("line_number", "id"))
        if not ordered_lines:
            raise ValidationError("Journal adjustment has no line items to post.")

        ledger_lines = []
        validation_legs = []
        pending_debit = None

        for je_line in ordered_lines:
            amount = je_line.amount.amount
            currency = str(je_line.amount.currency)
            validation_legs.append(
                LedgerLine(
                    ledger_id=je_line.ledger_id,
                    side="Dr" if je_line.side == "DR" else "Cr",
                    currency=currency,
                    amount=amount,
                    amount_base=amount,
                )
            )

            if je_line.side == "DR":
                if pending_debit is not None:
                    raise ValidationError(
                        "Journal adjustment lines must be entered as debit/credit pairs."
                    )
                pending_debit = je_line
                continue

            if pending_debit is None:
                raise ValidationError(
                    "A credit line was found without a preceding debit line."
                )

            if (
                pending_debit.amount.currency != je_line.amount.currency
                or pending_debit.amount.amount != je_line.amount.amount
            ):
                raise ValidationError(
                    "Each debit/credit pair must use the same amount and currency."
                )

            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=pending_debit.ledger_id,
                    credit_ledger_id=je_line.ledger_id,
                    currency=currency,
                    amount=amount,
                    amount_base=amount,
                )
            )
            pending_debit = None

        if pending_debit is not None:
            raise ValidationError(
                "The last posting row is incomplete. Every debit must be followed by a credit."
            )

        return PostingBundle(
            ledger_lines=ledger_lines,
            account_lines=[],
            _validation_legs=validation_legs,
        )

    def fingerprint_payload(self, ctx):
        doc = ctx.doc if hasattr(ctx, "doc") else ctx
        rows = [
            {
                "line_number": line.line_number,
                "ledger_id": line.ledger_id,
                "side": line.side,
                "amount": str(line.amount.amount),
                "currency": str(line.amount.currency),
                "description": line.description,
            }
            for line in doc.line_items.all().order_by("line_number", "id")
        ]
        return {
            "voucher_type": doc.get_voucher_type(),
            "je_number": doc.je_number,
            "entry_type": doc.entry_type,
            "je_date": str(doc.je_date),
            "rows": rows,
        }
