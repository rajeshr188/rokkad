from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from .party_accounts import (
    resolve_given_loan_borrower_account,
    resolve_taken_loan_lender_account,
)
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("LOAN_REPAY")
class LoanRepaymentRule(BasePostingRule):
    """
    Loan repayment posting with two scenarios:

    LOAN_GIVEN repayment (customer pays us back):
            Dr CASH, Cr LOAN_PRINCIPAL_CTRL (principal)
            AT Cr BORROWER_LOAN_CTRL (principal attribution)
      Dr CASH, Cr INTEREST_INCOME (interest, if any)

    LOAN_RECEIVED repayment (we pay back lender):
            Dr BORROWING_PRINCIPAL_CTRL, Cr CASH (principal)
            AT Dr LENDER_ACCOUNT_CTRL (principal attribution)
      Dr INTEREST_EXPENSE, Cr CASH (interest, if any)
    """

    voucher_type = "LOAN_REPAY"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        repayment = ctx.doc
        tenant_id = getattr(ctx, "tenant_id", None)

        # Extract components
        principal_component = Decimal(str(getattr(repayment, "principal_payment", "0")))
        interest_component = Decimal(str(getattr(repayment, "interest_payment", "0")))

        # Get loan type from the related loan (needed first to determine correct party)
        loan = getattr(repayment, "loan", None)
        if not loan:
            raise ValidationError("Repayment must be linked to a loan")

        loan_type = loan.loan_type  # "Taken" or "Given"

        # Resolve the correct party account based on loan type
        if loan_type == "Given":
            account = resolve_given_loan_borrower_account(loan)
        elif loan_type == "Taken":
            account = resolve_taken_loan_lender_account(loan)
        else:
            raise ValidationError(f"Invalid loan_type: {loan_type}. Must be 'Given' or 'Taken'")

        account_id = account.id

        # Validation
        if principal_component < 0 or interest_component < 0:
            raise ValidationError("Payment components cannot be negative")

        total = principal_component + interest_component
        if total <= 0:
            raise ValidationError("Total payment must be positive")

        if loan_type not in ["Taken", "Given"]:
            raise ValidationError(
                f"Invalid loan_type: {loan_type}. Must be 'Taken' or 'Given'"
            )

        # Get ledger configuration
        config = self._get_ledger_config(loan_type, tenant_id)

        # Build dual ledger lines
        ledger_lines = []

        # Principal repayment
        if principal_component > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=config["principal_debit"],
                    credit_ledger_id=config["principal_credit"],
                    currency="INR",
                    amount=principal_component,
                    amount_base=principal_component,
                )
            )

        # Interest payment
        if interest_component > 0:
            ledger_lines.append(
                DualLedgerLine(
                    debit_ledger_id=config["interest_debit"],
                    credit_ledger_id=config["interest_credit"],
                    currency="INR",
                    amount=interest_component,
                    amount_base=interest_component,
                )
            )

        # Account lines (only principal affects the party subledger; interest is GL-only)
        account_lines = []

        if principal_component > 0:
            account_lines.append(
                AccountLine(
                    ledger_id=config["principal_account_ledger"],
                    account_id=account_id,
                    side=config["principal_account_side"],
                    currency="INR",
                    amount=principal_component,
                    amount_base=principal_component,
                    xact_type_ext=config["principal_xact_ext"],
                )
            )

        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)

    def _get_ledger_config(self, loan_type, tenant_id):
        """
        Returns ledger configuration dict based on loan type.

        LT and AT targets are intentionally DIFFERENT ledgers (split-control pattern).
        Interest has LT entries only — no AT (party subledger) for interest.

        GIVEN (we lend money, customer repays):
          LT principal: Dr CASH, Cr LOAN_PRINCIPAL_CTRL
          AT principal: BORROWER_LOAN_CTRL, Cr, "RP"
          LT interest:  Dr CASH, Cr INTEREST_INCOME  (no AT)

        TAKEN (we borrow, we repay lender):
          LT principal: Dr BORROWING_PRINCIPAL_CTRL, Cr CASH
          AT principal: LENDER_ACCOUNT_CTRL, Dr, "LP"
          LT interest:  Dr INTEREST_EXPENSE, Cr CASH  (no AT)
        """
        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)

        if loan_type == "Given":
            loan_principal_ctrl_id = get_ledger_id_by_key(
                "LOAN_PRINCIPAL_CTRL", tenant_id=tenant_id
            )
            borrower_loan_ctrl_id = get_ledger_id_by_key(
                "BORROWER_LOAN_CTRL", tenant_id=tenant_id
            )
            interest_income_id = get_ledger_id_by_key(
                "INTEREST_INCOME", tenant_id=tenant_id
            )

            return {
                # Principal: Dr Cash, Cr LOAN_PRINCIPAL_CTRL
                "principal_debit": cash_id,
                "principal_credit": loan_principal_ctrl_id,
                "principal_account_ledger": borrower_loan_ctrl_id,
                "principal_account_side": "Cr",
                "principal_xact_ext": "RP",  # Repayment Principal
                # Interest: Dr Cash, Cr INTEREST_INCOME (GL only, no AT)
                "interest_debit": cash_id,
                "interest_credit": interest_income_id,
            }

        elif loan_type == "Taken":
            borrowing_principal_ctrl_id = get_ledger_id_by_key(
                "BORROWING_PRINCIPAL_CTRL", tenant_id=tenant_id
            )
            lender_account_ctrl_id = get_ledger_id_by_key(
                "LENDER_ACCOUNT_CTRL", tenant_id=tenant_id
            )
            interest_expense_id = get_ledger_id_by_key(
                "INTEREST_EXPENSE", tenant_id=tenant_id
            )

            return {
                # Principal: Dr BORROWING_PRINCIPAL_CTRL, Cr Cash
                "principal_debit": borrowing_principal_ctrl_id,
                "principal_credit": cash_id,
                "principal_account_ledger": lender_account_ctrl_id,
                "principal_account_side": "Dr",
                "principal_xact_ext": "LP",  # Loan Payment
                # Interest: Dr INTEREST_EXPENSE, Cr Cash (GL only, no AT)
                "interest_debit": interest_expense_id,
                "interest_credit": cash_id,
            }

        else:
            raise ValidationError(f"Unknown loan_type: {loan_type}")

    def fingerprint_payload(self, ctx):
        repayment = ctx.doc
        loan = getattr(repayment, "loan", None)
        customer = getattr(repayment, "customer", None)

        return {
            "voucher_type": self.voucher_type,
            "rule_version": self.rule_version,
            "loan_type": getattr(loan, "loan_type", None) if loan else None,
            "repayment_id": getattr(repayment, "id", None),
            "loan_id": getattr(loan, "id", None) if loan else None,
            "customer_id": getattr(customer, "id", None) if customer else None,
            "principal_payment": str(getattr(repayment, "principal_payment", "0")),
            "interest_payment": str(getattr(repayment, "interest_payment", "0")),
            "payment_date": str(getattr(repayment, "payment_date", None)),
        }
