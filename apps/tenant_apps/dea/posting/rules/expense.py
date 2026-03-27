"""
Expense Voucher Posting Rules

EXPENSE POSTING PATTERNS:
- EMP_CLAIM: Employee expense reimbursement
  DR: Expense accounts (by category) + GST Input
  CR: TDS Payable + Employee Payable
  
- VENDOR_BILL: Vendor invoice for expenses
  DR: Expense accounts + GST Input
  CR: TDS Payable + Accounts Payable
  
- DIRECT_PAYMENT: Direct expense payment (no payable)
  DR: Expense accounts + GST Input
  CR: TDS Payable + Cash/Bank
"""

from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine
from .base import BasePostingRule
from ..registry import register_rule


@register_rule("EXPENSE_EMP_CLAIM")
class EmployeeExpenseClaimRule(BasePostingRule):
    """
    Post employee expense claims to GL.

    Creates payable to employee that is later settled via PaymentVoucher.

    GL ENTRIES:
    - DR: Expense accounts (by category)
    - DR: GST Input Credit (receivable from tax authority)
    - CR: TDS Payable (non-resident contractor withholding)
    - CR: Employee Payable (accrued expense)
    """

    voucher_type = "EXPENSE_EMP_CLAIM"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        """Build posting for employee expense claim"""
        doc = ctx.doc if hasattr(ctx, "doc") else ctx

        # Validate
        if not hasattr(doc, "line_items"):
            raise ValidationError("Document must have line_items")

        lines = []

        # Add each line item as debit to expense account
        for line in doc.line_items.all():
            # DR: Expense account (by category)
            expense_ledger_key = self._get_expense_ledger_key(line.category)
            lines.append(
                DualLedgerLine(
                    debit_ledger_id=self._resolve_ledger(expense_ledger_key),
                    credit_ledger_id=None,
                    currency=line.amount.currency,
                    amount=line.amount.amount,
                    amount_base=line.amount.amount,
                )
            )

            # DR: GST Input Credit if taxable
            if line.is_taxable and line.tax_amount.amount > 0:
                lines.append(
                    DualLedgerLine(
                        debit_ledger_id=self._resolve_ledger("GST_INPUT_CREDIT"),
                        credit_ledger_id=None,
                        currency=line.tax_amount.currency,
                        amount=line.tax_amount.amount,
                        amount_base=line.tax_amount.amount,
                    )
                )

        # CR: TDS Payable (if applicable)
        if doc.tds_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    debit_ledger_id=None,
                    credit_ledger_id=self._resolve_ledger("TDS_PAYABLE"),
                    currency=doc.tds_amount.currency,
                    amount=doc.tds_amount.amount,
                    amount_base=doc.tds_amount.amount,
                )
            )

        # CR: Employee Payable (net of TDS)
        lines.append(
            DualLedgerLine(
                debit_ledger_id=None,
                credit_ledger_id=self._resolve_ledger("EMPLOYEE_PAYABLE"),
                currency=doc.net_payable.currency,
                amount=doc.net_payable.amount,
                amount_base=doc.net_payable.amount,
            )
        )

        return PostingBundle(
            voucher_type="EXPENSE_EMP_CLAIM",
            voucher_number=doc.expense_number,
            voucher_date=doc.expense_date,
            description=f"Employee expense: {doc.description}",
            lines=lines,
            account_lines=[],
        )

    def _get_expense_ledger_key(self, category: str) -> str:
        """Map expense category to GL account"""
        mapping = {
            "TRAVEL": "TRAVEL_EXPENSE",
            "FOOD": "FOOD_EXPENSE",
            "ACCOMMODATION": "ACCOMMODATION_EXPENSE",
            "PROFESSIONAL": "PROFESSIONAL_SERVICE_EXPENSE",
            "OFFICE": "OFFICE_SUPPLIES_EXPENSE",
            "UTILITIES": "UTILITIES_EXPENSE",
            "MAINTENANCE": "MAINTENANCE_EXPENSE",
            "MARKETING": "MARKETING_EXPENSE",
            "OTHER": "MISCELLANEOUS_EXPENSE",
        }
        return mapping.get(category, "MISCELLANEOUS_EXPENSE")

    def _resolve_ledger(self, ledger_key: str) -> int:
        """Resolve ledger key to ID"""
        # TODO: Implement ledger resolver from your system
        # For now, return placeholder
        from ..resolver import get_ledger_id_by_key

        return get_ledger_id_by_key(ledger_key)


@register_rule("EXPENSE_VENDOR_BILL")
class VendorBillRule(BasePostingRule):
    """
    Post vendor bills for expenses.

    Creates payable to vendor that is later settled via PaymentVoucher.

    GL ENTRIES:
    - DR: Expense accounts (by category)
    - DR: GST Input Credit
    - CR: TDS Payable (if contractor/vendor)
    - CR: Accounts Payable (to vendor)
    """

    voucher_type = "EXPENSE_VENDOR_BILL"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        """Build posting for vendor bill"""
        doc = ctx.doc if hasattr(ctx, "doc") else ctx

        lines = []

        # Add each line item as debit to expense account
        for line in doc.line_items.all():
            # DR: Expense account
            expense_ledger_key = self._get_expense_ledger_key(line.category)
            lines.append(
                DualLedgerLine(
                    debit_ledger_id=self._resolve_ledger(expense_ledger_key),
                    credit_ledger_id=None,
                    currency=line.amount.currency,
                    amount=line.amount.amount,
                    amount_base=line.amount.amount,
                )
            )

            # DR: GST Input Credit if taxable
            if line.is_taxable and line.tax_amount.amount > 0:
                lines.append(
                    DualLedgerLine(
                        debit_ledger_id=self._resolve_ledger("GST_INPUT_CREDIT"),
                        credit_ledger_id=None,
                        currency=line.tax_amount.currency,
                        amount=line.tax_amount.amount,
                        amount_base=line.tax_amount.amount,
                    )
                )

        # CR: TDS Payable (if contractor payment)
        if doc.tds_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    debit_ledger_id=None,
                    credit_ledger_id=self._resolve_ledger("TDS_PAYABLE"),
                    currency=doc.tds_amount.currency,
                    amount=doc.tds_amount.amount,
                    amount_base=doc.tds_amount.amount,
                )
            )

        # CR: Accounts Payable
        lines.append(
            DualLedgerLine(
                debit_ledger_id=None,
                credit_ledger_id=self._resolve_ledger("ACCOUNTS_PAYABLE"),
                currency=doc.net_payable.currency,
                amount=doc.net_payable.amount,
                amount_base=doc.net_payable.amount,
            )
        )

        return PostingBundle(
            voucher_type="EXPENSE_VENDOR_BILL",
            voucher_number=doc.expense_number,
            voucher_date=doc.expense_date,
            description=f"Vendor bill: {doc.description}",
            lines=lines,
            account_lines=[],
        )

    def _get_expense_ledger_key(self, category: str) -> str:
        """Map expense category to GL account"""
        mapping = {
            "TRAVEL": "TRAVEL_EXPENSE",
            "FOOD": "FOOD_EXPENSE",
            "ACCOMMODATION": "ACCOMMODATION_EXPENSE",
            "PROFESSIONAL": "PROFESSIONAL_SERVICE_EXPENSE",
            "OFFICE": "OFFICE_SUPPLIES_EXPENSE",
            "UTILITIES": "UTILITIES_EXPENSE",
            "MAINTENANCE": "MAINTENANCE_EXPENSE",
            "MARKETING": "MARKETING_EXPENSE",
            "OTHER": "MISCELLANEOUS_EXPENSE",
        }
        return mapping.get(category, "MISCELLANEOUS_EXPENSE")

    def _resolve_ledger(self, ledger_key: str) -> int:
        """Resolve ledger key to ID"""
        from ..resolver import get_ledger_id_by_key

        return get_ledger_id_by_key(ledger_key)


@register_rule("EXPENSE_DIRECT_PAYMENT")
class DirectExpensePaymentRule(BasePostingRule):
    """
    Post direct expense payments (no payable created).

    Used when expense is paid immediately from cash/bank.

    GL ENTRIES:
    - DR: Expense accounts (by category)
    - DR: GST Input Credit
    - CR: TDS Payable (if applicable)
    - CR: Cash/Bank (paid directly)
    """

    voucher_type = "EXPENSE_DIRECT_PAYMENT"
    rule_version = "1"

    def build_posting(self, ctx) -> PostingBundle:
        """Build posting for direct expense payment"""
        doc = ctx.doc if hasattr(ctx, "doc") else ctx

        lines = []

        # Add each line item as debit to expense account
        for line in doc.line_items.all():
            # DR: Expense account
            expense_ledger_key = self._get_expense_ledger_key(line.category)
            # Both debit and credit ledger IDs must be set; use a suspense/clearing account for credit
            lines.append(
                DualLedgerLine(
                    debit_ledger_id=self._resolve_ledger(expense_ledger_key),
                    credit_ledger_id=self._resolve_ledger("EXPENSE_SUSPENSE"),
                    currency=str(line.amount.currency),
                    amount=line.amount.amount,
                    amount_base=line.amount.amount,
                )
            )

            # DR: GST Input Credit if taxable
            if line.is_taxable and line.tax_amount.amount > 0:
                lines.append(
                    DualLedgerLine(
                        debit_ledger_id=self._resolve_ledger("GST_INPUT_CREDIT"),
                        credit_ledger_id=self._resolve_ledger("EXPENSE_SUSPENSE"),
                        currency=str(line.tax_amount.currency),
                        amount=line.tax_amount.amount,
                        amount_base=line.tax_amount.amount,
                    )
                )

        # CR: TDS Payable (deferred if contractor)
        if hasattr(doc.tds_amount, 'amount') and doc.tds_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    debit_ledger_id=self._resolve_ledger("EXPENSE_SUSPENSE"),
                    credit_ledger_id=self._resolve_ledger("TDS_PAYABLE"),
                    currency=str(doc.tds_amount.currency),
                    amount=doc.tds_amount.amount,
                    amount_base=doc.tds_amount.amount,
                )
            )

        # CR: Cash/Bank (direct payment)
        lines.append(
            DualLedgerLine(
                debit_ledger_id=self._resolve_ledger("EXPENSE_SUSPENSE"),
                credit_ledger_id=self._resolve_ledger("Cash"),
                currency=str(doc.net_payable.currency),
                amount=doc.net_payable.amount,
                amount_base=doc.net_payable.amount,
            )
        )

        return PostingBundle(
            # voucher_type="EXPENSE_DIRECT_PAYMENT",
            # voucher_number=doc.expense_number,
            # voucher_date=doc.expense_date,
            # description=f"Direct expense payment: {doc.description}",
            ledger_lines=lines,
            account_lines=[],
        )

    def _get_expense_ledger_key(self, category: str) -> str:
        """Map expense category to GL account"""
        mapping = {
            "TRAVEL & TRANSPORTATION": "TRAVEL_EXPENSE",
            "FOOD": "FOOD_EXPENSE",
            "ACCOMMODATION": "ACCOMMODATION_EXPENSE",
            "PROFESSIONAL": "PROFESSIONAL_SERVICE_EXPENSE",
            "OFFICE": "OFFICE_SUPPLIES_EXPENSE",
            "UTILITIES": "UTILITIES_EXPENSE",
            "MAINTENANCE": "MAINTENANCE_EXPENSE",
            "MARKETING": "MARKETING_EXPENSE",
            "Other Expense": "MISCELLANEOUS_EXPENSE",
        }
        return mapping.get(category, "Other Expense")

    def _resolve_ledger(self, ledger_key: str) -> int:
        """Resolve ledger key to ID"""
        from ..resolver import get_ledger_id_by_key

        return get_ledger_id_by_key(ledger_key)
