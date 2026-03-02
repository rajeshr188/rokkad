from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key


class LoanRepaymentRule(BasePostingRule):
    """
    Loan repayment posting with two scenarios:

    LOAN_GIVEN repayment (customer pays us back):
      Dr CASH, Cr LOAN_RECEIVABLE (principal)
      Dr CASH, Cr INTEREST_INCOME (interest, if any)

    LOAN_RECEIVED repayment (we pay back lender):
      Dr LOAN_PAYABLE, Cr CASH (principal)
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

        # Get the customer and their account
        customer = getattr(repayment, "customer", None)
        if not customer:
            # Try to get from related loan
            loan = getattr(repayment, "loan", None)
            if loan:
                customer = loan.customer

        if not customer or not getattr(customer, "account", None):
            raise ValidationError(f"No account found for customer {customer}")

        account_id = customer.account.id

        # Get loan type from the related loan
        loan = getattr(repayment, "loan", None)
        if not loan:
            raise ValidationError("Repayment must be linked to a loan")

        loan_type = loan.loan_type  # "Taken" or "Given"

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

        # Account lines (both principal and interest affect account balance)
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

        if interest_component > 0:
            account_lines.append(
                AccountLine(
                    ledger_id=config["interest_account_ledger"],
                    account_id=account_id,
                    side=config["interest_account_side"],
                    currency="INR",
                    amount=interest_component,
                    amount_base=interest_component,
                    xact_type_ext=config["interest_xact_ext"],
                )
            )

        return PostingBundle(ledger_lines=ledger_lines, account_lines=account_lines)

    def _get_ledger_config(self, loan_type, tenant_id):
        """
        Returns ledger configuration dict based on loan type.

        GIVEN (we lend money):
          Customer repays: Dr Cash, Cr Loan Receivable (principal)
                          Dr Cash, Cr Interest Income (interest)

        TAKEN (we borrow money):
          We repay: Dr Loan Payable, Cr Cash (principal)
                   Dr Interest Expense, Cr Cash (interest)
        """
        cash_id = get_ledger_id_by_key("CASH", tenant_id=tenant_id)

        if loan_type == "Given":
            # Customer repays us
            receivable_id = get_ledger_id_by_key("LOAN_RECEIVABLE", tenant_id=tenant_id)
            interest_income_id = get_ledger_id_by_key(
                "INTEREST_INCOME", tenant_id=tenant_id
            )

            return {
                # Principal: Dr Cash, Cr Loan Receivable
                "principal_debit": cash_id,
                "principal_credit": receivable_id,
                "principal_account_ledger": receivable_id,
                "principal_account_side": "Cr",  # Reduces what customer owes us
                "principal_xact_ext": "RP",  # Repayment Received (Principal)
                # Interest: Dr Cash, Cr Interest Income
                "interest_debit": cash_id,
                "interest_credit": interest_income_id,
                "interest_account_ledger": interest_income_id,
                "interest_account_side": "Cr",  # Records interest received
                "interest_xact_ext": "RI",  # Interest Received
            }

        elif loan_type == "Taken":
            # We repay lender
            payable_id = get_ledger_id_by_key("LOAN_PAYABLE", tenant_id=tenant_id)
            interest_expense_id = get_ledger_id_by_key(
                "INTEREST_EXPENSE", tenant_id=tenant_id
            )

            return {
                # Principal: Dr Loan Payable, Cr Cash
                "principal_debit": payable_id,
                "principal_credit": cash_id,
                "principal_account_ledger": payable_id,
                "principal_account_side": "Dr",  # Reduces what we owe lender
                "principal_xact_ext": "LP",  # Loan Payment (Principal)
                # Interest: Dr Interest Expense, Cr Cash
                "interest_debit": interest_expense_id,
                "interest_credit": cash_id,
                "interest_account_ledger": interest_expense_id,
                "interest_account_side": "Dr",  # Records interest paid
                "interest_xact_ext": "IP",  # Interest Paid
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
