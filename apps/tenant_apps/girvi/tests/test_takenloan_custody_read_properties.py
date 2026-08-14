import uuid
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.girvi.models import (
    GivenLoan,
    License,
    LoanItem,
    RepledgeHistory,
    Series,
    TakenLoan,
)
from apps.tenant_apps.girvi.selectors import get_loan_totals


User = get_user_model()


class TakenLoanCustodyReadPropertyTests(TenantTestCase):
    test_schema_name = f"taken_custody_{uuid.uuid4().hex[:8]}"
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
            username="taken-custody-owner",
            defaults={"email": "taken-custody-owner@example.com"},
        )
        user.set_password("testpass123")
        user.save(update_fields=["password"])
        tenant.name = f"taken-custody-tenant-{uuid.uuid4().hex[:8]}"
        tenant.owner = user
        tenant.creator = user

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)

        borrower = Customer.objects.create(firstname="Borrower")
        lender = Customer.objects.create(firstname="Lender")
        license_obj = License.objects.create(
            name="Custody Read License",
            license_number=f"CR-{uuid.uuid4().hex[:8]}",
        )
        given_series = Series.objects.create(
            license=license_obj,
            name="G",
            prefix="G",
            max_limit=5,
            loan_type="Given",
        )
        taken_series = Series.objects.create(
            license=license_obj,
            name="T",
            prefix="T",
            max_limit=5,
            loan_type="Taken",
        )
        self.given_loan = GivenLoan.objects.create(
            loan_id="G-CUST-1",
            series=given_series,
            borrower=borrower,
        )
        self.item = LoanItem.objects.create(
            loan=self.given_loan,
            itemtype="Gold",
            quantity=1,
            weight=Decimal("10.000"),
            purity=Decimal("75.00"),
            loanamount=Decimal("1000.00"),
            interestrate=Decimal("2.00"),
            itemdesc="Ring",
        )
        self.taken_loan = TakenLoan.objects.create(
            loan_id="T-CUST-1",
            series=taken_series,
            lender=lender,
            original_loan=self.given_loan,
        )
        RepledgeHistory.objects.create(
            loan_item=self.item,
            taken_loan=self.taken_loan,
            repledged_amount=Decimal("800.00"),
            item_value_at_repledge=Decimal("1200.00"),
        )

    def test_taken_loan_direct_read_properties_use_custody_history(self):
        self.assertEqual(self.taken_loan.get_loan_amount, Decimal("800.00"))
        self.assertEqual(self.taken_loan.get_interest_amount, Decimal("16"))
        self.assertEqual(self.taken_loan.get_item_description, "Ring")

        weight_summary = list(self.taken_loan.get_weight_summary)

        self.assertEqual(
            weight_summary,
            [
                {
                    "itemtype": "Gold",
                    "total_weight": Decimal("10.000"),
                    "pure_weight": Decimal("7.5"),
                }
            ],
        )

    def test_taken_loan_current_value_uses_custody_history_items(self):
        with patch(
            "apps.tenant_apps.girvi.services.RateCacheService.get_rate",
            return_value=Decimal("100.00"),
        ):
            self.assertEqual(self.taken_loan.current_value, Decimal("750.00"))

    def test_taken_loan_queryset_principal_aggregations_use_custody_history(self):
        self.assertEqual(TakenLoan.objects.all().total_loan_amount(), Decimal("800.00"))

        annotated_loan = TakenLoan.objects.get_queryset().with_itemwise_amounts().get(
            pk=self.taken_loan.pk
        )
        totals = get_loan_totals(taken_qs=TakenLoan.objects.all())

        self.assertEqual(annotated_loan.gold_loanamount, Decimal("800.00"))
        self.assertEqual(annotated_loan.silver_loanamount, Decimal("0.00"))
        self.assertEqual(annotated_loan.bronze_loanamount, Decimal("0.00"))
        self.assertEqual(totals["total_loan_amount"]["total"], Decimal("800.00"))
        self.assertEqual(totals["total_interest"]["total"], Decimal("16"))

    def test_taken_loan_interest_annotations_use_custody_history(self):
        annotated_loan = (
            TakenLoan.objects.get_queryset()
            .with_duration_metrics()
            .with_interest_metrics()
            .get(pk=self.taken_loan.pk)
        )

        self.assertEqual(annotated_loan.calculated_loan_amount, Decimal("800.00"))
        self.assertEqual(annotated_loan.calculated_interest_amount, Decimal("16"))
        self.assertEqual(annotated_loan.calculated_total_due, Decimal("800.00"))
        self.assertEqual(self.taken_loan.total_due, Decimal("800.00"))

    def test_given_loan_interest_metrics_do_not_shadow_total_due_property(self):
        annotated_loan = (
            GivenLoan.objects.get_queryset()
            .with_duration_metrics()
            .with_interest_metrics()
            .get(pk=self.given_loan.pk)
        )

        self.assertEqual(annotated_loan.calculated_loan_amount, Decimal("1000.00"))
        self.assertEqual(annotated_loan.calculated_interest_amount, Decimal("20"))
        self.assertEqual(annotated_loan.calculated_total_due, Decimal("1000.00"))
        self.assertEqual(annotated_loan.total_due, Decimal("1000.00"))

    def test_taken_loan_queryset_weight_and_value_annotations_use_custody_history(self):
        with patch(
            "apps.tenant_apps.girvi.services.RateCacheService.get_all_rates",
            return_value={
                "Gold": Decimal("100.00"),
                "Silver": Decimal("80.00"),
                "Bronze": Decimal("50.00"),
            },
        ):
            annotated_loan = (
                TakenLoan.objects.get_queryset()
                .with_metal_weights()
                .with_current_value()
                .get(pk=self.taken_loan.pk)
            )

        self.assertEqual(annotated_loan.gold_weight, Decimal("10.000"))
        self.assertEqual(annotated_loan.silver_weight, Decimal("0.000"))
        self.assertEqual(annotated_loan.bronze_weight, Decimal("0.000"))
        self.assertEqual(annotated_loan.pure_gold_weight, Decimal("7.5"))
        self.assertEqual(annotated_loan.gold_value, Decimal("750"))
        self.assertEqual(annotated_loan.total_current_value, Decimal("750"))
