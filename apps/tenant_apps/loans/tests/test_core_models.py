import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from apps.tenancy.testing import WorkspaceTestCase

from apps.orgs.models import Company
from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
    CollateralMetal,
    InterestMethod,
    LoanDocumentKind,
    PartialMonthMethod,
    PawnLoanState,
    RoundingMethod,
    ValuationMethod,
)
from apps.tenant_apps.loans.models import (
    LoanLicense,
    LoanNumberSequence,
    LoanPolicySnapshot,
    LoanSeries,
    PawnCollateralItem,
    PawnLoan,
    PawnMetalInterestRatePolicy,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version


class LoansCoreModelTests(WorkspaceTestCase):
    test_schema_name = f"loans_core_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="loans-core-owner",
            defaults={"email": "loans-core-owner@example.com"},
        )
        tenant.name = f"Loans Core {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.user = User.objects.create_user(
            username=f"loans-owner-{uuid.uuid4().hex[:8]}",
            email=f"loans-owner-{uuid.uuid4().hex[:8]}@example.com",
            password="pass",
        )
        self.workspace_a = self.tenant
        self.workspace_b = self._create_workspace(
            f"Loans Workspace B {uuid.uuid4().hex[:8]}",
            f"loans_b_{uuid.uuid4().hex[:8]}",
        )
        self.party = Party.objects.create(
            party_code=f"P-{uuid.uuid4().hex[:8]}",
            display_name="Pawn Borrower",
        )
        self.license_a = LoanLicense.objects.create(
            workspace=self.workspace_a,
            name="Pawn License A",
            license_number=f"PBL-A-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.user,
        )
        self.license_b = LoanLicense.objects.create(
            workspace=self.workspace_a,
            name="Pawn License B",
            license_number=f"PBL-B-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.user,
        )
        self.series_a = LoanSeries.objects.create(
            license=self.license_a,
            name="Main",
            code="A",
        )
        self.series_b = LoanSeries.objects.create(
            license=self.license_b,
            name="Main",
            code="B",
        )
        self.product_version = ensure_test_product_version(self.workspace_a)

    def _create_workspace(self, name, schema_name):
        workspace = Company(
            name=name,
            schema_name=schema_name,
            owner=self.user,
            creator=self.user,
        )
        workspace.auto_create_schema = False
        workspace.save()
        return workspace

    def build_loan(self, **overrides):
        values = {
            "workspace": self.workspace_a,
            "license": self.license_a,
            "series": self.series_a,
            "borrower": self.party,
            "product_version": self.product_version,
            "loan_number": "A00001",
            "state": PawnLoanState.DRAFT.value,
            "principal_amount": Decimal("10000.00"),
            "monthly_interest_rate": Decimal("2.000000"),
            "tenure_months": 3,
            "created_by": self.user,
        }
        values.update(overrides)
        return PawnLoan(**values)

    def test_workspace_can_have_multiple_active_licenses(self):
        second = LoanLicense.objects.create(
            workspace=self.workspace_a,
            name="Second Pawn License",
            license_number="PBL-A-2",
            issued_on=date(2026, 2, 1),
            expires_on=date(2027, 2, 1),
        )

        self.assertTrue(self.license_a.is_active)
        self.assertTrue(second.is_active)

    def test_license_number_is_unique_inside_workspace(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            LoanLicense.objects.create(
                workspace=self.workspace_a,
                name="Duplicate",
                license_number=self.license_a.license_number,
                issued_on=date(2026, 1, 1),
                expires_on=date(2027, 1, 1),
            )

    def test_license_rejects_another_workspace_inside_active_tenant(self):
        license_other_workspace = LoanLicense(
            workspace=self.workspace_b,
            name="Workspace-local Number",
            license_number=self.license_a.license_number,
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )

        with self.assertRaises(ValidationError) as error:
            license_other_workspace.save()

        self.assertIn("workspace", error.exception.message_dict)

    def test_license_rejects_expiry_before_issue_date(self):
        license_record = LoanLicense(
            workspace=self.workspace_a,
            name="Invalid Dates",
            license_number="INVALID-DATE",
            issued_on=date(2027, 1, 1),
            expires_on=date(2026, 1, 1),
        )

        with self.assertRaises(ValidationError):
            license_record.full_clean()

    def test_sequence_is_unique_per_series_and_document_kind(self):
        LoanNumberSequence.objects.create(
            series=self.series_a,
            document_kind=LoanDocumentKind.PAWN_LOAN.value,
            prefix="A",
        )

        with self.assertRaises(IntegrityError), transaction.atomic():
            LoanNumberSequence.objects.create(
                series=self.series_a,
                document_kind=LoanDocumentKind.PAWN_LOAN.value,
                prefix="OTHER",
            )

    def test_sequence_rejects_next_number_beyond_exhausted_marker(self):
        sequence = LoanNumberSequence(
            series=self.series_a,
            document_kind=LoanDocumentKind.PAWN_LOAN.value,
            prefix="A",
            next_number=102,
            maximum_number=100,
        )

        with self.assertRaises(ValidationError):
            sequence.full_clean()

    def test_pawn_loan_rejects_license_from_another_workspace(self):
        loan = self.build_loan(
            workspace=self.workspace_b,
            license=self.license_a,
            series=self.series_a,
        )

        with self.assertRaises(ValidationError) as error:
            loan.save()

        self.assertIn("license", error.exception.message_dict)

    def test_pawn_loan_rejects_series_from_another_license(self):
        loan = self.build_loan(series=self.series_b)

        with self.assertRaises(ValidationError) as error:
            loan.save()

        self.assertIn("series", error.exception.message_dict)

    def test_valid_core_aggregate_and_policy_snapshot(self):
        loan = self.build_loan()
        loan.full_clean()
        loan.save()
        collateral = PawnCollateralItem(
            loan=loan,
            description="Gold chain",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10.0000"),
            net_weight=Decimal("9.5000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("60000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        collateral.full_clean()
        collateral.save()
        snapshot = LoanPolicySnapshot(
            loan=loan,
            interest_method=InterestMethod.SIMPLE.value,
            partial_month_method=PartialMonthMethod.FULL_MONTH.value,
            partial_month_cutoff_days=15,
            partial_month_lower_fraction=Decimal("0.5000"),
            capitalization_interval_periods=12,
            valuation_method=ValuationMethod.CALCULATED_METAL_VALUE.value,
            maximum_ltv_ratio=Decimal("0.8000"),
            rounding_method=RoundingMethod.PER_ACCRUAL_PERIOD.value,
            currency_quantum=Decimal("0.0100"),
        )
        snapshot.full_clean()
        snapshot.save()

        self.assertEqual(loan.collateral_items.get(), collateral)
        self.assertEqual(loan.policy_snapshot, snapshot)

    def test_collateral_constraints_fail_closed(self):
        loan = self.build_loan()
        loan.save()
        item = PawnCollateralItem(
            loan=loan,
            description="Invalid item",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("5.0000"),
            net_weight=Decimal("6.0000"),
            purity_percentage=Decimal("101.0000"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )

        with self.assertRaises(ValidationError):
            item.full_clean()

    def test_collateral_rate_policy_must_match_metal_and_license(self):
        loan = self.build_loan()
        loan.save()
        wrong_license_rate = PawnMetalInterestRatePolicy.objects.create(
            workspace=self.workspace_a,
            license=self.license_b,
            metal=CollateralMetal.GOLD.value,
            monthly_interest_rate=Decimal("2.000000"),
            effective_from=date(2026, 1, 1),
        )
        item = PawnCollateralItem(
            loan=loan,
            description="Gold ring",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("2.0000"),
            net_weight=Decimal("1.9000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("7000.00"),
            allocated_principal=Decimal("5000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            interest_rate_policy=wrong_license_rate,
        )

        with self.assertRaises(ValidationError) as error:
            item.full_clean()

        self.assertIn("interest_rate_policy", error.exception.message_dict)
