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

        LOAN_GIVEN:
            LT Dr LOAN_PRINCIPAL_CTRL, Cr CASH
            AT Dr BORROWER_LOAN_CTRL

        LOAN_RECEIVED:
            LT Dr CASH, Cr BORROWING_PRINCIPAL_CTRL
            AT Cr LENDER_ACCOUNT_CTRL
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
        # Returns (debit_ledger_id, credit_ledger_id, at_ledger_id, account_side, xact_ext)
        (
            debit_ledger_id,
            credit_ledger_id,
            at_ledger_id,
            account_side,
            xact_ext,
        ) = self._get_ledger_config(loan_type, tenant_id)

        # Build posting - dual-leg ledger entry (LT: internal fund flow control)
        ledger_lines = [
            DualLedgerLine(
                debit_ledger_id=debit_ledger_id,
                credit_ledger_id=credit_ledger_id,
                currency="INR",
                amount=principal_amount,
                amount_base=principal_amount,
            )
        ]

        # Account line uses the party attribution control ledger (AT target, distinct from LT)
        account_lines = [
            AccountLine(
                ledger_id=at_ledger_id,
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
        Returns (debit_ledger_id, credit_ledger_id, at_ledger_id, account_side, xact_ext).

        LT target and AT target are intentionally DIFFERENT ledgers to prevent balance
        double-counting under the DEA split-control pattern:

        - "Given" (we lend out):
            LT: Dr LOAN_PRINCIPAL_CTRL, Cr CASH  (internal fund flow)
            AT: BORROWER_LOAN_CTRL, Dr           (party attribution)
        - "Taken" (we borrow):
            LT: Dr CASH, Cr BORROWING_PRINCIPAL_CTRL  (internal fund flow)
            AT: LENDER_ACCOUNT_CTRL, Cr               (party attribution)
        """
        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)

        if loan_type == "Given":
            lt_ledger_id = get_ledger_id_by_key("LOAN_PRINCIPAL_CTRL", tenant_id=tenant_id)
            at_ledger_id = get_ledger_id_by_key("BORROWER_LOAN_CTRL", tenant_id=tenant_id)
            return (lt_ledger_id, cash_id, at_ledger_id, "Dr", "LG")

        elif loan_type == "Taken":
            lt_ledger_id = get_ledger_id_by_key("BORROWING_PRINCIPAL_CTRL", tenant_id=tenant_id)
            at_ledger_id = get_ledger_id_by_key("LENDER_ACCOUNT_CTRL", tenant_id=tenant_id)
            return (cash_id, lt_ledger_id, at_ledger_id, "Cr", "LR")

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
