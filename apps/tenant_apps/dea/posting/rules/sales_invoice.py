"""
Sales Invoice Posting Rule

Posts sales revenue and GST output tax liability.
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("SALES_INVOICE")
class SalesInvoiceRule(BasePostingRule):
    """
    Posting rule for sales invoices.

    ACCOUNTING ENTRIES:
    DR: Accounts Receivable (Customer)
    CR: Sales Revenue
    CR: CGST Output
    CR: SGST Output
    CR: IGST Output
    CR: TCS Payable

    Example:
    Sold goods for ₹100,000 + GST ₹18,000
    DR: AR ₹118,000
    CR: Sales Revenue ₹100,000
    CR: GST Output ₹18,000
    """

    def should_run(self, doc) -> bool:
        """Only run for sales invoices"""
        from apps.tenant_apps.dea.models import SalesInvoiceVoucher

        return isinstance(doc, SalesInvoiceVoucher)

    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for sales invoice"""
        from apps.tenant_apps.dea.models import SalesInvoiceVoucher

        if not isinstance(doc, SalesInvoiceVoucher):
            raise ValidationError("Document must be SalesInvoiceVoucher")

        # Get  account IDs
        ar_ledger = get_ledger_id_by_key("ACCOUNTS_RECEIVABLE")
        sales_ledger = get_ledger_id_by_key("SALES_REVENUE")
        cgst_output_ledger = get_ledger_id_by_key("CGST_OUTPUT")
        sgst_output_ledger = get_ledger_id_by_key("SGST_OUTPUT")
        igst_output_ledger = get_ledger_id_by_key("IGST_OUTPUT")
        tcs_payable_ledger = get_ledger_id_by_key("TCS_PAYABLE")

        lines = []

        # DR: Accounts Receivable (total invoice amount)
        lines.append(
            DualLedgerLine(
                ledger_dr=ar_ledger,
                ledger_cr=None,
                amount=doc.total_amount.amount,
                memo=f"Sale to {doc.customer} - Invoice {doc.invoice_number}",
            )
        )

        # CR: Sales Revenue (taxable amount)
        lines.append(
            DualLedgerLine(
                ledger_dr=None,
                ledger_cr=sales_ledger,
                amount=doc.taxable_amount.amount,
                memo=f"Sales revenue - Invoice {doc.invoice_number}",
            )
        )

        # CR: CGST Output
        if doc.cgst_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=None,
                    ledger_cr=cgst_output_ledger,
                    amount=doc.cgst_amount.amount,
                    memo=f"CGST collected - Invoice {doc.invoice_number}",
                )
            )

        # CR: SGST Output
        if doc.sgst_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=None,
                    ledger_cr=sgst_output_ledger,
                    amount=doc.sgst_amount.amount,
                    memo=f"SGST collected - Invoice {doc.invoice_number}",
                )
            )

        # CR: IGST Output
        if doc.igst_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=None,
                    ledger_cr=igst_output_ledger,
                    amount=doc.igst_amount.amount,
                    memo=f"IGST collected - Invoice {doc.invoice_number}",
                )
            )

        # CR: TCS Payable
        if doc.tcs_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=None,
                    ledger_cr=tcs_payable_ledger,
                    amount=doc.tcs_amount.amount,
                    memo=f"TCS collected - Invoice {doc.invoice_number}",
                )
            )

        # Subledger: Customer account
        account_lines = [
            AccountLine(
                account_dr=doc.customer.id,
                account_cr=None,
                amount=doc.total_amount.amount,
                memo=f"Invoice {doc.invoice_number}",
            )
        ]

        return PostingBundle(
            voucher_type="SALES_INVOICE",
            voucher_number=doc.invoice_number,
            voucher_date=doc.invoice_date,
            description=f"Sales to {doc.customer}",
            lines=lines,
            account_lines=account_lines,
        )
