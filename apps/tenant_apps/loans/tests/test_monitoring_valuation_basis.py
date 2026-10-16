"""Current valuation decisions never rewrite the original lending contract."""
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.forms.models import model_to_dict
from django.test import RequestFactory, TransactionTestCase, override_settings
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import WorkspaceTestCase, historical_migration_database
from apps.tenant_apps.loans.models import LoanMonitoringPolicy, LoanRiskSnapshot
from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
from apps.tenant_apps.loans.selectors.delinquency import get_pawn_loan_delinquency
from apps.tenant_apps.loans.selectors.risk_portfolio import SNAPSHOT_CONTRACT, get_risk_portfolio_summary
from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot, RiskSnapshotRefreshError
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.loans.tests import test_recorded_origination as paper_fixtures
from apps.tenant_apps.loans.web.economic_forms import LoanMonitoringPolicyForm
from apps.tenant_apps.loans.web.economic_setup import pawn_economics_setup
from apps.tenant_apps.loans.web.operations import pawn_risk_portfolio
from apps.tenant_apps.rates.models import Rate


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class MonitoringValuationTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "monitoring-valuation-basis"

    @classmethod
    def setup_tenant(cls, tenant):
        cls.actor = get_user_model().objects.create_user(username="valuation-owner")
        tenant.owner = tenant.creator = cls.actor
        tenant.save()
        Membership.objects.create(user=cls.actor, company=tenant, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        fixtures.CollateralReappraisalTests.make_loan(self)

    def data(self, **changes):
        values = model_to_dict(self.policy, fields=LoanMonitoringPolicyForm.Meta.fields)
        values.update(license=None, supersedes=self.policy, effective_from=self.today,
                      amendment_reason="Owner reviewed current collateral valuation")
        values.update(changes)
        return values

    def amend(self, **changes):
        self.policy = create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **self.data(**changes))
        return self.policy

    def valuation(self, day=None):
        return get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=day or self.today)

    def refresh(self):
        return refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)

    def test_default_keeps_original_method_and_unknown_stale_appraisal(self):
        Rate.objects.create(rate_source=self.source, buying_rate=3500, selling_rate=3600)
        row = self.valuation()
        self.assertEqual(row.valuation_method, "LOWER_OF_CALCULATED_AND_APPRAISAL")
        self.assertEqual(row.valuation_basis, "ORIGINAL_AGREEMENT")
        self.assertIsNone(row.eligible_collateral_value)
        self.assertIn("STALE_APPRAISAL", row.ltv.blockers)
        snapshot = self.refresh()
        self.assertEqual(snapshot.status, "CURRENT")
        self.assertEqual(snapshot.source_provenance["financial"]["calculation_status"], "SUPPORTED")
        self.assertEqual(snapshot.source_provenance["valuation"]["original_method"], row.valuation_method)
        self.assertEqual(get_dashboard_health_summary(workspace=self.tenant)["unknown_coverage_count"], 1)

    def test_explicit_metal_choice_supplies_current_coverage_without_rewriting_origin(self):
        snapshot = self.refresh()
        original = list(self.loan.loan_events.values()), list(self.loan.repayment_schedules.values()), model_to_dict(self.loan.policy_snapshot), list(self.item.appraisals.values())
        Rate.objects.create(rate_source=self.source, buying_rate=3500, selling_rate=3600)
        predecessor = self.policy
        policy = self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        predecessor.refresh_from_db()
        self.assertEqual(predecessor.valuation_basis, "ORIGINAL_AGREEMENT")
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "STALE")
        current = self.refresh()
        self.assertEqual(current.collateral_value, Decimal("3500"))
        self.assertIsNotNone(current.ltv_ratio)
        self.assertEqual(current.source_provenance["valuation"]["monitoring_policy_id"], policy.pk)
        self.assertEqual(current.source_provenance["valuation"]["method"], "CALCULATED_METAL_VALUE")
        self.assertEqual(current.source_provenance["valuation"]["original_method"], "LOWER_OF_CALCULATED_AND_APPRAISAL")
        self.assertEqual(original, (list(self.loan.loan_events.values()), list(self.loan.repayment_schedules.values()), model_to_dict(self.loan.policy_snapshot), list(self.item.appraisals.values())))
        health = get_dashboard_health_summary(workspace=self.tenant)
        self.assertEqual((health["current_count"], health["financial_count"], health["coverage_count"]), (1, 1, 1))
        self.assertEqual(health["assumed_capture_count"], 1)

    def test_selected_methods_require_only_their_own_fresh_evidence(self):
        fixtures.CollateralReappraisalTests.reassess(self, appraised_value=Decimal("2500"))
        self.amend(valuation_basis="LATEST_APPRAISAL")
        self.assertEqual(self.valuation().eligible_collateral_value, Decimal("2500"))
        self.amend(valuation_basis="LOWER_OF_CALCULATED_AND_APPRAISAL")
        self.assertIn("STALE_RATE", self.valuation().ltv.blockers)
        Rate.objects.create(rate_source=self.source, buying_rate=3500, selling_rate=3600)
        self.assertEqual(self.valuation().eligible_collateral_value, Decimal("2500"))
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        self.assertEqual(self.valuation().eligible_collateral_value, Decimal("3500"))
        self.amend(valuation_basis="ORIGINAL_AGREEMENT")
        self.assertEqual(self.valuation().eligible_collateral_value, Decimal("2500"))
        with patch("apps.tenant_apps.loans.selectors.collateral_valuation.get_latest_commodity_valuation_rate") as lookup:
            lookup.return_value.status, lookup.return_value.rate = "MISSING", None
            lookup.return_value.next_effective_at = None
            self.amend(valuation_basis="CALCULATED_METAL_VALUE")
            self.assertIsNone(self.valuation().eligible_collateral_value)
            self.assertIn("MISSING_RATE", self.valuation().ltv.blockers)

    def test_freshness_and_ineligible_custody_still_block_explicit_metal_value(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        self.assertIn("STALE_RATE", self.valuation().ltv.blockers)
        Rate.objects.create(rate_source=self.source, buying_rate=3500, selling_rate=3600)
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today)
        with patch("apps.tenant_apps.loans.selectors.collateral_valuation.PawnLoan.objects") as loans:
            self.item.custody_state = "RETURNED_TO_BORROWER"
            with patch.object(type(self.loan).collateral_items.related_manager_cls, "all", return_value=[self.item]):
                loans.select_related.return_value.prefetch_related.return_value.get.return_value = self.loan
                row = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today, _exposure=exposure)
            self.assertIn("CUSTODY_NOT_ELIGIBLE", row.ltv.blockers)
            self.assertIsNone(row.eligible_collateral_value)

    def test_future_amendment_and_license_override_resolve_without_backdating(self):
        Rate.objects.create(rate_source=self.source, buying_rate=3500, selling_rate=3600)
        tomorrow = self.today + timedelta(days=1)
        snapshot = self.refresh()
        self.amend(valuation_basis="CALCULATED_METAL_VALUE", effective_from=tomorrow)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "CURRENT")
        self.assertEqual(self.valuation().valuation_method, "LOWER_OF_CALCULATED_AND_APPRAISAL")
        self.assertEqual(self.valuation(tomorrow).valuation_method, "CALCULATED_METAL_VALUE")
        data = self.data(license=self.loan.license, supersedes=None, effective_from=self.today,
                         valuation_basis="ORIGINAL_AGREEMENT")
        override = create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **data)
        row = self.valuation(tomorrow)
        self.assertEqual(row.monitoring_policy_id, override.pk)
        self.assertEqual(row.valuation_method, "LOWER_OF_CALCULATED_AND_APPRAISAL")

    def test_amendment_requires_authority_reason_and_today_and_cannot_mutate_basis(self):
        for values in ({"amendment_reason": ""}, {"effective_from": self.today-timedelta(days=1)}, {"valuation_basis": "UNSUPPORTED"}):
            with self.assertRaises(ValidationError):
                self.amend(**values)
        with self.assertRaises(PermissionDenied):
            create_loan_monitoring_policy(workspace=self.tenant, actor=None, **self.data())
        with self.assertRaises(DatabaseError), transaction.atomic():
            LoanMonitoringPolicy.objects.filter(pk=self.policy.pk).update(valuation_basis="CALCULATED_METAL_VALUE")

    def test_older_form_preserves_explicit_basis_and_unused_grace_is_not_exposed(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE", operational_grace_days=17)
        delinquency = get_pawn_loan_delinquency(self.loan.pk, as_of_date=self.today)
        self.assertEqual(delinquency.assessment.operational_grace_days, self.loan.product_version.operational_grace_days)
        self.assertNotEqual(delinquency.assessment.operational_grace_days, 17)
        data = self.data()
        data.pop("valuation_basis")
        data["license"], data["supersedes"] = "", self.policy.pk
        form = LoanMonitoringPolicyForm(data, workspace=self.tenant, actor=self.actor)
        self.assertNotIn("operational_grace_days", form.fields)
        self.assertNotIn("severity_mapping", form.fields)
        self.assertTrue(form.is_valid(), form.errors)
        successor = create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, **form.cleaned_data)
        self.assertEqual(successor.valuation_basis, "CALCULATED_METAL_VALUE")
        self.assertEqual(successor.operational_grace_days, 17)
        self.assertEqual(successor.severity_mapping, self.policy.severity_mapping)

    def test_setup_and_portfolio_explain_independent_dimensions_and_frozen_origin(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        Rate.objects.create(rate_source=self.source, buying_rate=3500, selling_rate=3600)
        self.refresh()
        request = RequestFactory().get("/", {"amend_monitoring": self.policy.pk})
        request.user, request.workspace = self.actor, self.tenant
        setup = pawn_economics_setup(request)
        for text in ("Current monitoring valuation method", "current collateral monitoring", "loan's frozen product", "Current calculated metal value"):
            self.assertContains(setup, text)
        self.assertNotContains(setup, 'name="monitoring-operational_grace_days"')
        with patch("apps.tenant_apps.loans.web.operations.assess_risk_alert_communication_readiness"):
            page = pawn_risk_portfolio(request)
        for text in ("Financial calculation", "SUPPORTED", "Transaction coverage", "SYSTEM_RECORDED", "monitoring policy choice"):
            self.assertContains(page, text)
        from apps.tenant_apps.loans.web.pawn_reads import pawn_loan_detail
        detail = pawn_loan_detail(request, self.loan.pk)
        for text in ("Current monitoring assessment", "Saved loan method: Lower of calculated and appraisal", "this need not establish the original lending valuation"):
            self.assertContains(detail, text)

    def test_older_saved_contract_is_stale_and_new_contract_records_selected_method(self):
        snapshot = self.refresh()
        snapshot.source_provenance["calculation_contract"] = "LOAN_RISK_SNAPSHOT_V7"
        snapshot.save(update_fields=["source_provenance"])
        self.assertEqual(get_risk_portfolio_summary().stale_count, 1)
        snapshot = self.refresh()
        self.assertEqual(snapshot.source_provenance["calculation_contract"], SNAPSHOT_CONTRACT)
        self.assertEqual(get_risk_portfolio_summary().current_count, 1)

    def test_failed_financial_calculation_is_visible_but_cannot_supply_dashboard_amounts(self):
        from dataclasses import replace
        from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
        exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=self.today)
        inconsistent = replace(exposure, integrity_findings=("Unreconciled source allocation",))
        with patch("apps.tenant_apps.loans.services.risk_snapshots.get_pawn_loan_exposure", return_value=inconsistent):
            with self.assertRaises(RiskSnapshotRefreshError):
                self.refresh()
        summary = get_risk_portfolio_summary()
        self.assertEqual((summary.error_count, summary.inconsistent_calculation_count), (1, 1))
        health = get_dashboard_health_summary(workspace=self.tenant)
        self.assertEqual((health["financial_count"], health["coverage_count"]), (0, 0))
        self.assertIsNone(health["economic_exposure"])
        request = RequestFactory().get("/")
        request.user, request.workspace = self.actor, self.tenant
        with patch("apps.tenant_apps.loans.web.operations.assess_risk_alert_communication_readiness"):
            page = pawn_risk_portfolio(request)
        self.assertContains(page, "INCONSISTENT")
        self.assertContains(page, "Unreconciled source allocation")

    def test_published_setup_profiles_remain_compatible_but_hold_explicit_overrides(self):
        from importlib.util import find_spec
        if find_spec("apps.tenant_apps.loans.services.business_setup_portability") is None:
            self.skipTest("Business setup profiles are outside the monitoring-only release.")
        from apps.tenant_apps.loans.services.business_setup_portability import export_setup, models
        for version in (1, 2):
            self.assertIn("loans.LoanMonitoringPolicy", models(version))
            tables = export_setup(workspace_id=self.tenant.pk, actor=self.actor, save_file=lambda field: None, version=version)
            self.assertNotIn("valuation_basis", tables["loans.LoanMonitoringPolicy"][0])
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        for version in (1, 2):
            with self.assertRaisesMessage(ValueError, "newer business setup profile"):
                export_setup(workspace_id=self.tenant.pk, actor=self.actor, save_file=lambda field: None, version=version)


class MonitoringValuationUpgradeTests(TransactionTestCase):
    def test_populated_upgrade_preserves_policies_and_defaults_to_original_method(self):
        actor = get_user_model().objects.create_user(username=uuid4().hex)
        workspace = Company.objects.create(name="Valuation upgrade", schema_name=uuid4().hex, owner=actor, creator=actor)
        membership = Membership.objects.create(user=actor, company=workspace, role=Role.objects.get_or_create(name="Owner")[0])
        with workspace_context(workspace.pk):
            policy = LoanMonitoringPolicy.objects.create(workspace=workspace, version=1, effective_from=timezone.localdate(),
                compliance_profile="Retained owner-reviewed policy", operational_grace_days=17,
                ltv_warning_ratio="0.7", ltv_breach_ratio="0.8", ltv_critical_ratio="0.9",
                eligible_custody_states=["IN_VAULT"], severity_mapping={"legacy": "retained"}, created_by=actor)
        before = [("loans", "0072_risk_evidence_guards")]
        after = [("loans", "0073_monitoring_valuation_basis")]
        with historical_migration_database(self, before, [membership, policy]) as (target, old_apps):
            old = old_apps.get_model("loans", "LoanMonitoringPolicy")
            retained = list(old.objects.using(target.alias).values())
            executor = MigrationExecutor(target)
            executor.migrate(after)
            new = executor.loader.project_state(after).apps.get_model("loans", "LoanMonitoringPolicy")
            rows = list(new.objects.using(target.alias).values())
            self.assertEqual([row.pop("valuation_basis") for row in rows], ["ORIGINAL_AGREEMENT"])
            self.assertEqual(rows, retained)
            # During the online switch an old web process can still insert a
            # policy without knowing this column. The database keeps its default.
            with target.cursor() as cursor:
                cursor.execute("SELECT column_default FROM information_schema.columns WHERE table_name='loans_loanmonitoringpolicy' AND column_name='valuation_basis'")
                self.assertIn("ORIGINAL_AGREEMENT", cursor.fetchone()[0])
            legacy = {key: value for key, value in retained[0].items() if key not in ("id", "created_at")}
            legacy.update(id=policy.pk+10, version=2, supersedes_id=policy.pk, amendment_reason="Online switch compatibility",
                          effective_from=timezone.localdate()+timedelta(days=1))
            created = old.objects.using(target.alias).create(**legacy)
            self.assertEqual(new.objects.using(target.alias).get(pk=created.pk).valuation_basis, "ORIGINAL_AGREEMENT")
            with self.assertRaisesMessage(DatabaseError, "immutable"), transaction.atomic(using=target.alias):
                new.objects.using(target.alias).filter(pk=policy.pk).update(valuation_basis="CALCULATED_METAL_VALUE")
            values = dict(retained[0], id=policy.pk+1, version=2, supersedes_id=policy.pk, amendment_reason="Current monitoring review", valuation_basis="INVALID")
            with self.assertRaises(DatabaseError), transaction.atomic(using=target.alias):
                new.objects.using(target.alias).create(**values)


class PaperMonitoringValuationTests(WorkspaceTestCase):
    setup_tenant = classmethod(paper_fixtures.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = paper_fixtures.RecordedOriginationTests.make_snapshot

    @classmethod
    def get_test_schema_name(cls):
        return "paper-monitoring-valuation"

    def test_current_metal_monitoring_does_not_certify_missing_paper_activity(self):
        from apps.tenant_apps.rates.models import RateSource
        origin = self.make_snapshot(method="LATEST_APPRAISAL")
        loan, today = origin.loan, timezone.localdate()
        frozen = model_to_dict(loan.policy_snapshot), list(loan.loan_events.values()), origin.evidence.copy()
        create_loan_monitoring_policy(workspace=self.tenant, actor=self.actor, effective_from=today,
            compliance_profile="Explicit paper-loan monitoring", valuation_basis="CALCULATED_METAL_VALUE",
            ltv_warning_ratio=Decimal("0.7"), ltv_breach_ratio=Decimal("0.8"), ltv_critical_ratio=Decimal("0.9"))
        Rate.objects.create(rate_source=RateSource.objects.create(name="Market", location="Local"), buying_rate=2000, selling_rate=2100)
        snapshot = refresh_loan_risk_snapshot(loan.pk, as_of_date=today)
        self.assertEqual(snapshot.status, "CURRENT")
        self.assertEqual(snapshot.collateral_value, Decimal("16200"))
        self.assertEqual(snapshot.source_provenance["valuation"]["reference_limit_source"], "RECORDED_MONITORING_REFERENCE")
        self.assertTrue(snapshot.source_provenance["transactions"]["complete"])
        self.assertFalse(snapshot.source_provenance["transactions"]["book_review"]["complete"])
        self.assertNotIn("TRANSACTIONS_UNCONFIRMED", snapshot.flags)
        health = get_dashboard_health_summary(workspace=self.tenant)
        self.assertEqual((health["financial_count"], health["coverage_count"], health["provisional_count"]), (1, 1, 0))
        self.assertTrue(health["financial_complete"])
        self.assertTrue(health["coverage_complete"])
        self.assertEqual(frozen, (model_to_dict(loan.policy_snapshot), list(loan.loan_events.values()), loan.disbursal_snapshot.evidence))
