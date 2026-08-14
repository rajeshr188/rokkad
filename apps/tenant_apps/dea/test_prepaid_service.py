from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.dea.models import AccountingPeriod, AccountType, Ledger
from apps.tenant_apps.dea.models.prepaid import PrepaidExpense, PrepaidScheduleLine
from apps.tenant_apps.dea.services.prepaid import PrepaidService


User = get_user_model()


class PrepaidServiceTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_dea_prepaid"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="dea-prepaid-owner",
            email="dea-prepaid-owner@example.com",
            password="testpass123",
        )
        tenant.name = "dea-prepaid-tenant"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username="dea-prepaid-user",
            email="dea-prepaid-user@example.com",
            password="testpass123",
        )

    def test_monthly_prepaid_amortization_posts_and_reduces_asset(self):
        period = AccountingPeriod.objects.create(
            name="Jan 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        asset_type = AccountType.objects.create(
            AccountType="Asset",
            description="Asset",
            code_prefix="1",
        )
        expense_type = AccountType.objects.create(
            AccountType="Expense",
            description="Expense",
            code_prefix="5",
        )

        prepaid_ledger = Ledger.objects.create(
            AccountType=asset_type,
            name="Prepaid Insurance - Test",
            code="1.PREPAID.TEST",
        )
        expense_ledger = Ledger.objects.create(
            AccountType=expense_type,
            name="Insurance Expense - Test",
            code="5.PREPAID.TEST",
        )

        prepaid = PrepaidExpense.objects.create(
            name="Annual Insurance",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            total_amount=Money(1200, "INR"),
            prepaid_ledger=prepaid_ledger,
            expense_ledger=expense_ledger,
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )

        schedule_line = PrepaidService.post_for_period(prepaid, period, user=self.user)

        self.assertIsNotNone(schedule_line.posted_voucher)
        self.assertEqual(PrepaidScheduleLine.objects.count(), 1)
        self.assertEqual(schedule_line.amount.amount, Decimal("100.00"))
        self.assertEqual(prepaid_ledger.calculate_balance("INR").amount, Decimal("-100.000"))
        self.assertEqual(expense_ledger.calculate_balance("INR").amount, Decimal("100.000"))
        self.assertEqual(PrepaidService.get_unposted_for_period(period).count(), 0)
