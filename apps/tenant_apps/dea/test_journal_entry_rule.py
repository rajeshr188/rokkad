from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import uuid

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import connection
from django.test import RequestFactory
from django.urls import reverse
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from .models import AccountingPeriod, AccountType, JournalEntryLineItem, JournalEntryVoucher, Ledger, Voucher
from .posting.rules.journal_entry import JournalEntryRule
from .views.journal_entry_voucher import (
    JournalEntryVoucherCreateView,
    JournalEntryVoucherDetailView,
    JournalEntryVoucherListView,
)


User = get_user_model()


class JournalEntryRuleTests(TenantTestCase):
    test_schema_name = f"test_dea_journal_rule_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        user, _ = User.objects.get_or_create(
            username="dea-journal-owner",
            defaults={"email": "dea-journal-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"dea-journal-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username="dea-journal-user",
            email="dea-journal-user@example.com",
            password="testpass123",
        )
        asset_type = AccountType.objects.create(
            AccountType="Asset",
            description="Asset",
            code_prefix="1",
        )
        equity_type = AccountType.objects.create(
            AccountType="Equity",
            description="Equity",
            code_prefix="3",
        )
        self.cash = Ledger.objects.create(
            AccountType=asset_type,
            name="Cash Rule Test",
            code="1.TEST.CASH.RULE",
        )
        self.capital = Ledger.objects.create(
            AccountType=equity_type,
            name="Capital Rule Test",
            code="3.TEST.CAPITAL.RULE",
        )
        self.factory = RequestFactory()
        self.period = AccountingPeriod.objects.create(
            name="Apr 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )

    def _build_manual_adjustment_doc(self):
        doc = JournalEntryVoucher.objects.create(
            je_date=date(2026, 4, 30),
            entry_type="ADJUSTMENT",
            description="Owner capital introduced",
            memo="MANUAL-PAIR",
            reference="PAIR-001",
            total_debit=Money(500, "INR"),
            total_credit=Money(500, "INR"),
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )
        JournalEntryLineItem.objects.bulk_create(
            [
                JournalEntryLineItem(
                    journal_entry=doc,
                    line_number=1,
                    ledger_id=self.cash.pk,
                    ledger_name=self.cash.name,
                    side="DR",
                    amount=Money(500, "INR"),
                    description="Cash introduced",
                ),
                JournalEntryLineItem(
                    journal_entry=doc,
                    line_number=2,
                    ledger_id=self.capital.pk,
                    ledger_name=self.capital.name,
                    side="CR",
                    amount=Money(500, "INR"),
                    description="Owner capital introduced",
                ),
            ]
        )
        return doc

    def test_rule_builds_one_dual_ledger_line_per_debit_credit_pair(self):
        doc = self._build_manual_adjustment_doc()

        bundle = JournalEntryRule().build_posting(SimpleNamespace(doc=doc))

        self.assertEqual(len(bundle.ledger_lines), 1)
        dual_line = bundle.ledger_lines[0]
        self.assertEqual(dual_line.debit_ledger_id, self.cash.pk)
        self.assertEqual(dual_line.credit_ledger_id, self.capital.pk)
        self.assertEqual(dual_line.currency, "INR")
        self.assertEqual(dual_line.amount, Decimal("500"))
        self.assertEqual(dual_line.amount_base, Decimal("500"))

    def test_create_view_explains_pair_based_entry(self):
        request = self.factory.get("/dea/journal-entry-vouchers/create/")
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = JournalEntryVoucherCreateView.as_view()(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"complete debit/credit pair", response.content.lower())

    def test_detail_view_renders_edit_link_for_saved_entry(self):
        doc = self._build_manual_adjustment_doc()

        request = self.factory.get(
            reverse("dea_journal_entry_voucher_detail", args=[doc.pk])
        )
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = JournalEntryVoucherDetailView.as_view()(request, pk=doc.pk)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            reverse("dea_journal_entry_voucher_update", args=[doc.pk]).encode(),
            response.content,
        )
        self.assertIn(b"500.00", response.content)

    def test_list_view_renders_saved_amounts(self):
        self._build_manual_adjustment_doc()

        request = self.factory.get(reverse("dea_journal_entry_voucher_list"))
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = JournalEntryVoucherListView.as_view()(request)
        response.render()

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"500.00", response.content)
        self.assertIn(b">1<", response.content)

    def test_create_view_saves_pair_rows_and_posts_voucher(self):
        request = self.factory.post(
            reverse("dea_journal_entry_voucher_create"),
            data={
                "je_date": "2026-04-30",
                "entry_type": "ADJUSTMENT",
                "description": "Owner capital introduced",
                "memo": "MANUAL-PAIR",
                "reference": "PAIR-POST-001",
                "pairs-TOTAL_FORMS": "1",
                "pairs-INITIAL_FORMS": "0",
                "pairs-MIN_NUM_FORMS": "1",
                "pairs-MAX_NUM_FORMS": "1000",
                "pairs-0-debit_ledger": str(self.cash.pk),
                "pairs-0-credit_ledger": str(self.capital.pk),
                "pairs-0-amount_0": "500.00",
                "pairs-0-amount_1": "INR",
                "pairs-0-description": "Capital introduced",
            },
        )
        request.user = self.user

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = JournalEntryVoucherCreateView.as_view()(request)

        self.assertEqual(response.status_code, 302)
        doc = JournalEntryVoucher.objects.get(reference="PAIR-POST-001")
        self.assertEqual(doc.line_items.count(), 2)
        self.assertEqual(
            list(doc.line_items.order_by("line_number", "id").values_list("side", flat=True)),
            ["DR", "CR"],
        )
        self.assertEqual(
            list(doc.line_items.order_by("line_number", "id").values_list("amount", flat=True)),
            [Decimal("500.00"), Decimal("500.00")],
        )
        self.assertEqual(doc.total_debit, Money(500, "INR"))
        self.assertEqual(doc.total_credit, Money(500, "INR"))
        voucher = Voucher.objects.get(
            doc_content_type=ContentType.objects.get_for_model(doc),
            doc_object_id=doc.pk,
            status="POSTED",
        )
        self.assertEqual(voucher.voucher_date, date(2026, 4, 30))
