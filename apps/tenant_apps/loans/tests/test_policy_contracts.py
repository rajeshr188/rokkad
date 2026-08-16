from dataclasses import FrozenInstanceError
from decimal import Decimal

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import (
    DisbursalPolicySnapshot,
    InterestMethod,
    LicensePolicyOverrides,
    PartialMonthMethod,
    RoundingMethod,
    ValuationMethod,
    WorkspacePolicyDefaults,
    resolve_policy,
)


class LoanPolicyContractTests(SimpleTestCase):
    def test_workspace_defaults_match_accepted_architecture(self):
        policy = resolve_policy()

        self.assertEqual(policy.interest_method, InterestMethod.SIMPLE)
        self.assertEqual(policy.partial_month_method, PartialMonthMethod.FULL_MONTH)
        self.assertEqual(policy.capitalization_interval_periods, 12)
        self.assertEqual(policy.maximum_ltv_ratio, Decimal("0.80"))
        self.assertEqual(policy.rounding_method, RoundingMethod.PER_ACCRUAL_PERIOD)

    def test_license_values_override_workspace_defaults_only_when_present(self):
        workspace = WorkspacePolicyDefaults(
            interest_method=InterestMethod.SIMPLE,
            partial_month_method=PartialMonthMethod.FULL_MONTH,
            valuation_method=ValuationMethod.CALCULATED_METAL_VALUE,
        )
        license_overrides = LicensePolicyOverrides(
            interest_method=InterestMethod.COMPOUND,
            partial_month_method=PartialMonthMethod.SLAB,
            valuation_method=ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL,
            maximum_ltv_ratio=Decimal("0.75"),
        )

        policy = resolve_policy(workspace, license_overrides)

        self.assertEqual(policy.interest_method, InterestMethod.COMPOUND)
        self.assertEqual(policy.partial_month_method, PartialMonthMethod.SLAB)
        self.assertEqual(
            policy.valuation_method,
            ValuationMethod.LOWER_OF_CALCULATED_AND_APPRAISAL,
        )
        self.assertEqual(policy.maximum_ltv_ratio, Decimal("0.75"))

    def test_invalid_policy_values_fail_closed(self):
        invalid_values = (
            {"partial_month_cutoff_days": 0},
            {"partial_month_lower_fraction": Decimal("0")},
            {"capitalization_interval_periods": 0},
            {"maximum_ltv_ratio": Decimal("1.01")},
            {"currency_quantum": Decimal("0")},
        )

        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(ValueError):
                WorkspacePolicyDefaults(**values)

    def test_snapshot_is_immutable_and_round_trips_deterministically(self):
        snapshot = resolve_policy(
            license_overrides=LicensePolicyOverrides(
                interest_method=InterestMethod.COMPOUND,
                maximum_ltv_ratio=Decimal("0.70"),
            )
        ).to_disbursal_snapshot()

        payload = snapshot.to_dict()

        self.assertEqual(DisbursalPolicySnapshot.from_dict(payload), snapshot)
        self.assertEqual(payload["maximum_ltv_ratio"], "0.70")
        self.assertEqual(payload["policy_version"], 1)
        with self.assertRaises(FrozenInstanceError):
            snapshot.maximum_ltv_ratio = Decimal("0.80")

    def test_snapshot_rejects_unknown_or_invalid_serialized_values(self):
        payload = resolve_policy().to_disbursal_snapshot().to_dict()
        payload["interest_method"] = "UNKNOWN"

        with self.assertRaises(ValueError):
            DisbursalPolicySnapshot.from_dict(payload)
