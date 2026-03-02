from atexit import register
from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


# filepath: posting/rules/loan_disbursement.py
@register_rule("LOAN_DISBURSE")
class LoanDisbursementRule(BasePostingRule):
    """
    Loan disbursement posting with two scenarios:

    LOAN_GIVEN: Dr LOAN_RECEIVABLE, Cr CASH (we lend money)
    LOAN_RECEIVED: Dr CASH, Cr LOAN_PAYABLE (we borrow money)
    """

    voucher_type = "LOAN_DISBURSE"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        disbursement = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)

        # Extract economic data
        principal_amount = Decimal(str(getattr(disbursement, "loan_amount", "0")))
        interest_amount = Decimal(str(getattr(disbursement, "interest", "0")))
        loan_type = getattr(disbursement, "loan_type", None)

        # Validation
        if principal_amount <= 0:
            raise ValidationError("Principal amount must be positive")

        # Normalize loan_type: capitalize first letter for consistency with model choices
        if loan_type:
            loan_type = loan_type.capitalize()

        if loan_type not in ["Given", "Taken"]:
            raise ValidationError("loan_type must be either 'Given' or 'Taken'")

        if not getattr(disbursement, "customer", None) or not getattr(
            disbursement.customer, "account", None
        ):
            raise ValidationError(
                f"No account found for {getattr(disbursement, 'customer', None)}"
            )

        # Resolve ledgers based on loan type
        (
            debit_ledger_id,
            credit_ledger_id,
            account_side,
            xact_ext,
        ) = self._get_ledger_config(loan_type, tenant_id)

        # Build posting - dual-leg ledger entry
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=debit_ledger_id,
                credit_ledger_id=credit_ledger_id,
                amount=principal_amount,
                amount_base=principal_amount,
            )
        ]

        # Account line uses the receivable/payable ledger
        account_ledger_id = (
            debit_ledger_id if loan_type == "Given" else credit_ledger_id
        )
        account_lines = [
            AccountLine(
                ledger_id=account_ledger_id,
                account_id=disbursement.customer.account.id,
                side=account_side,
                currency="INR",
                amount=principal_amount,
                amount_base=principal_amount,
                xact_type_ext=xact_ext,
            )
        ]

        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)

    def _get_ledger_config(self, loan_type, tenant_id):
        """
        Returns (debit_ledger_id, credit_ledger_id, account_side, xact_ext) based on loan type.

        loan_type can be:
        - "Given" (we lend out): Dr Loan Receivable, Cr Cash
        - "Taken" (we borrow): Dr Cash, Cr Loan Payable
        """
        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)

        if loan_type == "Given":
            # We lend: Dr Loan Receivable, Cr Cash
            receivable_id = get_ledger_id_by_key("LOAN_RECEIVABLE", tenant_id=tenant_id)
            return (
                receivable_id,
                cash_id,
                "Dr",
                "LG",
            )  # Customer owes us (Dr in receivable)

        elif loan_type == "Taken":
            # We borrow: Dr Cash, Cr Loan Payable
            payable_id = get_ledger_id_by_key("LOAN_PAYABLE", tenant_id=tenant_id)
            return cash_id, payable_id, "Cr", "LR"  # We owe lender (Cr in payable)

        else:
            raise ValidationError(
                f"Unknown loan_type: {loan_type}. Must be 'Given' or 'Taken'."
            )

    def fingerprint_payload(self, ctx):
        """
        Return the economic payload used for fingerprinting idempotency.
        Uses the doc's get_economic_payload() method if available.
        """
        disbursement = ctx.doc

        # Try to use the doc's built-in method if available
        if hasattr(disbursement, "get_economic_payload"):
            return disbursement.get_economic_payload()

        # Fallback: manually construct payload
        return {
            "customer_id": getattr(getattr(disbursement, "customer", None), "id", None),
            "loan_amount": getattr(disbursement, "loan_amount", None),
            "interest": str(getattr(disbursement, "interest", 0)),
            "loan_type": getattr(disbursement, "loan_type", None),
        }


# or register the rule directly without decorator
# # Module-level registration (runs when imported)
# registry.register(LoanDisbursementRule.voucher_type, LoanDisbursementRule)
