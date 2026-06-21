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
from .party_accounts import resolve_given_loan_borrower_account
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

        borrower_account = resolve_given_loan_borrower_account(source_loan)

        # Resolve ledgers
        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)
        # LT target: internal principal flow control ledger
        loan_principal_ctrl_id = get_ledger_id_by_key(
            "LOAN_PRINCIPAL_CTRL", tenant_id=tenant_id
        )
        # AT target: party attribution control ledger (separate from LT target)
        borrower_loan_ctrl_id = get_ledger_id_by_key(
            "BORROWER_LOAN_CTRL", tenant_id=tenant_id
        )

        if not cash_id or not loan_principal_ctrl_id or not borrower_loan_ctrl_id:
            raise ValidationError(
                "Required ledgers (CASH, LOAN_PRINCIPAL_CTRL, BORROWER_LOAN_CTRL) not found"
            )

        ledger_lines = []

        # Principal: Dr CASH, Cr LOAN_PRINCIPAL_CTRL
        if principal_decimal > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=cash_id,
                    credit_ledger_id=loan_principal_ctrl_id,
                    currency=str(payment.total_amount.currency),
                    amount=principal_decimal,
                    amount_base=principal_decimal,
                )
            )

        # Interest: first clear any booked receivable, then recognise fresh income.
        if interest_decimal > 0:
            receivable_balance = Decimal("0")
            receivable_balance_fn = getattr(source_loan, "interest_receivable_balance", None)
            if callable(receivable_balance_fn):
                receivable_balance = Decimal(str(receivable_balance_fn() or 0))

            receivable_portion = min(interest_decimal, receivable_balance)
            income_portion = interest_decimal - receivable_portion

            if receivable_portion > 0:
                interest_receivable_id = get_ledger_id_by_key(
                    "INTEREST_RECEIVABLE", tenant_id=tenant_id
                )
                ledger_lines.append(
                    DualLedgerLine(
                        debit_ledger_id=cash_id,
                        credit_ledger_id=interest_receivable_id,
                        currency=str(payment.total_amount.currency),
                        amount=receivable_portion,
                        amount_base=receivable_portion,
                    )
                )

            if income_portion > 0:
                interest_income_id = get_ledger_id_by_key(
                    "INTEREST_INCOME", tenant_id=tenant_id
                )
                if not interest_income_id:
                    raise ValidationError("Required ledger INTEREST_INCOME not found")
                ledger_lines.append(
                    DualLedgerLine(
                        debit_ledger_id=cash_id,
                        credit_ledger_id=interest_income_id,
                        currency=str(payment.total_amount.currency),
                        amount=income_portion,
                        amount_base=income_portion,
                    )
                )

        # Account line: principal reduces borrower's debt against BORROWER_LOAN_CTRL
        account_lines = []
        if principal_decimal > 0:
            account_lines.append(
                AccountLine(
                    ledger_id=borrower_loan_ctrl_id,
                    account_id=borrower_account.id,
                    side="Cr",
                    currency=str(payment.total_amount.currency),
                    amount=principal_decimal,
                    amount_base=principal_decimal,
                    xact_type_ext="RP",  # Repayment Principal
                )
            )

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
