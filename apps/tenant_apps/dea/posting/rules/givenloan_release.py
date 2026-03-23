"""
GivenLoan Release Posting Rule

Posts a write-off style entry when a GivenLoan is released with outstanding amount.
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
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        payment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)

        source_loan = payment.source_loan
        if not source_loan:
            raise ValidationError("Cannot find source GivenLoan for release posting")

        if not getattr(source_loan, "borrower", None):
            raise ValidationError("GivenLoan has no borrower")

        if not getattr(source_loan.borrower, "account", None):
            raise ValidationError(
                f"Borrower {source_loan.borrower} has no account for release posting"
            )

        amount = Decimal(str(payment.total_amount.amount))
        if amount <= 0:
            raise ValidationError("Release posting amount must be positive")

        def _resolve_with_fallback(primary_key, fallbacks):
            keys = [primary_key] + list(fallbacks)
            for key in keys:
                try:
                    return get_ledger_id_by_key(key, tenant_id=tenant_id)
                except ValidationError:
                    continue
            raise ValidationError(
                f"Required ledger not found. Tried: {', '.join(keys)}"
            )

        # Prefer canonical semantic keys; fall back to seeded CoA labels used in this project.
        loan_receivable_id = _resolve_with_fallback(
            "LOAN_RECEIVABLE",
            ["Loans & Advances", "Loans"],
        )
        writeoff_expense_id = _resolve_with_fallback(
            "SERVICES_EXPENSE",
            ["Interest Paid", "COGS"],
        )

        # Release write-off policy:
        #   Dr SERVICES_EXPENSE, Cr LOAN_RECEIVABLE
        # This records unrecovered principal as an expense and closes receivable.
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=writeoff_expense_id,
                credit_ledger_id=loan_receivable_id,
                currency=str(payment.total_amount.currency),
                amount=amount,
                amount_base=amount,
            )
        ]

        account_lines = [
            AccountLine(
                ledger_id=loan_receivable_id,
                account_id=source_loan.borrower.account.id,
                side="Cr",
                currency=str(payment.total_amount.currency),
                amount=amount,
                amount_base=amount,
                xact_type_ext="LG",
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
            "amount": str(payment.total_amount.amount),
            "currency": str(payment.total_amount.currency),
        }
