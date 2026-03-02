"""
Purchase Invoice Posting Rules

Posts purchase of goods (inventory) or services (expense) with GST input credit.
"""

from decimal import Decimal
from django.core.exceptions import ValidationError
from ..types import PostingBundle, DualLedgerLine, AccountLine
from .base import BasePostingRule
from ..resolver import get_ledger_id_by_key
from ..registry import register_rule


@register_rule("PURCHASE_GOODS")
class PurchaseGoodsRule(BasePostingRule):
    """
    Posting rule for purchase of goods (inventory).

    ACCOUNTING ENTRIES:
    DR: Inventory/Stock
    DR: GST Input Credit
    CR: Accounts Payable (Vendor)
    CR: TDS Payable (if withheld)

    Example:
    Purchased goods for ₹100,000 + GST ₹18,000 - TDS ₹1,000
    DR: Inventory ₹100,000
    DR: GST Input ₹18,000
    CR: TDS Payable ₹1,000
    CR: AP ₹117,000
    """

    def should_run(self, doc) -> bool:
        """Only run for goods purchases"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        return isinstance(doc, PurchaseInvoiceVoucher) and doc.purchase_type == "GOODS"

    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for purchase of goods"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        if not isinstance(doc, PurchaseInvoiceVoucher):
            raise ValidationError("Document must be PurchaseInvoiceVoucher")

        # Get ledger IDs
        inventory_ledger = get_ledger_id_by_key("INVENTORY")
        gst_input_ledger = get_ledger_id_by_key("GST_INPUT_CREDIT")
        ap_ledger = get_ledger_id_by_key("ACCOUNTS_PAYABLE")
        tds_payable_ledger = get_ledger_id_by_key("TDS_PAYABLE")

        lines = []

        # DR: Inventory (taxable amount)
        lines.append(
            DualLedgerLine(
                ledger_dr=inventory_ledger,
                ledger_cr=None,
                amount=doc.taxable_amount.amount,
                memo=f"Purchase from {doc.vendor} - {doc.internal_number}",
            )
        )

        # DR: GST Input Credit (total GST)
        total_gst = (
            doc.cgst_amount.amount + doc.sgst_amount.amount + doc.igst_amount.amount
        )
        if total_gst > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=gst_input_ledger,
                    ledger_cr=None,
                    amount=total_gst,
                    memo=f"GST Input Credit - {doc.internal_number}",
                )
            )

        # CR: TDS Payable (if withheld)
        if doc.tds_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=None,
                    ledger_cr=tds_payable_ledger,
                    amount=doc.tds_amount.amount,
                    memo=f"TDS withheld - {doc.internal_number}",
                )
            )

        # CR: Accounts Payable (net payable to vendor)
        lines.append(
            DualLedgerLine(
                ledger_dr=None,
                ledger_cr=ap_ledger,
                amount=doc.net_payable.amount,
                memo=f"Payable to {doc.vendor} - {doc.internal_number}",
            )
        )

        # Subledger: Vendor account
        account_lines = [
            AccountLine(
                account_dr=None,
                account_cr=doc.vendor.id,
                amount=doc.net_payable.amount,
                memo=f"Purchase {doc.internal_number}",
            )
        ]

        return PostingBundle(
            voucher_type="PURCHASE_GOODS",
            voucher_number=doc.internal_number,
            voucher_date=doc.invoice_date,
            description=f"Purchase from {doc.vendor}",
            lines=lines,
            account_lines=account_lines,
        )


@register_rule("PURCHASE_SERVICES")
class PurchaseServicesRule(BasePostingRule):
    """
    Posting rule for purchase of services (expense).

    ACCOUNTING ENTRIES:
    DR: Expense Account
    DR: GST Input Credit
    CR: Accounts Payable (Vendor)
    CR: TDS Payable (if withheld)

    Example:
    Consulting services ₹50,000 + GST ₹9,000 - TDS ₹5,000
    DR: Professional Services Expense ₹50,000
    DR: GST Input ₹9,000
    CR: TDS Payable ₹5,000
    CR: AP ₹54,000
    """

    def should_run(self, doc) -> bool:
        """Only run for services purchases"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        return (
            isinstance(doc, PurchaseInvoiceVoucher) and doc.purchase_type == "SERVICES"
        )

    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for purchase of services"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        if not isinstance(doc, PurchaseInvoiceVoucher):
            raise ValidationError("Document must be PurchaseInvoiceVoucher")

        # Get ledger IDs
        services_expense_ledger = get_ledger_id_by_key("SERVICES_EXPENSE")
        gst_input_ledger = get_ledger_id_by_key("GST_INPUT_CREDIT")
        ap_ledger = get_ledger_id_by_key("ACCOUNTS_PAYABLE")
        tds_payable_ledger = get_ledger_id_by_key("TDS_PAYABLE")

        lines = []

        # DR: Services Expense (taxable amount)
        lines.append(
            DualLedgerLine(
                ledger_dr=services_expense_ledger,
                ledger_cr=None,
                amount=doc.taxable_amount.amount,
                memo=f"Services from {doc.vendor} - {doc.internal_number}",
            )
        )

        # DR: GST Input Credit (total GST)
        total_gst = (
            doc.cgst_amount.amount + doc.sgst_amount.amount + doc.igst_amount.amount
        )
        if total_gst > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=gst_input_ledger,
                    ledger_cr=None,
                    amount=total_gst,
                    memo=f"GST Input Credit - {doc.internal_number}",
                )
            )

        # CR: TDS Payable (if withheld)
        if doc.tds_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=None,
                    ledger_cr=tds_payable_ledger,
                    amount=doc.tds_amount.amount,
                    memo=f"TDS withheld - {doc.internal_number}",
                )
            )

        # CR: Accounts Payable (net payable to vendor)
        lines.append(
            DualLedgerLine(
                ledger_dr=None,
                ledger_cr=ap_ledger,
                amount=doc.net_payable.amount,
                memo=f"Payable to {doc.vendor} - {doc.internal_number}",
            )
        )

        # Subledger: Vendor account
        account_lines = [
            AccountLine(
                account_dr=None,
                account_cr=doc.vendor.id,
                amount=doc.net_payable.amount,
                memo=f"Services {doc.internal_number}",
            )
        ]

        return PostingBundle(
            voucher_type="PURCHASE_SERVICES",
            voucher_number=doc.internal_number,
            voucher_date=doc.invoice_date,
            description=f"Services from {doc.vendor}",
            lines=lines,
            account_lines=account_lines,
        )


@register_rule("PURCHASE_ASSETS")
class PurchaseAssetsRule(BasePostingRule):
    """
    Posting rule for purchase of fixed assets.

    ACCOUNTING ENTRIES:
    DR: Fixed Assets
    DR: GST Input Credit
    CR: Accounts Payable (Vendor)
    CR: TDS Payable (if withheld)

    Example:
    Computer equipment ₹200,000 + GST ₹36,000
    DR: Computer Equipment ₹200,000
    DR: GST Input ₹36,000
    CR: AP ₹236,000
    """

    def should_run(self, doc) -> bool:
        """Only run for asset purchases"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        return isinstance(doc, PurchaseInvoiceVoucher) and doc.purchase_type == "ASSETS"

    def build_posting(self, doc, context=None) -> PostingBundle:
        """Build posting for purchase of assets"""
        from apps.tenant_apps.dea.models import PurchaseInvoiceVoucher

        if not isinstance(doc, PurchaseInvoiceVoucher):
            raise ValidationError("Document must be PurchaseInvoiceVoucher")

        # Get ledger IDs
        fixed_assets_ledger = get_ledger_id_by_key("FIXED_ASSETS")
        gst_input_ledger = get_ledger_id_by_key("GST_INPUT_CREDIT")
        ap_ledger = get_ledger_id_by_key("ACCOUNTS_PAYABLE")
        tds_payable_ledger = get_ledger_id_by_key("TDS_PAYABLE")

        lines = []

        # DR: Fixed Assets (taxable amount)
        lines.append(
            DualLedgerLine(
                ledger_dr=fixed_assets_ledger,
                ledger_cr=None,
                amount=doc.taxable_amount.amount,
                memo=f"Asset purchase from {doc.vendor} - {doc.internal_number}",
            )
        )

        # DR: GST Input Credit (total GST)
        total_gst = (
            doc.cgst_amount.amount + doc.sgst_amount.amount + doc.igst_amount.amount
        )
        if total_gst > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=gst_input_ledger,
                    ledger_cr=None,
                    amount=total_gst,
                    memo=f"GST Input Credit - {doc.internal_number}",
                )
            )

        # CR: TDS Payable (if withheld)
        if doc.tds_amount.amount > 0:
            lines.append(
                DualLedgerLine(
                    ledger_dr=None,
                    ledger_cr=tds_payable_ledger,
                    amount=doc.tds_amount.amount,
                    memo=f"TDS withheld - {doc.internal_number}",
                )
            )

        # CR: Accounts Payable (net payable to vendor)
        lines.append(
            DualLedgerLine(
                ledger_dr=None,
                ledger_cr=ap_ledger,
                amount=doc.net_payable.amount,
                memo=f"Payable to {doc.vendor} - {doc.internal_number}",
            )
        )

        # Subledger: Vendor account
        account_lines = [
            AccountLine(
                account_dr=None,
                account_cr=doc.vendor.id,
                amount=doc.net_payable.amount,
                memo=f"Asset purchase {doc.internal_number}",
            )
        ]

        return PostingBundle(
            voucher_type="PURCHASE_ASSETS",
            voucher_number=doc.internal_number,
            voucher_date=doc.invoice_date,
            description=f"Asset purchase from {doc.vendor}",
            lines=lines,
            account_lines=account_lines,
        )
