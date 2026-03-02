"""
Journal Entry Voucher Posting Rules

JOURNAL ENTRY POSTING PATTERN:
- Simply posts the lines as entered by user
- No automatic generation - manual entry only
- All validation done at data entry time
- Supports all 7 journal entry types
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine
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
    Posting rule for manual journal entries.

    Simply posts the lines as entered by user without transformation.
    All validation is done at data entry time (balanced, line count, etc).

    Uses the ledger_id directly from each line item.
    """

    voucher_type = "JOURNAL_ENTRY"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        """Build posting from journal entry lines"""
        doc = ctx.doc if hasattr(ctx, "doc") else ctx

        # Validate document
        if not hasattr(doc, "line_items"):
            raise ValidationError("Document must have line_items")

        # Validate balanced
        if not doc.is_balanced:
            raise ValidationError(
                f"Entry not balanced: Difference = {doc.balance_difference}"
            )

        lines = []

        # Add each line from journal entry
        for je_line in doc.line_items.all():
            if je_line.side == "DR":
                # Debit line
                lines.append(
                    DualLedgerLine(
                        ledger_dr=je_line.ledger_id,
                        ledger_cr=None,
                        amount=je_line.amount.amount,
                        memo=je_line.description,
                    )
                )
            else:  # CR
                # Credit line
                lines.append(
                    DualLedgerLine(
                        ledger_dr=None,
                        ledger_cr=je_line.ledger_id,
                        amount=je_line.amount.amount,
                        memo=je_line.description,
                    )
                )

        return PostingBundle(
            voucher_type=doc.get_voucher_type(),
            voucher_number=doc.je_number,
            voucher_date=doc.je_date,
            description=f"{doc.get_entry_type_display()}: {doc.description}",
            lines=lines,
            account_lines=[],
        )
