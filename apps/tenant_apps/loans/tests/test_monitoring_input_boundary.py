"""Current observations are not original approvals or financial support."""
from dataclasses import replace
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.db import connection
from django.forms.models import model_to_dict
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

from apps.orgs.models import Company
from apps.tenancy.context import without_workspace_context, workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.integrations import disbursal_payload
from apps.tenant_apps.loans.selectors.collateral_valuation import (
    get_pawn_loan_collateral_observation, get_pawn_loan_collateral_valuation,
)
from apps.tenant_apps.loans.selectors.monitoring_inputs import resolve_monitoring_valuation_inputs
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio_summary
from apps.tenant_apps.loans.services.event_recording import record_loan_event
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot, RiskSnapshotRefreshError
from apps.tenant_apps.rates.models import Rate
from . import test_collateral_reappraisal as fixtures
from . import test_monitoring_valuation_basis as valuations


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MonitoringInputBoundaryTests(WorkspaceTestCase):
    get_test_schema_name = classmethod(lambda cls: "monitoring-input-boundary")
    setup_tenant = classmethod(valuations.MonitoringValuationTests.setup_tenant.__func__)
    data = valuations.MonitoringValuationTests.data
    amend = valuations.MonitoringValuationTests.amend

    def setUp(self):
        fixtures.CollateralReappraisalTests.make_loan(self)
        self.quote = Rate.objects.create(rate_source=self.source, buying_rate="3000.127", selling_rate="3100")

    def legacy_loan(self):
        loan = m.PawnLoan.objects.create(workspace=self.tenant, license=self.loan.license,
            series=self.loan.series, borrower=self.loan.borrower, product_version=self.loan.product_version,
            loan_number="LEGACY-OBS", loan_date=self.loan.loan_date, tenure_months=12,
            principal_amount=1000, monthly_interest_rate=2, state="ACTIVE")
        record_loan_event(loan.pk, actor=self.actor, event_kind="DISBURSAL", effective_date=loan.loan_date,
            payload=disbursal_payload(loan, effective_date=loan.loan_date, principal_amount=1000,
                net_cash_amount=1000, advance_interest_amount=0, deducted_fee_amount=0).to_dict())
        item = m.PawnCollateralItem.objects.create(loan=loan, description="Recorded legacy gold ring",
            metal="GOLD", gross_weight=1, net_weight=1, purity_percentage=100, custody_state="IN_VAULT")
        return loan, item

    def test_all_methods_keep_saved_precision_limits_and_frozen_evidence(self):
        frozen = (model_to_dict(self.loan.policy_snapshot), list(self.loan.approval_snapshots.values()),
            list(self.loan.loan_events.values()), list(self.loan.repayment_schedules.values()))
        fixtures.CollateralReappraisalTests.reassess(self, appraised_value="2500")
        for method, expected in (("CALCULATED_METAL_VALUE", Decimal("3000.13")),
                ("LATEST_APPRAISAL", Decimal("2500")), ("LOWER_OF_CALCULATED_AND_APPRAISAL", Decimal("2500"))):
            with self.subTest(method=method):
                self.amend(valuation_basis=method)
                with CaptureQueriesContext(connection) as reads:
                    observed = get_pawn_loan_collateral_observation(self.loan.pk, as_of_date=self.today)
                self.assertFalse(any(q["sql"].lstrip().upper().startswith(("INSERT ", "UPDATE ", "DELETE ")) for q in reads))
                self.assertEqual(observed.eligible_collateral_value, expected)
                self.assertEqual(observed.inputs.reference_ltv_ratio, Decimal(".8"))
                self.assertEqual(observed.inputs.precision_source, "SAVED_AGREEMENT")
                self.assertEqual(observed.inputs.saved_method, "LOWER_OF_CALCULATED_AND_APPRAISAL")
        self.assertEqual(frozen, (model_to_dict(self.loan.policy_snapshot), list(self.loan.approval_snapshots.values()),
            list(self.loan.loan_events.values()), list(self.loan.repayment_schedules.values())))

    def test_current_metal_observation_needs_no_historical_policy_or_approval(self):
        loan, _item = self.legacy_loan()
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        with patch("apps.tenant_apps.loans.selectors.collateral_valuation.get_pawn_loan_exposure",
                   side_effect=ValueError("Financial projection unavailable")) as debt:
            observed = get_pawn_loan_collateral_observation(loan.pk, as_of_date=self.today)
            debt.assert_not_called()
            self.assertEqual(observed.eligible_collateral_value, Decimal("3000.13"))
            self.assertEqual(observed.inputs.precision_source, "MONITORING_PAISE_DEFAULT")
            self.assertEqual(observed.inputs.saved_method, "")
            self.assertIsNone(observed.inputs.reference_ltv_ratio)
            with self.assertRaisesMessage(ValueError, "Financial projection unavailable"):
                get_pawn_loan_collateral_valuation(loan.pk, as_of_date=self.today)
        self.assertFalse(loan.approval_snapshots.exists())
        self.assertIsNone(loan.policy_snapshot_id)
        with self.assertRaises(RiskSnapshotRefreshError):
            refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today)
        self.assertEqual(m.LoanRiskSnapshot.objects.get(loan=loan).status, "ERROR")

    def test_preserve_unknown_saved_method_does_not_silently_choose_metal(self):
        loan, _item = self.legacy_loan()
        observed = get_pawn_loan_collateral_observation(loan.pk, as_of_date=self.today)
        self.assertIsNone(observed.eligible_collateral_value)
        self.assertIsNone(observed.inputs.method)
        self.assertIn("SAVED_VALUATION_METHOD_UNAVAILABLE", observed.items[0].blockers)

    def test_current_appraisal_and_lower_of_observe_legacy_items_without_original_decision(self):
        from apps.tenant_apps.loans.services.collateral_reappraisal import record_collateral_reappraisal
        loan, item = self.legacy_loan()
        record_collateral_reappraisal(loan_id=loan.pk, item_id=item.pk, actor=self.actor,
            appraised_value="2500", method="PHYSICAL_INSPECTION", evidence_reference="Current inspection",
            review_notes="Fictional legacy item physically checked", expected_version=0)
        for method in ("LATEST_APPRAISAL", "LOWER_OF_CALCULATED_AND_APPRAISAL"):
            with self.subTest(method=method):
                self.amend(valuation_basis=method)
                observed = get_pawn_loan_collateral_observation(loan.pk, as_of_date=self.today)
                self.assertEqual(observed.eligible_collateral_value, Decimal("2500"))
                self.assertIsNone(observed.inputs.reference_ltv_ratio)
                self.assertEqual(observed.inputs.saved_method, "")
        self.assertFalse(loan.approval_snapshots.exists())

    def test_compatibility_precision_preserves_whole_rupees_without_altering_snapshot(self):
        # Reader-level legacy storage projection: no policy row is edited.
        self.loan.policy_snapshot.currency_quantum = Decimal("1.0000")
        inputs = resolve_monitoring_valuation_inputs(self.loan, as_of_date=self.today)
        self.assertEqual(inputs.currency_quantum, Decimal("1"))
        self.assertEqual(inputs.precision_source, "SAVED_AGREEMENT")
        self.loan.policy_snapshot.refresh_from_db()
        self.assertEqual(self.loan.policy_snapshot.currency_quantum, Decimal(".01"))

    def test_current_thresholds_are_distinct_from_saved_reference_limit(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE", ltv_warning_ratio=Decimal(".1"),
            ltv_breach_ratio=Decimal(".2"), ltv_critical_ratio=Decimal(".3"))
        snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        row = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today)
        self.assertEqual(row.ltv.allowed_ltv_ratio, Decimal(".8"))
        self.assertEqual(row.ltv.headroom, row.eligible_collateral_value * Decimal(".8") - row.ltv.exposure)
        self.assertIn("LTV_CRITICAL", snapshot.flags)
        provenance = snapshot.source_provenance["valuation"]
        self.assertEqual(Decimal(provenance["reference_ltv_ratio"]), Decimal(".8"))
        self.assertEqual(provenance["reference_limit_source"], "SAVED_LENDING_REFERENCE")
        self.assertEqual(provenance["precision_source"], "SAVED_AGREEMENT")
        self.assertEqual(Decimal(provenance["currency_quantum"]), Decimal(".01"))
        snapshot.source_provenance["calculation_contract"] = "LOAN_RISK_SNAPSHOT_V10"
        snapshot.save(update_fields=["source_provenance"])
        self.assertEqual(get_risk_portfolio_summary().stale_count, 1)

    def test_bad_financial_evidence_does_not_erase_observation_or_supply_usable_ltv(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        bad = replace(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today),
            integrity_findings=("Unreconciled recorded position",))
        observed = get_pawn_loan_collateral_observation(self.loan.pk, as_of_date=self.today)
        row = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today, _exposure=bad)
        self.assertEqual(row.eligible_collateral_value, observed.eligible_collateral_value)
        self.assertIsNone(row.ltv.ltv_ratio)
        self.assertIn("FINANCIAL_EVIDENCE_INCONSISTENT", row.ltv.blockers)

    def test_observation_and_resolver_preserve_workspace_isolation_under_restricted_role(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        with without_workspace_context():
            other = Company.objects.create(name="Other observation", schema_name=uuid4().hex,
                owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("monitoring_input_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            self.assertIsNotNone(get_pawn_loan_collateral_observation(self.loan.pk, as_of_date=self.today).eligible_collateral_value)
            with without_workspace_context(), workspace_context(other.pk):
                with self.assertRaises(m.PawnLoan.DoesNotExist):
                    get_pawn_loan_collateral_observation(self.loan.pk, as_of_date=self.today)
                with self.assertRaisesMessage(ValueError, "Workspace"):
                    resolve_monitoring_valuation_inputs(self.loan, as_of_date=self.today)
            with without_workspace_context(), self.assertRaisesMessage(ValueError, "Workspace"):
                get_pawn_loan_collateral_observation(self.loan.pk, as_of_date=self.today)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
