from django.core.exceptions import ValidationError

from ..registry import register_rule
from ..types import DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("PREPAID_EXPENSE")
class PrepaidExpensePostingRule(BasePostingRule):
    voucher_type = "PREPAID_EXPENSE"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        schedule = ctx.doc if hasattr(ctx, "doc") else ctx
        prepaid = getattr(schedule, "prepaid_expense", None)

        if prepaid is None:
            raise ValidationError("Prepaid schedule must reference a prepaid expense.")
        if not getattr(prepaid, "expense_ledger_id", None):
            raise ValidationError("Expense ledger is required.")
        if not getattr(prepaid, "prepaid_ledger_id", None):
            raise ValidationError("Prepaid ledger is required.")

        amount = getattr(schedule, "amount", None)
        if amount is None or amount.amount <= 0:
            raise ValidationError("Prepaid amortization amount must be positive.")

        return PostingBundle(
            ledger_lines=[
                DualLedgerLine(
                    debit_ledger_id=prepaid.expense_ledger_id,
                    credit_ledger_id=prepaid.prepaid_ledger_id,
                    currency=str(amount.currency),
                    amount=amount.amount,
                    amount_base=amount.amount,
                )
            ],
            account_lines=[],
        )
