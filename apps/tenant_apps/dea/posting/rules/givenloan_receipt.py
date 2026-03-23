"""
GivenLoan Receipt Posting Rule
Generated: February 26, 2026

When we receive payment on a loan we gave out:
- Dr CASH (money comes in)
- Cr LOAN_RECEIVABLE (our loan receivable decreases)
- Also update subledger for the customer account
"""

from decimal import Decimal
from django.core.exceptions import ValidationError

from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("GIVENLOAN_RECEIPT")
class GivenLoanReceiptRule(BasePostingRule):
    """
    Posting rule for GivenLoan payment receipts.

    When we receive a payment back on a loan we gave:
    - Dr CASH (money coming in)
    - Cr LOAN_RECEIVABLE (our receivable reduces)

    Plus subledger entry:
    - Customer account: CREDIT (their debt reduces)
    """

    voucher_type = "GIVENLOAN_RECEIPT"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        """
        Build posting bundle for loan receipt.

        ctx.doc = PaymentVoucher instance
        """
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)

        # Extract economic data
        principal_amount = payment.principal_amount or payment.total_amount
        interest_amount = payment.interest_amount or Money(
            0, payment.total_amount.currency
        )

        # Get amount as Decimal (work in base currency)
        principal_decimal = Decimal(str(principal_amount.amount))
        interest_decimal = Decimal(str(interest_amount.amount))
        total_decimal = principal_decimal + interest_decimal

        # Validation
        if total_decimal <= 0:
            raise ValidationError("Receipt amount must be positive")

        # Get source loan to access borrower/customer account
        source_loan = payment.source_loan
        if not source_loan:
            raise ValidationError("Cannot find source GivenLoan")

        # Current GivenLoan model uses borrower; keep customer as legacy fallback.
        party = getattr(source_loan, "borrower", None) or getattr(
            source_loan, "customer", None
        )
        if not party:
            raise ValidationError("Loan has no borrower/customer")

        if not hasattr(party, "account") or not party.account:
            raise ValidationError(f"Borrower/customer {party} has no account")

        # Resolve ledgers
        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)
        loan_receivable_id = get_ledger_id_by_key(
            "LOAN_RECEIVABLE", tenant_id=tenant_id
        )

        if not cash_id or not loan_receivable_id:
            raise ValidationError("Required ledgers (CASH, LOAN_RECEIVABLE) not found")

        # Build posting - dual-leg ledger entry
        # Dr CASH, Cr LOAN_RECEIVABLE
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=cash_id,
                credit_ledger_id=loan_receivable_id,
                amount=total_decimal,
                amount_base=total_decimal,
            )
        ]

        # Account line for borrower/customer (CREDIT side - reduces their debt)
        account_lines = [
            AccountLine(
                ledger_id=loan_receivable_id,
                account_id=party.account.id,
                side="Cr",
                currency=str(payment.total_amount.currency),
                amount=total_decimal,
                amount_base=total_decimal,
                xact_type_ext="LG",  # Loan Given
            )
        ]

        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)

    def fingerprint_payload(self, ctx):
        """
        Economic payload for idempotency.
        """
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


from moneyed import Money
