from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase
from moneyed import Money

from apps.tenant_apps.dea.models import AccountingPeriod, AccountType, Ledger
from apps.tenant_apps.dea.models.asset import DepreciationSchedule, FixedAsset
from apps.tenant_apps.dea.services.depreciation import DepreciationService


User = get_user_model()


class DepreciationServiceTests(TenantTestCase):
    @staticmethod
    def get_test_schema_name():
        return "test_dea_depreciation"

    @classmethod
    def setup_tenant(cls, tenant):
        user = User.objects.create_user(
            username="dea-dep-owner",
            email="dea-dep-owner@example.com",
            password="testpass123",
        )
        tenant.name = "dea-dep-tenant"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.user = User.objects.create_user(
            username="dea-dep-user",
            email="dea-dep-user@example.com",
            password="testpass123",
        )

    def test_slm_depreciation_posts_and_accumulates_each_period(self):
        period1 = AccountingPeriod.objects.create(
            name="Jan 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )
        period2 = AccountingPeriod.objects.create(
            name="Feb 2026",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
        )
        period3 = AccountingPeriod.objects.create(
            name="Mar 2026",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
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

        asset_ledger = Ledger.objects.create(
            AccountType=asset_type,
            name="Office Equipment - Dep Test",
            code="1.DEP.TEST.ASSET",
        )
        acc_dep_ledger = Ledger.objects.create(
            AccountType=asset_type,
            name="Accumulated Depreciation - Dep Test",
            code="1.DEP.TEST.ACC",
        )
        dep_exp_ledger = Ledger.objects.create(
            AccountType=expense_type,
            name="Depreciation Expense - Dep Test",
            code="5.DEP.TEST.EXP",
        )

        asset = FixedAsset.objects.create(
            name="Laptop Batch",
            purchase_date=date(2025, 12, 15),
            cost=Money(1200, "INR"),
            salvage_value=Money(0, "INR"),
            useful_life_months=12,
            method="SLM",
            ledger=asset_ledger,
            acc_dep_ledger=acc_dep_ledger,
            dep_exp_ledger=dep_exp_ledger,
            created_by=self.user,
            updated_by=self.user,
            auto_post_to_accounting=False,
        )

        schedule1 = DepreciationService.post_for_period(asset, period1, user=self.user)
        schedule2 = DepreciationService.post_for_period(asset, period2, user=self.user)
        schedule3 = DepreciationService.post_for_period(asset, period3, user=self.user)

        self.assertIsNotNone(schedule1.posted_voucher)
        self.assertIsNotNone(schedule2.posted_voucher)
        self.assertIsNotNone(schedule3.posted_voucher)
        self.assertEqual(DepreciationSchedule.objects.count(), 3)

        acc_balance = acc_dep_ledger.calculate_balance("INR")
        exp_balance = dep_exp_ledger.calculate_balance("INR")

        self.assertEqual(acc_balance.amount, Decimal("-300.000"))
        self.assertEqual(exp_balance.amount, Decimal("300.000"))

        self.assertEqual(
            DepreciationService.get_unposted_for_period(period1).count(), 0
        )
