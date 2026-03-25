"""
TakenLoan Receipt Posting Rule
Generated: February 26, 2026

When we receive a loan (money from lender):
- Dr CASH (we receive money)
- Cr BORROWING_PRINCIPAL_CTRL (internal principal liability control)
- AT Cr LENDER_ACCOUNT_CTRL (lender subledger attribution)
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from moneyed import Money

from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("TAKENLOAN_RECEIPT")
class TakenLoanReceiptRule(BasePostingRule):
    """
    Posting rule for TakenLoan receipts (when we receive borrowed money).

    When we receive a loan from a lender:
    - Dr CASH (money coming in)
    - Cr BORROWING_PRINCIPAL_CTRL (internal liability control)

    Plus subledger entry:
    - Lender account: CREDIT against LENDER_ACCOUNT_CTRL (we owe them)
    """

    voucher_type = "TAKENLOAN_RECEIPT"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        """
        Build posting bundle for loan receipt.

        ctx.doc = PaymentVoucher instance
        """
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)

        # Extract economic data - principal amount
        principal_amount = payment.principal_amount or payment.total_amount

        # Get amount as Decimal
        principal_decimal = Decimal(str(principal_amount.amount))

        # Validation
        if principal_decimal <= 0:
            raise ValidationError("Receipt amount must be positive")

        # Get source loan
        source_loan = payment.source_loan
        if not source_loan:
            raise ValidationError("Cannot find source TakenLoan")

        if not hasattr(source_loan, "lender") or not source_loan.lender:
            raise ValidationError("Loan has no lender")

        if not hasattr(source_loan.lender, "account") or not source_loan.lender.account:
            raise ValidationError(f"Lender {source_loan.lender} has no account")

        # Resolve ledgers
        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)
        # LT target: internal borrowing fund flow control ledger
        borrowing_principal_ctrl_id = get_ledger_id_by_key(
            "BORROWING_PRINCIPAL_CTRL", tenant_id=tenant_id
        )
        # AT target: party attribution control ledger (separate from LT target)
        lender_account_ctrl_id = get_ledger_id_by_key(
            "LENDER_ACCOUNT_CTRL", tenant_id=tenant_id
        )

        if not cash_id or not borrowing_principal_ctrl_id or not lender_account_ctrl_id:
            raise ValidationError(
                "Required ledgers (CASH, BORROWING_PRINCIPAL_CTRL, LENDER_ACCOUNT_CTRL) not found"
            )

        # Build posting - dual-leg ledger entry
        # Dr CASH, Cr BORROWING_PRINCIPAL_CTRL (internal fund flow)
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=cash_id,
                credit_ledger_id=borrowing_principal_ctrl_id,
                amount=principal_decimal,
                amount_base=principal_decimal,
            )
        ]

        # Account line for lender against LENDER_ACCOUNT_CTRL (CREDIT - we owe them)
        account_lines = [
            AccountLine(
                ledger_id=lender_account_ctrl_id,
                account_id=source_loan.lender.account.id,
                side="Cr",
                currency=str(payment.total_amount.currency),
                amount=principal_decimal,
                amount_base=principal_decimal,
                xact_type_ext="LR",  # Loan Received
            )
        ]

        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)

    def fingerprint_payload(self, ctx):
        """Economic payload for idempotency."""
        payment = ctx.doc
        source_loan = payment.source_loan

        return {
            "voucher_type": self.voucher_type,
            "rule_version": self.rule_version,
            "source_loan_id": source_loan.id if source_loan else None,
            "payment_id": payment.payment_id,
            "payment_date": payment.payment_date.isoformat()
            if payment.payment_date
            else None,
            "total_amount": str(payment.total_amount.amount),
            "currency": str(payment.total_amount.currency),
        }
