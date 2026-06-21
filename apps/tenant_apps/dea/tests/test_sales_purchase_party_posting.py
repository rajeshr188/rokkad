from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase
from moneyed import Money

from apps.tenant_apps.dea.posting.rules.party_accounts import (
    resolve_customer_advance_account,
    resolve_purchase_supplier_account,
    resolve_sales_customer_account,
    resolve_supplier_advance_account,
)
from apps.tenant_apps.dea.posting.rules.purchase_invoice import PurchaseGoodsRule
from apps.tenant_apps.dea.posting.rules.sales_invoice import SalesInvoiceRule


class SalesPurchasePartyResolverTests(SimpleTestCase):
    @patch("apps.tenant_apps.dea.posting.rules.party_accounts.resolve_customer_account")
    def test_sales_customer_uses_customer_receivable_purpose(self, mock_resolve):
        customer = SimpleNamespace(id=1)
        doc = SimpleNamespace(customer=customer)
        mock_resolve.return_value = SimpleNamespace(id=91)

        account = resolve_sales_customer_account(doc)

        self.assertEqual(account.id, 91)
        mock_resolve.assert_called_once_with(
            customer,
            role_key="CUSTOMER",
            purpose="CUSTOMER_RECEIVABLE",
        )

    @patch("apps.tenant_apps.dea.posting.rules.party_accounts.resolve_customer_account")
    def test_purchase_supplier_uses_supplier_payable_purpose(self, mock_resolve):
        supplier = SimpleNamespace(id=2)
        doc = SimpleNamespace(vendor=supplier)
        mock_resolve.return_value = SimpleNamespace(id=92)

        account = resolve_purchase_supplier_account(doc)

        self.assertEqual(account.id, 92)
        mock_resolve.assert_called_once_with(
            supplier,
            role_key="SUPPLIER",
            purpose="SUPPLIER_PAYABLE",
        )

    @patch("apps.tenant_apps.dea.posting.rules.party_accounts.resolve_customer_account")
    def test_customer_advance_uses_customer_advance_purpose(self, mock_resolve):
        customer = SimpleNamespace(id=3)
        doc = SimpleNamespace(customer=customer)
        mock_resolve.return_value = SimpleNamespace(id=93)

        account = resolve_customer_advance_account(doc)

        self.assertEqual(account.id, 93)
        mock_resolve.assert_called_once_with(
            customer,
            role_key="CUSTOMER",
            purpose="CUSTOMER_ADVANCE",
        )

    @patch("apps.tenant_apps.dea.posting.rules.party_accounts.resolve_customer_account")
    def test_supplier_advance_uses_supplier_advance_purpose(self, mock_resolve):
        supplier = SimpleNamespace(id=4)
        doc = SimpleNamespace(supplier=supplier)
        mock_resolve.return_value = SimpleNamespace(id=94)

        account = resolve_supplier_advance_account(doc)

        self.assertEqual(account.id, 94)
        mock_resolve.assert_called_once_with(
            supplier,
            role_key="SUPPLIER",
            purpose="SUPPLIER_ADVANCE",
        )


class SalesPurchasePostingRuleTests(SimpleTestCase):
    @patch(
        "apps.tenant_apps.dea.posting.rules.sales_invoice.resolve_sales_customer_account",
        return_value=SimpleNamespace(id=501),
    )
    @patch("apps.tenant_apps.dea.posting.rules.sales_invoice.get_ledger_id_by_key")
    def test_sales_invoice_account_line_uses_resolved_customer_account(
        self,
        mock_ledger,
        mock_resolve_account,
    ):
        mock_ledger.side_effect = lambda key, tenant_id=None: {
            "ACCOUNTS_RECEIVABLE": 10,
            "SALES_REVENUE": 20,
            "CGST_OUTPUT": 30,
            "SGST_OUTPUT": 31,
            "IGST_OUTPUT": 32,
            "TCS_PAYABLE": 33,
        }[key]
        doc = SimpleNamespace(
            id=1,
            invoice_number="INV-1",
            customer_id=7,
            customer=SimpleNamespace(id=7),
            total_amount=Money(118, "INR"),
            taxable_amount=Money(100, "INR"),
            cgst_amount=Money(9, "INR"),
            sgst_amount=Money(9, "INR"),
            igst_amount=Money(0, "INR"),
            tcs_amount=Money(0, "INR"),
        )

        bundle = SalesInvoiceRule().build_posting(SimpleNamespace(doc=doc))

        self.assertEqual(len(bundle.ledger_lines), 3)
        self.assertEqual(len(bundle.account_lines), 1)
        self.assertEqual(bundle.account_lines[0].account_id, 501)
        self.assertEqual(bundle.account_lines[0].ledger_id, 10)
        self.assertEqual(bundle.account_lines[0].side, "Dr")
        self.assertEqual(bundle.account_lines[0].amount, Decimal("118"))
        mock_resolve_account.assert_called_once_with(doc)

    @patch(
        "apps.tenant_apps.dea.posting.rules.purchase_invoice.resolve_purchase_supplier_account",
        return_value=SimpleNamespace(id=601),
    )
    @patch("apps.tenant_apps.dea.posting.rules.purchase_invoice.get_ledger_id_by_key")
    def test_purchase_invoice_account_line_uses_resolved_supplier_account(
        self,
        mock_ledger,
        mock_resolve_account,
    ):
        mock_ledger.side_effect = lambda key, tenant_id=None: {
            "INVENTORY": 11,
            "GST_INPUT_CREDIT": 12,
            "ACCOUNTS_PAYABLE": 13,
            "TDS_PAYABLE": 14,
        }[key]
        doc = SimpleNamespace(
            id=2,
            internal_number="PI-1",
            vendor_id=8,
            vendor=SimpleNamespace(id=8),
            purchase_type="GOODS",
            taxable_amount=Money(100, "INR"),
            cgst_amount=Money(9, "INR"),
            sgst_amount=Money(9, "INR"),
            igst_amount=Money(0, "INR"),
            tds_amount=Money(5, "INR"),
            net_payable=Money(113, "INR"),
        )

        bundle = PurchaseGoodsRule().build_posting(SimpleNamespace(doc=doc))

        self.assertEqual(len(bundle.ledger_lines), 4)
        self.assertEqual(len(bundle.account_lines), 1)
        self.assertEqual(bundle.account_lines[0].account_id, 601)
        self.assertEqual(bundle.account_lines[0].ledger_id, 13)
        self.assertEqual(bundle.account_lines[0].side, "Cr")
        self.assertEqual(bundle.account_lines[0].amount, Decimal("113"))
        mock_resolve_account.assert_called_once_with(doc)
