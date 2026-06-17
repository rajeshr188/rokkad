import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models import (
    GivenLoan,
    License,
    LoanItem,
    RepledgedLoanItem,
    Series,
    TakenLoan,
)
from apps.tenant_apps.girvi.services import DashboardMetricsService
from apps.tenant_apps.rates.models import Rate, RateSource


User = get_user_model()


class DashboardMetricsServiceTests(TenantTestCase):
    test_schema_name = f"girvi_dash_{uuid.uuid4().hex[:8]}"
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
            username="girvi-dashboard-owner",
            defaults={"email": "girvi-dashboard-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"girvi-dashboard-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

        self.borrower = Customer.objects.create(firstname="Borrower")
        self.lender = Customer.objects.create(firstname="Lender")
        self.license = License.objects.create(
            name="Dashboard License",
            license_number=f"DL-{uuid.uuid4().hex[:8]}",
        )
        self.given_series = Series.objects.create(
            license=self.license,
            name="G",
            prefix="G",
            max_limit=5,
            loan_type="Given",
        )
        self.taken_series = Series.objects.create(
            license=self.license,
            name="T",
            prefix="T",
            max_limit=5,
            loan_type="Taken",
        )

        source = RateSource.objects.create(name="Test", location="Local")
        for metal in ["Gold", "Silver", "Bronze"]:
            Rate.objects.create(
                rate_source=source,
                metal=metal,
                buying_rate=Decimal("100.00"),
                selling_rate=Decimal("110.00"),
            )

    def test_dashboard_metric_payloads_use_refactored_loan_models(self):
        old_date = timezone.now() - timezone.timedelta(days=70)
        given_loan = GivenLoan.objects.create(
            loan_id="G00001",
            series=self.given_series,
            borrower=self.borrower,
            loan_date=old_date,
        )
        original_item = LoanItem.objects.create(
            loan=given_loan,
            itemtype="Gold",
            quantity=1,
            weight=Decimal("1.000"),
            purity=Decimal("75.00"),
            loanamount=Decimal("1000.00"),
            interestrate=Decimal("2.00"),
            itemdesc="Ring",
        )
        taken_loan = TakenLoan.objects.create(
            loan_id="T00001",
            series=self.taken_series,
            lender=self.lender,
            original_loan=given_loan,
            loan_date=old_date,
        )
        RepledgedLoanItem.objects.create(
            loan=taken_loan,
            original_loanitem=original_item,
            repledged_loanamount=Decimal("800.00"),
            interest_rate=Decimal("1.00"),
        )

        given_stats = DashboardMetricsService.get_non_performing_loans_stats(
            GivenLoan.objects.all()
        )
        taken_stats = DashboardMetricsService.get_non_performing_loans_stats(
            TakenLoan.objects.all()
        )
        long_dead_stats = DashboardMetricsService.get_long_dead_loans_stats(
            GivenLoan.objects.all(), threshold_months=1
        )

        self.assertEqual(given_stats["count"], 1)
        self.assertEqual(taken_stats["count"], 1)
        self.assertEqual(long_dead_stats["count"], 1)
