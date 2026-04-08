from datetime import date, datetime, time

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.db import connection
from django.test import RequestFactory
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.contact.models import Customer

from .models import (
    AccountStatement,
    AccountingPeriod,
    AccountType,
    JournalEntry,
    JournalEntryVoucher,
    Ledger,
    LedgerTransaction,
    Voucher,
    VoucherStatus,
    VoucherType,
)
from .views.period import period_adjustments, period_close


User = get_user_model()


class AccountingPeriodCloseTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_dea_period_close"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="dea-period-owner",
            email="dea-period-owner@example.com",
            password="testpass123",
        )
        tenant.name = "dea-period-tenant"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username="dea-period-user",
            email="dea-period-user@example.com",
            password="testpass123",
        )

    def test_period_close_view_redirects_after_successful_close(self):
        period = AccountingPeriod.objects.create(
            name="Apr 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
        )
        factory = RequestFactory()
        request = factory.post(
            f"/dea/period/{period.pk}/close/",
            data={
                "review_adjustments": "on",
                "review_unposted_items": "on",
                "review_carry_forward": "on",
                "confirm": "on",
            },
        )
        request.user = self.user
        request.htmx = False

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = period_close(request, period.pk)

        self.assertEqual(response.status_code, 302)

    def test_closed_period_view_shows_already_closed_message(self):
        period = AccountingPeriod.objects.create(
            name="Closed Apr 2026",
            start_date=date(2026, 4, 1),
            end_date=date(2026, 4, 30),
            status=AccountingPeriod.PeriodStatus.CLOSED,
        )
        factory = RequestFactory()
        request = factory.get(f"/dea/period/{period.pk}/close/")
        request.user = self.user
        request.htmx = False

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = period_close(request, period.pk)

        self.assertEqual(response.status_code, 302)
        messages = [message.message for message in get_messages(request)]
        self.assertIn("already closed", messages[0].lower())

    def test_period_adjustment_view_posts_manual_adjustment(self):
        period = AccountingPeriod.objects.create(
            name="Jun 2026",
            start_date=date(2026, 6, 1),
            end_date=date(2026, 6, 30),
        )
        expense_type = AccountType.objects.create(
            AccountType="Expense",
            description="Expense",
            code_prefix="5",
        )
        liability_type = AccountType.objects.create(
            AccountType="Liability",
            description="Liability",
            code_prefix="2",
        )
        interest_expense = Ledger.objects.create(
            AccountType=expense_type,
            name="Interest Expense-Test",
            code="5.TEST.INTEREST",
        )
        interest_payable = Ledger.objects.create(
            AccountType=liability_type,
            name="Interest Payable-Test",
            code="2.TEST.INTEREST",
        )

        factory = RequestFactory()

        get_request = factory.get(f"/dea/period/{period.pk}/adjustments/")
        get_request.user = self.user
        get_request.htmx = False
        get_session_middleware = SessionMiddleware(lambda req: None)
        get_session_middleware.process_request(get_request)
        get_request.session.save()
        setattr(get_request, "_messages", FallbackStorage(get_request))

        get_response = period_adjustments(get_request, period.pk)
        get_response.render()
        self.assertEqual(get_response.status_code, 200)

        request = factory.post(
            f"/dea/period/{period.pk}/adjustments/",
            data={
                "adjustment_type": "INTEREST_ACCRUAL",
                "effective_date": period.end_date.isoformat(),
                "debit_ledger": interest_expense.pk,
                "credit_ledger": interest_payable.pk,
                "amount_0": "250.00",
                "amount_1": "INR",
                "description": "Accrue month-end interest",
                "auto_reverse_next_period": "on",
            },
        )
        request.user = self.user
        request.htmx = False

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = period_adjustments(request, period.pk)

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            JournalEntryVoucher.objects.filter(
                reference=f"PERIOD:{period.pk}",
                memo="PRE_CLOSE:INTEREST_ACCRUAL",
            ).exists()
        )
        posted_entry = period.journal_entries.get(desc__icontains="Accrue month-end interest")
        self.assertEqual(posted_entry.voucher.status, VoucherStatus.POSTED)

    def test_period_close_blocks_when_draft_vouchers_exist(self):
        period = AccountingPeriod.objects.create(
            name="Jul 2026",
            start_date=date(2026, 7, 1),
            end_date=date(2026, 7, 31),
        )
        voucher_type = VoucherType.objects.create(
            name="DRAFT-PERIOD-CLOSE",
            description="Draft close guard",
        )
        draft_voucher = Voucher.objects.create(
            voucher_no="DRAFT-PERIOD-1",
            voucher_type=voucher_type,
            voucher_date=period.end_date,
            status=VoucherStatus.DRAFT,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(type(period)),
            doc_object_id=period.pk,
            fingerprint="draft-period-close",
        )
        JournalEntry.objects.create(
            voucher=draft_voucher,
            period=period,
            posted_by=self.user,
            desc="Draft period entry",
        )

        factory = RequestFactory()
        request = factory.post(
            f"/dea/period/{period.pk}/close/",
            data={
                "review_adjustments": "on",
                "review_unposted_items": "on",
                "review_carry_forward": "on",
                "confirm": "on",
            },
        )
        request.user = self.user
        request.htmx = False

        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()
        setattr(request, "_messages", FallbackStorage(request))

        response = period_close(request, period.pk)
        response.render()
        period.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(period.status, AccountingPeriod.PeriodStatus.OPEN)
        self.assertIn(b"draft voucher", response.content.lower())

    def test_close_period_bootstraps_retained_earnings_for_income_balance(self):
        period = AccountingPeriod.objects.create(
            name="May 2026",
            start_date=date(2026, 5, 1),
            end_date=date(2026, 5, 31),
        )
        asset_type = AccountType.objects.create(
            AccountType="Asset",
            description="Asset",
            code_prefix="1",
        )
        income_type = AccountType.objects.create(
            AccountType="Income",
            description="Income",
            code_prefix="4",
        )

        cash = Ledger.objects.create(
            AccountType=asset_type,
            name="Cash-Test",
            code="1.TEST.CASH",
        )
        sales = Ledger.objects.create(
            AccountType=income_type,
            name="Sales-Test",
            code="4.TEST.SALES",
        )

        Ledger.objects.filter(name="Retained Earnings").delete()
        self.assertFalse(Ledger.objects.filter(name="Retained Earnings").exists())

        customer = Customer.objects.create(firstname="Account Holder")
        account = customer.account

        voucher_type = VoucherType.objects.create(name="TEST_PERIOD", description="Test")
        voucher = Voucher.objects.create(
            voucher_no="TEST-PERIOD-1",
            voucher_type=voucher_type,
            voucher_date=period.start_date,
            created_by=self.user,
            updated_by=self.user,
            doc_content_type=ContentType.objects.get_for_model(type(period)),
            doc_object_id=period.pk,
            fingerprint="test-period-balance",
        )
        journal_entry = JournalEntry.objects.create(
            voucher=voucher,
            period=period,
            posted_by=self.user,
            desc="Income during period",
        )
        seed_txn = LedgerTransaction.objects.create(
            journal_entry=journal_entry,
            ledgerno=sales,
            ledgerno_dr=cash,
            amount=Money(100, "INR"),
        )
        aware_created = timezone.make_aware(datetime.combine(period.start_date, time(12, 0)))
        LedgerTransaction.objects.filter(pk=seed_txn.pk).update(created=aware_created)

        period.close_period(user=self.user, notes="Income close")
        period.refresh_from_db()
        retained_earnings = Ledger.objects.get(name="Retained Earnings")

        self.assertEqual(period.status, AccountingPeriod.PeriodStatus.CLOSED)
        self.assertIsNotNone(period.closing_journal_entry)
        self.assertEqual(period.closing_journal_entry.period, period)
        self.assertEqual(period.closing_journal_entry.voucher.status, "POSTED")
        self.assertTrue(
            period.closing_journal_entry.ltxns.filter(
                ledgerno=retained_earnings,
                ledgerno_dr=sales,
            ).exists()
        )

        account_statement = AccountStatement.objects.get(AccountNo=account, period=period)
        self.assertEqual(account_statement.TotalCredit, Money(0, "INR"))
        self.assertEqual(account_statement.TotalDebit, Money(0, "INR"))
