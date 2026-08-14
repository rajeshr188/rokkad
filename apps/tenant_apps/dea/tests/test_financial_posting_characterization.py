from collections import defaultdict
from datetime import date
from decimal import Decimal
import uuid

from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import RequestFactory
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.dea.models import (
    AccountTransaction,
    AccountBalance,
    AccountingPeriod,
    AccountType,
    AccountType_Ext,
    EntityType,
    ExpenseCategory,
    ExpenseLineItem,
    ExpenseSource,
    ExpenseVoucher,
    JournalEntryLineItem,
    JournalEntryVoucher,
    Ledger,
    LedgerBalance,
    LedgerTransaction,
    PurchaseInvoiceVoucher,
    SalesInvoiceVoucher,
    TransactionType_DE,
    Voucher,
    VoucherLine,
    VoucherStatus,
    VoucherType,
)
from apps.tenant_apps.dea.posting.context import PostingContext
from apps.tenant_apps.dea.posting.engine import DjangoPostingEngine
from apps.tenant_apps.dea.services.reversal import (
    VoucherNotPostedError,
    reverse_posted_voucher,
)
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc
from apps.tenant_apps.dea.views.expense import post_expense_voucher as post_expense_voucher_view
from apps.tenant_apps.dea.views.voucher import post_voucher as post_voucher_view
from apps.tenant_apps.dea.views.voucher import reverse_voucher as reverse_voucher_view


User = get_user_model()


class FinancialPostingCharacterizationTests(TenantTestCase):
    test_schema_name = f"dea_fin_post_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = User.objects.get_or_create(
            username="dea-fin-post-owner",
            defaults={"email": "dea-fin-post-owner@example.com"},
        )
        owner.set_password("testpass123")
        owner.save(update_fields=["password"])
        tenant.name = f"dea-fin-post-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username=f"dea-fin-post-user-{uuid.uuid4().hex[:8]}",
            email=f"dea-fin-post-user-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            is_staff=True,
        )
        self.period = AccountingPeriod.objects.create(
            name="April 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )
        self.request_factory = RequestFactory()
        self._seed_account_masters()
        self.ledgers = self._seed_ledgers()

    def test_manual_journal_posts_balanced_ledger_transactions_only(self):
        doc = JournalEntryVoucher.objects.create(
            je_date=date(2026, 4, 30),
            entry_type="ADJUSTMENT",
            description="Owner capital introduced",
            memo="CHAR-JE",
            reference="CHAR-JE-001",
            total_debit=Money(Decimal("500.00"), "INR"),
            total_credit=Money(Decimal("500.00"), "INR"),
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )
        JournalEntryLineItem.objects.bulk_create(
            [
                JournalEntryLineItem(
                    journal_entry=doc,
                    line_number=1,
                    ledger_id=self.ledgers["CASH"].pk,
                    ledger_name=self.ledgers["CASH"].name,
                    side="DR",
                    amount=Money(Decimal("500.00"), "INR"),
                    description="Cash introduced",
                ),
                JournalEntryLineItem(
                    journal_entry=doc,
                    line_number=2,
                    ledger_id=self.ledgers["CAPITAL"].pk,
                    ledger_name=self.ledgers["CAPITAL"].name,
                    side="CR",
                    amount=Money(Decimal("500.00"), "INR"),
                    description="Capital introduced",
                ),
            ]
        )

        voucher, journal_entry = self._post_doc(doc)

        self.assertEqual(voucher.status, VoucherStatus.POSTED)
        self.assertTrue(voucher.fingerprint)
        self.assertEqual(journal_entry.period, self.period)
        self.assertEqual(journal_entry.posted_by, self.user)
        self.assertTrue(journal_entry.validate_balanced()[0])
        self.assertEqual(LedgerTransaction.objects.filter(journal_entry=journal_entry).count(), 1)
        self.assertEqual(AccountTransaction.objects.filter(journal_entry=journal_entry).count(), 0)

        ledger_txn = journal_entry.ltxns.get()
        self.assertEqual(ledger_txn.ledgerno_dr, self.ledgers["CASH"])
        self.assertEqual(ledger_txn.ledgerno, self.ledgers["CAPITAL"])
        self.assertEqual(ledger_txn.amount, Money(Decimal("500.000"), "INR"))
        self.assertEqual(ledger_txn.amount_base, Money(Decimal("500.000"), "INR"))

    def test_sales_invoice_posts_financial_gl_and_customer_subledger_rows(self):
        customer = Customer.objects.create(
            firstname="Retail",
            lastname="Buyer",
            customer_type=Customer.CustomerType.Retail,
        )
        doc = SalesInvoiceVoucher.objects.create(
            invoice_number="CHAR-SALE-001",
            invoice_date=date(2026, 4, 15),
            customer=customer,
            subtotal=Money(Decimal("100.00"), "INR"),
            discount_amount=Money(Decimal("0.00"), "INR"),
            taxable_amount=Money(Decimal("100.00"), "INR"),
            cgst_amount=Money(Decimal("9.00"), "INR"),
            sgst_amount=Money(Decimal("9.00"), "INR"),
            igst_amount=Money(Decimal("0.00"), "INR"),
            tcs_amount=Money(Decimal("0.00"), "INR"),
            total_amount=Money(Decimal("118.00"), "INR"),
            description="Characterization sale",
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )

        voucher, journal_entry = self._post_doc(doc)

        self.assertEqual(voucher.status, VoucherStatus.POSTED)
        self.assertTrue(journal_entry.validate_balanced()[0])
        self.assertEqual(journal_entry.ltxns.count(), 3)
        self.assertEqual(journal_entry.atxns.count(), 1)
        self.assert_ledger_totals(
            journal_entry,
            debits={"Accounts Receivable": Decimal("118.000")},
            credits={
                "Sales": Decimal("100.000"),
                "Output CGST": Decimal("9.000"),
                "Output SGST": Decimal("9.000"),
            },
        )

        account_txn = journal_entry.atxns.select_related("Account", "ledgerno", "XactTypeCode").get()
        self.assertEqual(account_txn.Account.contact, customer)
        self.assertEqual(account_txn.ledgerno, self.ledgers["ACCOUNTS_RECEIVABLE"])
        self.assertEqual(account_txn.XactTypeCode_id, "Dr")
        self.assertEqual(account_txn.amount, Money(Decimal("118.000"), "INR"))

    def test_purchase_invoice_posts_financial_gl_and_supplier_subledger_rows(self):
        supplier = Customer.objects.create(
            firstname="Bullion",
            lastname="Supplier",
            customer_type=Customer.CustomerType.Supplier,
        )
        doc = PurchaseInvoiceVoucher.objects.create(
            invoice_number="SUP-001",
            internal_number="CHAR-PUR-001",
            invoice_date=date(2026, 4, 18),
            vendor=supplier,
            purchase_type="GOODS",
            subtotal=Money(Decimal("100.00"), "INR"),
            discount_amount=Money(Decimal("0.00"), "INR"),
            taxable_amount=Money(Decimal("100.00"), "INR"),
            cgst_amount=Money(Decimal("9.00"), "INR"),
            sgst_amount=Money(Decimal("9.00"), "INR"),
            igst_amount=Money(Decimal("0.00"), "INR"),
            tds_amount=Money(Decimal("5.00"), "INR"),
            total_amount=Money(Decimal("118.00"), "INR"),
            net_payable=Money(Decimal("113.00"), "INR"),
            description="Characterization purchase",
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )

        voucher, journal_entry = self._post_doc(doc)

        self.assertEqual(voucher.status, VoucherStatus.POSTED)
        self.assertTrue(journal_entry.validate_balanced()[0])
        self.assertEqual(journal_entry.ltxns.count(), 4)
        self.assertEqual(journal_entry.atxns.count(), 1)
        self.assert_ledger_totals(
            journal_entry,
            debits={
                "INVENTORY": Decimal("100.000"),
                "GST_INPUT_CREDIT": Decimal("18.000"),
                "ACCOUNTS_PAYABLE": Decimal("5.000"),
            },
            credits={
                "ACCOUNTS_PAYABLE": Decimal("118.000"),
                "TDS_PAYABLE": Decimal("5.000"),
            },
        )

        account_txn = journal_entry.atxns.select_related("Account", "ledgerno", "XactTypeCode").get()
        self.assertEqual(account_txn.Account.contact, supplier)
        self.assertEqual(account_txn.ledgerno, self.ledgers["ACCOUNTS_PAYABLE"])
        self.assertEqual(account_txn.XactTypeCode_id, "Cr")
        self.assertEqual(account_txn.amount, Money(Decimal("113.000"), "INR"))

    def test_account_transactions_are_subledger_attribution_not_gl_balance_basis(self):
        customer = Customer.objects.create(
            firstname="Control",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
        )
        doc = SalesInvoiceVoucher.objects.create(
            invoice_number="CHAR-SALE-SEM-001",
            invoice_date=date(2026, 4, 16),
            customer=customer,
            subtotal=Money(Decimal("100.00"), "INR"),
            discount_amount=Money(Decimal("0.00"), "INR"),
            taxable_amount=Money(Decimal("100.00"), "INR"),
            cgst_amount=Money(Decimal("9.00"), "INR"),
            sgst_amount=Money(Decimal("9.00"), "INR"),
            igst_amount=Money(Decimal("0.00"), "INR"),
            tcs_amount=Money(Decimal("0.00"), "INR"),
            total_amount=Money(Decimal("118.00"), "INR"),
            description="Subledger characterization sale",
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )

        _, journal_entry = self._post_doc(doc)

        is_balanced, debit_totals, credit_totals, imbalances = journal_entry.validate_balanced()

        self.assertTrue(is_balanced)
        self.assertEqual(imbalances, {})
        self.assertEqual(debit_totals[Money(0, "INR").currency], Decimal("118.000"))
        self.assertEqual(credit_totals[Money(0, "INR").currency], Decimal("118.000"))
        self.assertEqual(journal_entry.atxns.count(), 1)
        self.assertEqual(
            journal_entry.atxns.get().amount,
            Money(Decimal("118.000"), "INR"),
        )

    def test_account_balance_view_tracks_party_subledger_amount_for_customer(self):
        customer = Customer.objects.create(
            firstname="Statement",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
        )
        doc = SalesInvoiceVoucher.objects.create(
            invoice_number="CHAR-SALE-BAL-001",
            invoice_date=date(2026, 4, 17),
            customer=customer,
            subtotal=Money(Decimal("100.00"), "INR"),
            discount_amount=Money(Decimal("0.00"), "INR"),
            taxable_amount=Money(Decimal("100.00"), "INR"),
            cgst_amount=Money(Decimal("9.00"), "INR"),
            sgst_amount=Money(Decimal("9.00"), "INR"),
            igst_amount=Money(Decimal("0.00"), "INR"),
            tcs_amount=Money(Decimal("0.00"), "INR"),
            total_amount=Money(Decimal("118.00"), "INR"),
            description="Balance view characterization sale",
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )

        self._post_doc(doc)
        account = AccountTransaction.objects.select_related("Account").latest("id").Account

        balance = AccountBalance.objects.get(account=account, currency="INR")

        self.assertEqual(balance.debit_sum, Decimal("118.000"))
        self.assertEqual(balance.credit_sum, Decimal("0.000"))
        self.assertEqual(balance.current_balance, Decimal("118.000"))

    def test_ledger_balance_view_currently_merges_gl_and_subledger_effects(self):
        customer = Customer.objects.create(
            firstname="Merged",
            lastname="Customer",
            customer_type=Customer.CustomerType.Retail,
        )
        doc = SalesInvoiceVoucher.objects.create(
            invoice_number="CHAR-SALE-VIEW-001",
            invoice_date=date(2026, 4, 19),
            customer=customer,
            subtotal=Money(Decimal("100.00"), "INR"),
            discount_amount=Money(Decimal("0.00"), "INR"),
            taxable_amount=Money(Decimal("100.00"), "INR"),
            cgst_amount=Money(Decimal("9.00"), "INR"),
            sgst_amount=Money(Decimal("9.00"), "INR"),
            igst_amount=Money(Decimal("0.00"), "INR"),
            tcs_amount=Money(Decimal("0.00"), "INR"),
            total_amount=Money(Decimal("118.00"), "INR"),
            description="Ledger balance view characterization sale",
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )

        self._post_doc(doc)

        balance = LedgerBalance.objects.get(
            ledgerno=self.ledgers["ACCOUNTS_RECEIVABLE"],
            currency="INR",
        )

        self.assertEqual(balance.ledger_debit_sum, Decimal("118.000"))
        self.assertEqual(balance.account_debit_sum, Decimal("118.000"))
        self.assertEqual(balance.total_debit_sum, Decimal("236.000"))
        self.assertEqual(balance.current_balance, Decimal("236.000"))

    def test_posted_journal_voucher_line_and_ledger_transaction_are_immutable(self):
        doc = JournalEntryVoucher.objects.create(
            je_date=date(2026, 4, 30),
            entry_type="ADJUSTMENT",
            description="Owner capital introduced",
            memo="IMMUTABLE-JE",
            reference="IMMUTABLE-JE-001",
            total_debit=Money(Decimal("500.00"), "INR"),
            total_credit=Money(Decimal("500.00"), "INR"),
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )
        JournalEntryLineItem.objects.bulk_create(
            [
                JournalEntryLineItem(
                    journal_entry=doc,
                    line_number=1,
                    ledger_id=self.ledgers["CASH"].pk,
                    ledger_name=self.ledgers["CASH"].name,
                    side="DR",
                    amount=Money(Decimal("500.00"), "INR"),
                    description="Cash introduced",
                ),
                JournalEntryLineItem(
                    journal_entry=doc,
                    line_number=2,
                    ledger_id=self.ledgers["CAPITAL"].pk,
                    ledger_name=self.ledgers["CAPITAL"].name,
                    side="CR",
                    amount=Money(Decimal("500.00"), "INR"),
                    description="Capital introduced",
                ),
            ]
        )

        voucher, journal_entry = self._post_doc(doc)

        journal_entry.desc = "mutated after post"
        with self.assertRaises(ValidationError):
            journal_entry.save()
        with self.assertRaises(ValidationError):
            journal_entry.delete()

        voucher_line = voucher.lines.first()
        voucher_line.narration = "mutated after post"
        with self.assertRaises(ValidationError):
            voucher_line.save()

        ledger_txn = journal_entry.ltxns.get()
        ledger_txn.amount = Money(Decimal("600.00"), "INR")
        with self.assertRaises(ValidationError):
            ledger_txn.save()
        with self.assertRaises(ValidationError):
            ledger_txn.delete()

    def test_posted_account_transaction_is_immutable(self):
        customer = Customer.objects.create(
            firstname="Immutable",
            lastname="Buyer",
            customer_type=Customer.CustomerType.Retail,
        )
        doc = SalesInvoiceVoucher.objects.create(
            invoice_number="IMMUTABLE-SALE-001",
            invoice_date=date(2026, 4, 15),
            customer=customer,
            subtotal=Money(Decimal("100.00"), "INR"),
            discount_amount=Money(Decimal("0.00"), "INR"),
            taxable_amount=Money(Decimal("100.00"), "INR"),
            cgst_amount=Money(Decimal("9.00"), "INR"),
            sgst_amount=Money(Decimal("9.00"), "INR"),
            igst_amount=Money(Decimal("0.00"), "INR"),
            tcs_amount=Money(Decimal("0.00"), "INR"),
            total_amount=Money(Decimal("118.00"), "INR"),
            description="Immutable account transaction sale",
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )

        _, journal_entry = self._post_doc(doc)

        account_txn = journal_entry.atxns.get()
        account_txn.amount = Money(Decimal("119.00"), "INR")
        with self.assertRaises(ValidationError):
            account_txn.save()
        with self.assertRaises(ValidationError):
            account_txn.delete()

    def test_posting_same_voucher_twice_returns_existing_journal_entry(self):
        doc = self._build_manual_journal_doc(
            reference="IDEMPOTENT-SAME-VOUCHER",
            amount=Decimal("500.00"),
        )
        voucher, first_journal_entry = self._post_doc(doc)

        second_journal_entry = DjangoPostingEngine().post(
            PostingContext(voucher=voucher, doc=doc, user_id=self.user.id)
        )
        voucher.refresh_from_db()

        self.assertEqual(voucher.status, VoucherStatus.POSTED)
        self.assertEqual(second_journal_entry, first_journal_entry)
        self.assertEqual(voucher.journal_entries.count(), 1)
        self.assertEqual(LedgerTransaction.objects.filter(journal_entry=first_journal_entry).count(), 1)

    def test_create_and_post_same_document_payload_returns_existing_posting(self):
        doc = self._build_manual_journal_doc(
            reference="IDEMPOTENT-SAME-DOC",
            amount=Decimal("500.00"),
        )
        voucher_type = self._ensure_voucher_type(doc)

        first_voucher, first_journal_entry = create_and_post_voucher_for_doc(
            doc,
            self.user,
            voucher_type,
            DjangoPostingEngine(),
        )
        second_voucher, second_journal_entry = create_and_post_voucher_for_doc(
            doc,
            self.user,
            voucher_type,
            DjangoPostingEngine(),
        )

        self.assertEqual(second_voucher, first_voucher)
        self.assertEqual(second_journal_entry, first_journal_entry)
        self.assertEqual(
            Voucher.objects.filter(
                doc_content_type=ContentType.objects.get_for_model(doc),
                doc_object_id=doc.pk,
                voucher_type=first_voucher.voucher_type,
            ).count(),
            1,
        )
        self.assertEqual(first_voucher.journal_entries.count(), 1)

    def test_changed_document_payload_reverses_previous_and_posts_correction(self):
        doc = self._build_manual_journal_doc(
            reference="IDEMPOTENT-CHANGED-DOC",
            amount=Decimal("500.00"),
        )
        voucher_type = self._ensure_voucher_type(doc)
        first_voucher, first_journal_entry = create_and_post_voucher_for_doc(
            doc,
            self.user,
            voucher_type,
            DjangoPostingEngine(),
        )

        doc.line_items.update(amount=Money(Decimal("600.00"), "INR"))
        doc.total_debit = Money(Decimal("600.00"), "INR")
        doc.total_credit = Money(Decimal("600.00"), "INR")
        doc.save(update_fields=["total_debit", "total_credit"])

        second_voucher, second_journal_entry = create_and_post_voucher_for_doc(
            doc,
            self.user,
            voucher_type,
            DjangoPostingEngine(),
        )
        first_voucher.refresh_from_db()

        self.assertNotEqual(second_voucher, first_voucher)
        self.assertEqual(second_voucher.corrected_from, first_voucher)
        self.assertEqual(first_voucher.status, VoucherStatus.REVERSED)
        self.assertEqual(second_voucher.status, VoucherStatus.POSTED)
        self.assertNotEqual(second_journal_entry, first_journal_entry)
        self.assertTrue(
            first_voucher.journal_entries.filter(is_reversal_of=first_journal_entry).exists()
        )
        self.assertEqual(
            Voucher.objects.filter(
                doc_content_type=ContentType.objects.get_for_model(doc),
                doc_object_id=doc.pk,
                voucher_type=first_voucher.voucher_type,
                status=VoucherStatus.POSTED,
            ).count(),
            1,
        )
        corrected_txn = second_journal_entry.ltxns.get()
        self.assertEqual(corrected_txn.amount, Money(Decimal("600.000"), "INR"))

    def test_reverse_posted_voucher_creates_opposite_journal_entry(self):
        doc = self._build_manual_journal_doc(
            reference="REVERSAL-MANUAL",
            amount=Decimal("500.00"),
        )
        voucher, original_je = self._post_doc(doc)

        result = reverse_posted_voucher(
            voucher=voucher,
            actor=self.user,
            reason="Characterization reversal",
        )
        voucher.refresh_from_db()

        self.assertFalse(result.already_reversed)
        self.assertEqual(voucher.status, VoucherStatus.REVERSED)
        self.assertEqual(result.original_journal_entry, original_je)
        self.assertEqual(result.reversal_journal_entry.is_reversal_of, original_je)
        self.assertEqual(voucher.journal_entries.count(), 2)

        original_txn = original_je.ltxns.get()
        reversal_txn = result.reversal_journal_entry.ltxns.get()
        self.assertEqual(reversal_txn.ledgerno_dr, original_txn.ledgerno)
        self.assertEqual(reversal_txn.ledgerno, original_txn.ledgerno_dr)
        self.assertEqual(reversal_txn.amount, original_txn.amount)
        self.assertEqual(reversal_txn.amount_base, original_txn.amount_base)

    def test_engine_reverse_voucher_is_idempotent(self):
        doc = self._build_manual_journal_doc(
            reference="REVERSAL-IDEMPOTENT",
            amount=Decimal("500.00"),
        )
        voucher, original_je = self._post_doc(doc)

        first_reversal = DjangoPostingEngine().reverse_voucher(voucher.pk, self.user)
        second_reversal = DjangoPostingEngine().reverse_voucher(voucher.pk, self.user)
        voucher.refresh_from_db()

        self.assertEqual(voucher.status, VoucherStatus.REVERSED)
        self.assertEqual(first_reversal, second_reversal)
        self.assertEqual(
            voucher.journal_entries.filter(is_reversal_of=original_je).count(),
            1,
        )

    def test_reverse_posted_voucher_flips_account_transaction_side(self):
        customer = Customer.objects.create(
            firstname="Reversal",
            lastname="Buyer",
            customer_type=Customer.CustomerType.Retail,
        )
        doc = SalesInvoiceVoucher.objects.create(
            invoice_number="REVERSAL-SALE-001",
            invoice_date=date(2026, 4, 15),
            customer=customer,
            subtotal=Money(Decimal("100.00"), "INR"),
            discount_amount=Money(Decimal("0.00"), "INR"),
            taxable_amount=Money(Decimal("100.00"), "INR"),
            cgst_amount=Money(Decimal("9.00"), "INR"),
            sgst_amount=Money(Decimal("9.00"), "INR"),
            igst_amount=Money(Decimal("0.00"), "INR"),
            tcs_amount=Money(Decimal("0.00"), "INR"),
            total_amount=Money(Decimal("118.00"), "INR"),
            description="Reversal account side sale",
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )
        voucher, original_je = self._post_doc(doc)

        result = reverse_posted_voucher(
            voucher=voucher,
            actor=self.user,
            reason="Reverse sale",
        )

        original_account_txn = original_je.atxns.get()
        reversal_account_txn = result.reversal_journal_entry.atxns.get()
        self.assertEqual(original_account_txn.XactTypeCode_id, "Dr")
        self.assertEqual(reversal_account_txn.XactTypeCode_id, "Cr")
        self.assertEqual(reversal_account_txn.Account, original_account_txn.Account)
        self.assertEqual(reversal_account_txn.ledgerno, original_account_txn.ledgerno)
        self.assertEqual(reversal_account_txn.amount, original_account_txn.amount)

    def test_reverse_draft_voucher_is_rejected(self):
        doc = self._build_manual_journal_doc(
            reference="REVERSAL-DRAFT",
            amount=Decimal("500.00"),
        )
        voucher_type = self._ensure_voucher_type(doc)
        draft_voucher = Voucher.objects.create(
            voucher_no="REVERSAL-DRAFT-001",
            voucher_type=voucher_type,
            voucher_date=doc.je_date,
            status=VoucherStatus.DRAFT,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(doc),
            doc_object_id=doc.pk,
        )

        with self.assertRaises(VoucherNotPostedError):
            reverse_posted_voucher(
                voucher=draft_voucher,
                actor=self.user,
                reason="Cannot reverse draft",
            )

    def test_voucher_post_view_uses_command_for_manual_voucher_lines(self):
        voucher = self._build_manual_line_voucher("POST-VIEW-MANUAL-001")
        request = self._build_post_view_request(voucher)

        response = post_voucher_view(request, pk=voucher.pk)
        voucher.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(voucher.status, VoucherStatus.POSTED)
        self.assertTrue(voucher.fingerprint)
        self.assertEqual(voucher.journal_entries.count(), 1)
        journal_entry = voucher.journal_entries.get()
        self.assertEqual(journal_entry.period, self.period)
        self.assertEqual(journal_entry.ltxns.count(), 1)
        ledger_txn = journal_entry.ltxns.get()
        self.assertEqual(ledger_txn.ledgerno_dr, self.ledgers["CASH"])
        self.assertEqual(ledger_txn.ledgerno, self.ledgers["CAPITAL"])

    def test_voucher_post_view_rejects_closed_period_without_materializing(self):
        self.period.status = "CLOSED"
        self.period.save(update_fields=["status"])
        voucher = self._build_manual_line_voucher("POST-VIEW-CLOSED-001")
        request = self._build_post_view_request(voucher)

        response = post_voucher_view(request, pk=voucher.pk)
        voucher.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(voucher.status, VoucherStatus.DRAFT)
        self.assertEqual(voucher.journal_entries.count(), 0)

    def test_voucher_reverse_view_uses_reversal_service_for_posted_voucher(self):
        doc = self._build_manual_journal_doc(
            reference="REVERSAL-VIEW",
            amount=Decimal("500.00"),
        )
        voucher, original_je = self._post_doc(doc)
        request = self._build_reverse_view_request(
            voucher,
            {"reason": "Reverse through voucher view"},
        )

        response = reverse_voucher_view(request, pk=voucher.pk)
        voucher.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(voucher.status, VoucherStatus.REVERSED)
        self.assertEqual(
            voucher.journal_entries.filter(is_reversal_of=original_je).count(),
            1,
        )
        reversal_je = voucher.journal_entries.get(is_reversal_of=original_je)
        self.assertEqual(reversal_je.ltxns.count(), original_je.ltxns.count())

    def test_voucher_reverse_view_rejects_draft_voucher_without_materializing(self):
        doc = self._build_manual_journal_doc(
            reference="REVERSAL-VIEW-DRAFT",
            amount=Decimal("500.00"),
        )
        voucher_type = self._ensure_voucher_type(doc)
        draft_voucher = Voucher.objects.create(
            voucher_no="REVERSAL-VIEW-DRAFT-001",
            voucher_type=voucher_type,
            voucher_date=doc.je_date,
            status=VoucherStatus.DRAFT,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(doc),
            doc_object_id=doc.pk,
        )
        request = self._build_reverse_view_request(
            draft_voucher,
            {"reason": "Cannot reverse draft through view"},
        )

        response = reverse_voucher_view(request, pk=draft_voucher.pk)
        draft_voucher.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(draft_voucher.status, VoucherStatus.DRAFT)
        self.assertEqual(draft_voucher.journal_entries.count(), 0)

    def test_expense_post_view_is_idempotent_for_direct_payment(self):
        expense = self._build_direct_payment_expense(
            expense_number="EXP-DIRECT-IDEMPOTENT-001",
            amount=Decimal("100.00"),
        )
        request = self._build_expense_post_view_request(expense)

        first_response = post_expense_voucher_view(request, pk=expense.pk)
        second_response = post_expense_voucher_view(request, pk=expense.pk)

        self.assertEqual(first_response.status_code, 302)
        self.assertEqual(second_response.status_code, 302)
        posted_vouchers = Voucher.objects.filter(
            doc_content_type=ContentType.objects.get_for_model(expense),
            doc_object_id=expense.pk,
            status=VoucherStatus.POSTED,
        )
        self.assertEqual(posted_vouchers.count(), 1)

        voucher = posted_vouchers.get()
        self.assertEqual(voucher.journal_entries.count(), 1)
        journal_entry = voucher.journal_entries.get()
        self.assertTrue(journal_entry.validate_balanced()[0])
        self.assertEqual(LedgerTransaction.objects.filter(journal_entry=journal_entry).count(), 2)

    def test_expense_post_view_closed_period_does_not_materialize_journal_effects(self):
        self.period.status = AccountingPeriod.PeriodStatus.CLOSED
        self.period.save(update_fields=["status"])
        expense = self._build_direct_payment_expense(
            expense_number="EXP-DIRECT-CLOSED-001",
            amount=Decimal("100.00"),
        )
        request = self._build_expense_post_view_request(expense)

        response = post_expense_voucher_view(request, pk=expense.pk)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            Voucher.objects.filter(
                doc_content_type=ContentType.objects.get_for_model(expense),
                doc_object_id=expense.pk,
                status=VoucherStatus.POSTED,
            ).count(),
            0,
        )
        self.assertEqual(LedgerTransaction.objects.count(), 0)
        self.assertEqual(AccountTransaction.objects.count(), 0)

    def _post_doc(self, doc):
        voucher_type = self._ensure_voucher_type(doc)
        voucher = Voucher.objects.create(
            voucher_no=f"CHAR-{doc.get_voucher_type()}-{doc.pk}",
            voucher_type=voucher_type,
            voucher_date=getattr(doc, "je_date", None)
            or getattr(doc, "invoice_date", None),
            status=VoucherStatus.DRAFT,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(doc),
            doc_object_id=doc.pk,
        )

        journal_entry = DjangoPostingEngine().post(
            PostingContext(voucher=voucher, doc=doc, user_id=self.user.id)
        )
        voucher.refresh_from_db()
        return voucher, journal_entry

    def _ensure_voucher_type(self, doc):
        voucher_type, _ = VoucherType.objects.get_or_create(
            name=doc.get_voucher_type(),
            defaults={"description": doc.get_voucher_type()},
        )
        return voucher_type

    def _build_manual_journal_doc(self, *, reference, amount):
        doc = JournalEntryVoucher.objects.create(
            je_date=date(2026, 4, 30),
            entry_type="ADJUSTMENT",
            description="Owner capital introduced",
            memo=reference,
            reference=reference,
            total_debit=Money(amount, "INR"),
            total_credit=Money(amount, "INR"),
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )
        JournalEntryLineItem.objects.bulk_create(
            [
                JournalEntryLineItem(
                    journal_entry=doc,
                    line_number=1,
                    ledger_id=self.ledgers["CASH"].pk,
                    ledger_name=self.ledgers["CASH"].name,
                    side="DR",
                    amount=Money(amount, "INR"),
                    description="Cash introduced",
                ),
                JournalEntryLineItem(
                    journal_entry=doc,
                    line_number=2,
                    ledger_id=self.ledgers["CAPITAL"].pk,
                    ledger_name=self.ledgers["CAPITAL"].name,
                    side="CR",
                    amount=Money(amount, "INR"),
                    description="Capital introduced",
                ),
            ]
        )
        return doc

    def _build_direct_payment_expense(self, *, expense_number, amount):
        expense = ExpenseVoucher.objects.create(
            expense_number=expense_number,
            expense_date=date(2026, 4, 15),
            source_type=ExpenseSource.DIRECT_PAYMENT,
            party_name="Office Vendor",
            gross_amount=Money(amount, "INR"),
            taxable_amount=Money(Decimal("0.00"), "INR"),
            tax_amount=Money(Decimal("0.00"), "INR"),
            tds_amount=Money(Decimal("0.00"), "INR"),
            description=expense_number,
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )
        ExpenseLineItem.objects.create(
            expense_voucher=expense,
            line_number=1,
            category=ExpenseCategory.FOOD,
            description="Team meal",
            amount=Money(amount, "INR"),
            is_taxable=False,
            tax_rate=Decimal("0.00"),
            tds_rate=Decimal("0.00"),
        )
        return expense

    def _build_manual_line_voucher(self, voucher_no):
        voucher_type, _ = VoucherType.objects.get_or_create(
            name="MANUAL_VIEW_LINES",
            defaults={"description": "Manual voucher view line posting"},
        )
        voucher = Voucher.objects.create(
            voucher_no=voucher_no,
            voucher_type=voucher_type,
            voucher_date=self.period.end_date,
            status=VoucherStatus.DRAFT,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(AccountingPeriod),
            doc_object_id=self.period.pk,
        )
        VoucherLine.objects.bulk_create(
            [
                VoucherLine(
                    voucher=voucher,
                    line_no=1,
                    side=VoucherLine.LineSide.DR,
                    ledger=self.ledgers["CASH"],
                    amount=Money(Decimal("500.00"), "INR"),
                    amount_base=Money(Decimal("500.00"), "INR"),
                    narration="Cash debit",
                ),
                VoucherLine(
                    voucher=voucher,
                    line_no=2,
                    side=VoucherLine.LineSide.CR,
                    ledger=self.ledgers["CAPITAL"],
                    amount=Money(Decimal("500.00"), "INR"),
                    amount_base=Money(Decimal("500.00"), "INR"),
                    narration="Capital credit",
                ),
            ]
        )
        return voucher

    def _build_post_view_request(self, voucher, data=None):
        request = self.request_factory.post(
            f"/dea/vouchers/{voucher.pk}/post/",
            data=data or {},
        )
        request.user = self.user
        request.tenant = self.tenant
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def _build_expense_post_view_request(self, expense):
        request = self.request_factory.post(
            f"/dea/expenses/{expense.pk}/post/",
            data={},
        )
        request.user = self.user
        request.tenant = self.tenant
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def _build_reverse_view_request(self, voucher, data=None):
        request = self.request_factory.post(
            f"/dea/vouchers/{voucher.pk}/reverse/",
            data=data or {},
        )
        request.user = self.user
        request.tenant = self.tenant
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))
        return request

    def assert_ledger_totals(self, journal_entry, *, debits, credits):
        debit_totals = defaultdict(Decimal)
        credit_totals = defaultdict(Decimal)
        for txn in journal_entry.ltxns.select_related("ledgerno_dr", "ledgerno"):
            debit_totals[txn.ledgerno_dr.name] += txn.amount.amount
            credit_totals[txn.ledgerno.name] += txn.amount.amount

        self.assertEqual(dict(debit_totals), debits)
        self.assertEqual(dict(credit_totals), credits)

    def _seed_account_masters(self):
        debit_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Dr",
            defaults={"name": "Debit"},
        )
        credit_code, _ = TransactionType_DE.objects.get_or_create(
            XactTypeCode="Cr",
            defaults={"name": "Credit"},
        )
        AccountType_Ext.objects.get_or_create(
            description="Debtor",
            defaults={"XactTypeCode": debit_code},
        )
        AccountType_Ext.objects.get_or_create(
            description="Creditor",
            defaults={"XactTypeCode": credit_code},
        )
        EntityType.objects.get_or_create(name="Person")
        EntityType.objects.get_or_create(name="Organisation")

    def _seed_ledgers(self):
        asset_type, _ = AccountType.objects.get_or_create(
            AccountType="Asset",
            defaults={"description": "Asset", "code_prefix": "1"},
        )
        liability_type, _ = AccountType.objects.get_or_create(
            AccountType="Liability",
            defaults={"description": "Liability", "code_prefix": "2"},
        )
        equity_type, _ = AccountType.objects.get_or_create(
            AccountType="Equity",
            defaults={"description": "Equity", "code_prefix": "3"},
        )
        revenue_type, _ = AccountType.objects.get_or_create(
            AccountType="Revenue",
            defaults={"description": "Revenue", "code_prefix": "4"},
        )
        expense_type, _ = AccountType.objects.get_or_create(
            AccountType="Expense",
            defaults={"description": "Expense", "code_prefix": "5"},
        )

        cash, _ = Ledger.objects.get_or_create(
            name="CASH",
            defaults={
                "AccountType": asset_type,
                "code": "1.CHAR.CASH",
            },
        )
        cash_title, _ = Ledger.objects.get_or_create(
            name="Cash",
            defaults={
                "AccountType": asset_type,
                "code": "1.CHAR.CASH.TITLE",
            },
        )
        capital, _ = Ledger.objects.get_or_create(
            name="CHARACTERIZATION_CAPITAL",
            defaults={
                "AccountType": equity_type,
                "code": "3.CHAR.CAPITAL",
            },
        )
        ar, _ = Ledger.objects.get_or_create(
            name="Accounts Receivable",
            defaults={
                "AccountType": asset_type,
                "code": "1.CHAR.AR",
            },
        )
        sales, _ = Ledger.objects.get_or_create(
            name="Sales",
            defaults={
                "AccountType": revenue_type,
                "code": "4.CHAR.SALES",
            },
        )
        cgst, _ = Ledger.objects.get_or_create(
            name="Output CGST",
            defaults={
                "AccountType": liability_type,
                "code": "2.CHAR.CGST",
            },
        )
        sgst, _ = Ledger.objects.get_or_create(
            name="Output SGST",
            defaults={
                "AccountType": liability_type,
                "code": "2.CHAR.SGST",
            },
        )
        inventory, _ = Ledger.objects.get_or_create(
            name="INVENTORY",
            defaults={
                "AccountType": asset_type,
                "code": "1.CHAR.INVENTORY",
            },
        )
        gst_input, _ = Ledger.objects.get_or_create(
            name="GST_INPUT_CREDIT",
            defaults={
                "AccountType": asset_type,
                "code": "1.CHAR.GSTINPUT",
            },
        )
        ap, _ = Ledger.objects.get_or_create(
            name="ACCOUNTS_PAYABLE",
            defaults={
                "AccountType": liability_type,
                "code": "2.CHAR.AP",
            },
        )
        tds, _ = Ledger.objects.get_or_create(
            name="TDS_PAYABLE",
            defaults={
                "AccountType": liability_type,
                "code": "2.CHAR.TDS",
            },
        )
        expense_suspense, _ = Ledger.objects.get_or_create(
            name="EXPENSE_SUSPENSE",
            defaults={
                "AccountType": liability_type,
                "code": "2.CHAR.EXPENSESUSPENSE",
            },
        )
        food_expense, _ = Ledger.objects.get_or_create(
            name="FOOD_EXPENSE",
            defaults={
                "AccountType": expense_type,
                "code": "5.CHAR.FOOD",
            },
        )

        return {
            "CASH": cash,
            "Cash": cash_title,
            "CAPITAL": capital,
            "ACCOUNTS_RECEIVABLE": ar,
            "SALES_REVENUE": sales,
            "CGST_OUTPUT": cgst,
            "SGST_OUTPUT": sgst,
            "INVENTORY": inventory,
            "GST_INPUT_CREDIT": gst_input,
            "ACCOUNTS_PAYABLE": ap,
            "TDS_PAYABLE": tds,
            "EXPENSE_SUSPENSE": expense_suspense,
            "FOOD_EXPENSE": food_expense,
        }
