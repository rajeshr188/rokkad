"""
TakenLoan Payment Posting Rule
Generated: February 26, 2026

When we repay a loan (money to lender):
- Dr LOAN_PAYABLE (our liability reduces)
- Cr CASH (money goes out)
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from moneyed import Money

from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("TAKENLOAN_PAYMENT")
class TakenLoanPaymentRule(BasePostingRule):
    """
    Posting rule for TakenLoan repayments.

    When we repay a loan to the lender:
    - Dr LOAN_PAYABLE (our liability reduces)
    - Cr CASH (money goes out)

    Plus subledger entry:
    - Lender account: DEBIT (our debt to them reduces)
    """

    voucher_type = "TAKENLOAN_PAYMENT"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        """
        Build posting bundle for loan repayment.

        ctx.doc = PaymentVoucher instance
        """
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)

        # Extract economic data
        principal_amount = payment.principal_amount or payment.total_amount
        interest_amount = payment.interest_amount or Money(
            0, payment.total_amount.currency
        )

        # Get amount as Decimal
        principal_decimal = Decimal(str(principal_amount.amount))
        interest_decimal = Decimal(str(interest_amount.amount))
        total_decimal = principal_decimal + interest_decimal

        # Validation
        if total_decimal <= 0:
            raise ValidationError("Payment amount must be positive")

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
        loan_payable_id = get_ledger_id_by_key("LOAN_PAYABLE", tenant_id=tenant_id)

        if not cash_id or not loan_payable_id:
            raise ValidationError("Required ledgers (CASH, LOAN_PAYABLE) not found")

        # Build posting - dual-leg ledger entry
        # Dr LOAN_PAYABLE, Cr CASH
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=loan_payable_id,
                credit_ledger_id=cash_id,
                amount=total_decimal,
                amount_base=total_decimal,
            )
        ]

        # Account line for lender (DEBIT side - our debt reduces)
        account_lines = [
            AccountLine(
                ledger_id=loan_payable_id,
                account_id=source_loan.lender.account.id,
                side="Dr",
                currency=str(payment.total_amount.currency),
                amount=total_decimal,
                amount_base=total_decimal,
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
