import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from apps.tenancy.testing import WorkspaceTestCase

from apps.tenant_apps.loans.domain import (
    CollateralMetal,
    FeeCalculationType,
    InterestMethod,
    PartialMonthMethod,
    ValuationMethod,
)
from apps.tenant_apps.loans.services import (
    PawnEconomicPolicyError,
    create_license,
    create_pawn_economic_configuration,
    create_pawn_loan_economic_policy,
    create_pawn_loan_fee_policy,
    create_pawn_metal_interest_rate_policy,
    resolve_pawn_loan_economic_policy,
    resolve_pawn_loan_fee_policies,
    resolve_pawn_metal_interest_rate_policy,
)


class PawnEconomicPolicyServiceTests(WorkspaceTestCase):
    test_schema_name = f"loans_economics_{uuid.uuid4().hex[:8]}"
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
            username="loans-economics-owner",
            defaults={"email": "loans-economics-owner@example.com"},
        )
        tenant.name = f"Loans Economics {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username=f"economics-user-{uuid.uuid4().hex[:8]}",
            email=f"economics-user-{uuid.uuid4().hex[:8]}@example.com",
        )
        self.license = create_license(
            workspace=self.tenant,
            name="Pawn Broker License",
            license_number="PBL-ECO",
            issued_on=date(2026, 1, 1),
            expires_on=date(2028, 1, 1),
            actor=self.user,
        )

    def test_license_economic_policy_overrides_workspace_default(self):
        workspace_policy = create_pawn_loan_economic_policy(
            workspace=self.tenant,
            valuation_method=ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL,
            maximum_ltv_ratio=Decimal("0.80"),
            effective_from=date(2026, 1, 1),
            actor=self.user,
        )
        license_policy = create_pawn_loan_economic_policy(
            workspace=self.tenant,
            license=self.license,
            valuation_method=ValuationMethod.LATEST_APPRAISAL,
            maximum_ltv_ratio=Decimal("0.75"),
            advance_interest_periods=2,
            interest_method=InterestMethod.COMPOUND,
            partial_month_method=PartialMonthMethod.SLAB,
            partial_month_cutoff_days=15,
            partial_month_lower_fraction=Decimal("0.5"),
            capitalization_interval_periods=12,
            currency_quantum=Decimal("0.01"),
            effective_from=date(2026, 6, 1),
            actor=self.user,
        )

        resolved = resolve_pawn_loan_economic_policy(
            workspace_id=self.tenant.pk,
            license_id=self.license.pk,
            as_of_date=date(2026, 8, 1),
        )
        fallback = resolve_pawn_loan_economic_policy(
            workspace_id=self.tenant.pk,
            license_id=None,
            as_of_date=date(2026, 8, 1),
        )

        self.assertEqual(resolved, license_policy)
        self.assertEqual(resolved.interest_method, InterestMethod.COMPOUND.value)
        self.assertEqual(resolved.partial_month_method, PartialMonthMethod.SLAB.value)
        self.assertEqual(fallback, workspace_policy)

    def test_complete_configuration_creates_policy_and_both_rates(self):
        configuration = create_pawn_economic_configuration(
            workspace=self.tenant,
            license=self.license,
            valuation_method=ValuationMethod.LATEST_APPRAISAL,
            maximum_ltv_ratio=Decimal("0.75"),
            gold_monthly_interest_rate=Decimal("2.00"),
            silver_monthly_interest_rate=Decimal("4.00"),
            effective_from=date(2026, 8, 1),
            actor=self.user,
        )

        self.assertEqual(configuration.economic_policy.license, self.license)
        self.assertEqual(configuration.gold_rate_policy.metal, CollateralMetal.GOLD.value)
        self.assertEqual(configuration.silver_rate_policy.metal, CollateralMetal.SILVER.value)
        self.assertEqual(configuration.gold_rate_policy.effective_from, date(2026, 8, 1))
        self.assertEqual(configuration.silver_rate_policy.created_by, self.user)

    def test_complete_configuration_rolls_back_when_second_rate_is_invalid(self):
        with self.assertRaises(ValidationError):
            create_pawn_economic_configuration(
                workspace=self.tenant,
                valuation_method=ValuationMethod.LATEST_APPRAISAL,
                maximum_ltv_ratio=Decimal("0.75"),
                gold_monthly_interest_rate=Decimal("2.00"),
                silver_monthly_interest_rate=Decimal("101.00"),
                effective_from=date(2026, 8, 1),
                actor=self.user,
            )

        self.assertFalse(
            self.tenant.pawn_loan_economic_policies.filter(
                effective_from=date(2026, 8, 1)
            ).exists()
        )
        self.assertFalse(
            self.tenant.pawn_metal_interest_rate_policies.filter(
                effective_from=date(2026, 8, 1)
            ).exists()
        )

    def test_rate_resolution_is_effective_dated_and_falls_back_to_workspace(self):
        old_rate = create_pawn_metal_interest_rate_policy(
            workspace=self.tenant,
            metal=CollateralMetal.GOLD,
            monthly_interest_rate=Decimal("2"),
            effective_from=date(2026, 1, 1),
            effective_until=date(2026, 6, 30),
        )
        current_rate = create_pawn_metal_interest_rate_policy(
            workspace=self.tenant,
            metal=CollateralMetal.GOLD,
            monthly_interest_rate=Decimal("2.5"),
            effective_from=date(2026, 7, 1),
        )
        override = create_pawn_metal_interest_rate_policy(
            workspace=self.tenant,
            license=self.license,
            metal=CollateralMetal.GOLD,
            monthly_interest_rate=Decimal("1.75"),
            effective_from=date(2026, 8, 1),
        )

        june = resolve_pawn_metal_interest_rate_policy(
            workspace_id=self.tenant.pk,
            license_id=self.license.pk,
            metal=CollateralMetal.GOLD,
            as_of_date=date(2026, 6, 15),
        )
        july = resolve_pawn_metal_interest_rate_policy(
            workspace_id=self.tenant.pk,
            license_id=self.license.pk,
            metal=CollateralMetal.GOLD,
            as_of_date=date(2026, 7, 15),
        )
        august = resolve_pawn_metal_interest_rate_policy(
            workspace_id=self.tenant.pk,
            license_id=self.license.pk,
            metal=CollateralMetal.GOLD,
            as_of_date=date(2026, 8, 15),
        )

        self.assertEqual(june, old_rate)
        self.assertEqual(july, current_rate)
        self.assertEqual(august, override)

    def test_fee_resolution_merges_workspace_defaults_with_license_overrides(self):
        create_pawn_loan_fee_policy(
            workspace=self.tenant,
            code="PROCESSING",
            name="Processing fee",
            calculation_type=FeeCalculationType.FIXED,
            value=Decimal("100"),
            effective_from=date(2026, 1, 1),
        )
        create_pawn_loan_fee_policy(
            workspace=self.tenant,
            code="DOCUMENT",
            name="Document fee",
            calculation_type=FeeCalculationType.FIXED,
            value=Decimal("25"),
            effective_from=date(2026, 1, 1),
        )
        override = create_pawn_loan_fee_policy(
            workspace=self.tenant,
            license=self.license,
            code="processing",
            name="License processing fee",
            calculation_type=FeeCalculationType.PERCENTAGE,
            value=Decimal("1.5"),
            effective_from=date(2026, 7, 1),
        )

        policies = resolve_pawn_loan_fee_policies(
            workspace_id=self.tenant.pk,
            license_id=self.license.pk,
            as_of_date=date(2026, 8, 1),
        )

        self.assertEqual([policy.code for policy in policies], ["DOCUMENT", "PROCESSING"])
        self.assertEqual(policies[1], override)

    def test_missing_rate_fails_explicitly(self):
        with self.assertRaisesRegex(PawnEconomicPolicyError, "SILVER"):
            resolve_pawn_metal_interest_rate_policy(
                workspace_id=self.tenant.pk,
                license_id=self.license.pk,
                metal=CollateralMetal.SILVER,
                as_of_date=date(2026, 8, 1),
            )

    def test_invalid_percentage_fee_is_rejected(self):
        with self.assertRaises(ValidationError):
            create_pawn_loan_fee_policy(
                workspace=self.tenant,
                code="BAD",
                name="Invalid fee",
                calculation_type=FeeCalculationType.PERCENTAGE,
                value=Decimal("100.01"),
                effective_from=date(2026, 1, 1),
            )

    def test_active_tenant_boundary_is_required(self):
        with self.assertRaisesRegex(PawnEconomicPolicyError, "active workspace"):
            resolve_pawn_loan_economic_policy(
                workspace_id=self.tenant.pk + 1000,
                license_id=None,
                as_of_date=date(2026, 8, 1),
            )
