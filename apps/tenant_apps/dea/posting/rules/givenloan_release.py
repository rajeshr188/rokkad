"""
GivenLoan Release Posting Rule

When a GivenLoan is released (collateral returned, loan repaid):
  Principal:  Dr CASH / Cr LOAN_PRINCIPAL_CTRL
  Interest:   Dr CASH / Cr INTEREST_INCOME  (if interest_amount > 0)
  Subledger:  AT -- Cr BORROWER_LOAN_CTRL (borrower's receivable closes)

This records the cash receipt from the borrower at the moment of release, closing
the loan receivable and recognising interest income.  Replaces the legacy write-off
entry (Dr SERVICES_EXPENSE / Cr LOAN_RECEIVABLE) which was semantically wrong for a
normal cash repayment.
"""

from decimal import Decimal

from django.core.exceptions import ValidationError

from ..resolver import get_ledger_id_by_key
from ..registry import register_rule
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("GIVENLOAN_RELEASE")
class GivenLoanReleaseRule(BasePostingRule):
    voucher_type = "GIVENLOAN_RELEASE"
    rule_version = "2"

    def build_posting(self, ctx) -> PostingBundle:
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)
        currency = str(payment.total_amount.currency)

        source_loan = payment.source_loan
        if not source_loan:
            raise ValidationError("Cannot find source GivenLoan for release posting")

        party = getattr(source_loan, "borrower", None) or getattr(source_loan, "customer", None)
        if not party:
            raise ValidationError("GivenLoan has no borrower")

        if not hasattr(party, "account") or not party.account:
            raise ValidationError(
                f"Borrower {party} has no account for release posting"
            )

        # Split principal and interest from the voucher (set by record_loan_release).
        # Fall back to total_amount as principal if components are not set.
        principal_decimal = Decimal(
            str(payment.principal_amount.amount)
            if payment.principal_amount
            else str(payment.total_amount.amount)
        )
        interest_decimal = Decimal(
            str(payment.interest_amount.amount) if payment.interest_amount else "0"
        )
        total_decimal = principal_decimal + interest_decimal

        if total_decimal <= 0:
            raise ValidationError("Release posting amount must be positive")

        # Resolve required ledgers
        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)
        loan_principal_ctrl_id = get_ledger_id_by_key("LOAN_PRINCIPAL_CTRL", tenant_id=tenant_id)
        borrower_loan_ctrl_id = get_ledger_id_by_key("BORROWER_LOAN_CTRL", tenant_id=tenant_id)

        if not cash_id or not loan_principal_ctrl_id or not borrower_loan_ctrl_id:
            raise ValidationError(
                "Required ledgers (CASH, LOAN_PRINCIPAL_CTRL, BORROWER_LOAN_CTRL) not found"
            )

        ledger_lines = []

        # Principal receipt: Dr CASH / Cr LOAN_PRINCIPAL_CTRL
        if principal_decimal > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=cash_id,
                    credit_ledger_id=loan_principal_ctrl_id,
                    currency=currency,
                    amount=principal_decimal,
                    amount_base=principal_decimal,
                )
            )

        # Interest receipt: first clear any posted receivable, then recognise any remainder as fresh income.
        if interest_decimal > 0:
            receivable_balance = Decimal("0")
            receivable_balance_fn = getattr(source_loan, "interest_receivable_balance", None)
            if callable(receivable_balance_fn):
                receivable_balance = Decimal(str(receivable_balance_fn() or 0))

            receivable_portion = min(interest_decimal, receivable_balance)
            income_portion = interest_decimal - receivable_portion

            if receivable_portion > 0:
                interest_receivable_id = get_ledger_id_by_key("INTEREST_RECEIVABLE", tenant_id=tenant_id)
                ledger_lines.append(
                    DualLedgerLine(
                        debit_ledger_id=cash_id,
                        credit_ledger_id=interest_receivable_id,
                        currency=currency,
                        amount=receivable_portion,
                        amount_base=receivable_portion,
                    )
                )

            if income_portion > 0:
                interest_income_id = get_ledger_id_by_key("INTEREST_INCOME", tenant_id=tenant_id)
                if not interest_income_id:
                    raise ValidationError("Required ledger INTEREST_INCOME not found")
                ledger_lines.append(
                    DualLedgerLine(
                        debit_ledger_id=cash_id,
                        credit_ledger_id=interest_income_id,
                        currency=currency,
                        amount=income_portion,
                        amount_base=income_portion,
                    )
                )

        # Subledger AT: close borrower receivable against BORROWER_LOAN_CTRL
        account_lines = []
        if principal_decimal > 0:
            account_lines.append(
                AccountLine(
                    ledger_id=borrower_loan_ctrl_id,
                    account_id=party.account.id,
                    side="Cr",
                    currency=currency,
                    amount=principal_decimal,
                    amount_base=principal_decimal,
                    xact_type_ext="RP",  # Repayment
                )
            )

        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)

    def fingerprint_payload(self, ctx):
        payment = ctx.doc
        source_loan = payment.source_loan
        return {
            "voucher_type": self.voucher_type,
            "rule_version": self.rule_version,
            "source_loan_id": source_loan.id if source_loan else None,
            "payment_id": payment.payment_id,
            "payment_date": payment.payment_date.isoformat() if payment.payment_date else None,
            "total_amount": str(payment.total_amount.amount),
            "principal_amount": str(payment.principal_amount.amount) if payment.principal_amount else None,
            "interest_amount": str(payment.interest_amount.amount) if payment.interest_amount else None,
            "currency": str(payment.total_amount.currency),
        }
