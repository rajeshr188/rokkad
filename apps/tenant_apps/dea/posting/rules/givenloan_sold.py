"""
GivenLoan Collateral Sale Recovery Posting Rule

When collateral is sold and cash is recovered:
- Dr CASH
- Cr LOAN_PRINCIPAL_CTRL
- AT: Cr BORROWER_LOAN_CTRL (reduces borrower outstanding)
"""

from decimal import Decimal

from django.core.exceptions import ValidationError

from ..resolver import get_ledger_id_by_key
from ..registry import register_rule
from ..types import AccountLine, DualLedgerLine, PostingBundle
from .base import BasePostingRule


@register_rule("GIVENLOAN_SOLD")
class GivenLoanSoldRule(BasePostingRule):
    voucher_type = "GIVENLOAN_SOLD"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)
        currency = str(payment.total_amount.currency)

        source_loan = payment.source_loan
        if not source_loan:
            raise ValidationError("Cannot find source GivenLoan for sale posting")

        party = getattr(source_loan, "borrower", None) or getattr(source_loan, "customer", None)
        if not party:
            raise ValidationError("GivenLoan has no borrower/customer")

        if not hasattr(party, "account") or not party.account:
            raise ValidationError(f"Borrower/customer {party} has no account")

        amount_decimal = Decimal(str(payment.total_amount.amount))
        if amount_decimal <= 0:
            raise ValidationError("Sale recovery amount must be positive")

        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)
        loan_principal_ctrl_id = get_ledger_id_by_key(
            "LOAN_PRINCIPAL_CTRL", tenant_id=tenant_id
        )
        borrower_loan_ctrl_id = get_ledger_id_by_key(
            "BORROWER_LOAN_CTRL", tenant_id=tenant_id
        )

        if not cash_id or not loan_principal_ctrl_id or not borrower_loan_ctrl_id:
            raise ValidationError(
                "Required ledgers (CASH, LOAN_PRINCIPAL_CTRL, BORROWER_LOAN_CTRL) not found"
            )

        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=cash_id,
                credit_ledger_id=loan_principal_ctrl_id,
                currency=currency,
                amount=amount_decimal,
                amount_base=amount_decimal,
            )
        ]

        account_lines = [
            AccountLine(
                ledger_id=borrower_loan_ctrl_id,
                account_id=party.account.id,
                side="Cr",
                currency=currency,
                amount=amount_decimal,
                amount_base=amount_decimal,
                xact_type_ext="RP",
            )
        ]

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
            "currency": str(payment.total_amount.currency),
        }
