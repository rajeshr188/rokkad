"""
GivenLoan Disbursal Posting Rule
Generated: February 26, 2026

When we give out a loan (disburse it):
- Dr LOAN_RECEIVABLE (we now have a receivable)
- Cr CASH (money goes out)
- Plus subledger for the customer account
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from moneyed import Money

from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from .party_accounts import resolve_given_loan_borrower_account
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("GIVENLOAN_PAYMENT")
class GivenLoanDisbursalRule(BasePostingRule):
    """
    Posting rule for GivenLoan disbursals.

    When we give out a loan:
    - Dr LOAN_RECEIVABLE (we now have a receivable from the borrower)
    - Cr CASH (money goes out)

    Plus subledger entry:
    - Customer account: DEBIT (they owe us)
    """

    voucher_type = "GIVENLOAN_PAYMENT"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        """
        Build posting bundle for loan disbursal.

        ctx.doc = PaymentVoucher instance
        """
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)

        # Extract economic data.
        # For GivenLoan disbursal with deductions:
        # - principal_amount = gross principal receivable
        # - total_amount = net cash payout
        # - interest_amount + fee_amount are deducted components
        principal_amount = payment.principal_amount or payment.total_amount
        interest_amount = payment.interest_amount or Money(0, payment.total_amount.currency)
        fee_amount = payment.fee_amount or Money(0, payment.total_amount.currency)
        net_cash_amount = payment.total_amount

        # Get amount as Decimal
        principal_decimal = Decimal(str(principal_amount.amount))
        interest_decimal = Decimal(str(interest_amount.amount))
        fee_decimal = Decimal(str(fee_amount.amount))
        net_cash_decimal = Decimal(str(net_cash_amount.amount))

        # Validation
        if principal_decimal <= 0:
            raise ValidationError("Disbursal amount must be positive")
        if interest_decimal < 0 or fee_decimal < 0:
            raise ValidationError("Disbursal deductions cannot be negative")
        if net_cash_decimal < 0:
            raise ValidationError("Net disbursal cash amount cannot be negative")
        if net_cash_decimal + interest_decimal + fee_decimal != principal_decimal:
            raise ValidationError(
                "GivenLoan disbursal components must satisfy principal = net cash + interest deduction + document charge"
            )

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

        interest_income_id = None
        if interest_decimal > 0:
            interest_income_id = get_ledger_id_by_key("INTEREST_INCOME", tenant_id=tenant_id)

        document_charge_income_id = None
        if fee_decimal > 0:
            try:
                document_charge_income_id = get_ledger_id_by_key(
                    "DOCUMENT_CHARGE_INCOME",
                    tenant_id=tenant_id,
                )
            except ValidationError:
                document_charge_income_id = get_ledger_id_by_key(
                    "INTEREST_INCOME",
                    tenant_id=tenant_id,
                )

        # Build posting - dual-leg ledger entry
        # Dr LOAN_PRINCIPAL_CTRL for gross principal,
        # then credit net cash and deduction income ledgers.
        ledger_lines = []
        if net_cash_decimal > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=loan_principal_ctrl_id,
                    credit_ledger_id=cash_id,
                    currency=str(payment.total_amount.currency),
                    amount=net_cash_decimal,
                    amount_base=net_cash_decimal,
                )
            )
        if interest_decimal > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=loan_principal_ctrl_id,
                    credit_ledger_id=interest_income_id,
                    currency=str(payment.total_amount.currency),
                    amount=interest_decimal,
                    amount_base=interest_decimal,
                )
            )
        if fee_decimal > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=loan_principal_ctrl_id,
                    credit_ledger_id=document_charge_income_id,
                    currency=str(payment.total_amount.currency),
                    amount=fee_decimal,
                    amount_base=fee_decimal,
                )
            )

        # Account line for borrower against BORROWER_LOAN_CTRL (DEBIT - they owe us)
        account_lines = [
            AccountLine(
                ledger_id=borrower_loan_ctrl_id,
                account_id=borrower_account.id,
                side="Dr",
                currency=str(payment.total_amount.currency),
                amount=principal_decimal,
                amount_base=principal_decimal,
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
            "principal_amount": str(payment.principal_amount.amount)
            if payment.principal_amount
            else None,
            "interest_amount": str(payment.interest_amount.amount)
            if payment.interest_amount
            else None,
            "fee_amount": str(payment.fee_amount.amount) if payment.fee_amount else None,
            "currency": str(payment.total_amount.currency),
        }
