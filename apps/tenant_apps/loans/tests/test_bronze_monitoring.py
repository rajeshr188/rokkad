"""Bronze shares origination, current valuation and evidence freshness rules."""
from decimal import Decimal
from datetime import timedelta

from django.forms.models import model_to_dict
from django.utils import timezone
from django.test import override_settings

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.rates.models import Rate
from apps.tenant_apps.rates.services import record_quote
from apps.tenant_apps.loans.services.monitoring_policies import create_loan_monitoring_policy
from . import test_collateral_reappraisal as fixtures
from . import test_monitoring_valuation_basis as monitoring


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
                            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class BronzeMonitoringTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)
    data = monitoring.MonitoringValuationTests.data
    amend = monitoring.MonitoringValuationTests.amend
    valuation = monitoring.MonitoringValuationTests.valuation
    refresh = monitoring.MonitoringValuationTests.refresh

    @classmethod
    def get_test_schema_name(cls):
        return "bronze-monitoring"

    def setUp(self):
        fixtures.CollateralReappraisalTests.make_loan(self, metal="BRONZE", purity="85.25")

    def market_quote(self, **changes):
        values = dict(rate_source=self.source, metal="Bronze", currency="INR", purity="24k",
                      buying_rate=Decimal("123.45"), selling_rate=Decimal("130"), effective_at=timezone.now())
        values.update(changes)
        return record_quote(workspace=self.tenant, actor=self.actor, values=values)

    def test_current_bronze_value_and_saved_risk_preserve_frozen_lending_and_money(self):
        original = (list(self.loan.loan_events.values()), model_to_dict(self.loan.policy_snapshot),
                    list(self.loan.repayment_schedules.values()), list(self.item.appraisals.values()))
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        quote = self.market_quote()
        live = self.valuation()
        self.assertEqual(live.eligible_collateral_value, Decimal("105.24"))
        self.assertEqual(live.items[0].rate_id, quote.pk)
        self.assertEqual(live.items[0].rate_status, "CURRENT")
        self.assertNotIn("MISSING_APPRAISAL", live.ltv.blockers)
        saved = self.refresh()
        self.assertEqual(saved.collateral_value, live.eligible_collateral_value)
        self.assertEqual(saved.ltv_ratio, live.ltv.ltv_ratio)
        self.assertEqual(original, (list(self.loan.loan_events.values()), model_to_dict(self.loan.policy_snapshot),
                    list(self.loan.repayment_schedules.values()), list(self.item.appraisals.values())))
        self.assertEqual(self.loan.approval_snapshots.get().payload["collateral_economics"]["tranches"][0]["metal"], "BRONZE")

    def test_missing_stale_future_or_withdrawn_bronze_price_does_not_become_coverage(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        self.assertIn("STALE_RATE", self.valuation().ltv.blockers)
        future = self.market_quote(effective_at=timezone.now() + timedelta(days=1))
        self.assertNotEqual(self.valuation().items[0].rate_id, future.pk)
        current = self.market_quote()
        self.assertIsNotNone(self.valuation().eligible_collateral_value)
        from apps.tenant_apps.rates.services import withdraw_quote
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=current.pk, reason="Fictional source review")
        self.assertIsNone(self.valuation().eligible_collateral_value)
        self.assertIn("STALE_RATE", self.valuation().ltv.blockers)

    def test_bronze_quote_changes_invalidate_saved_risk_without_posting_money(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        self.market_quote()
        saved = self.refresh()
        events = list(self.loan.loan_events.values())
        from apps.tenant_apps.loans.services.risk_snapshots import _source_fingerprint
        fingerprint = _source_fingerprint(self.loan.pk, self.tenant.pk, self.today)
        self.market_quote(buying_rate=Decimal("120"))
        self.assertNotEqual(_source_fingerprint(self.loan.pk, self.tenant.pk, self.today), fingerprint)
        saved.refresh_from_db()
        self.assertEqual(saved.status, "STALE")
        self.assertEqual(self.refresh().collateral_value, Decimal("102.30"))
        self.assertEqual(list(self.loan.loan_events.values()), events)

    def test_previous_contract_is_outdated_and_pending_even_when_dated_today(self):
        from apps.tenant_apps.loans.selectors.risk_portfolio import snapshot_is_current, get_risk_portfolio_summary
        from apps.tenant_apps.loans.services.risk_snapshots import _pending_loans
        from apps.tenant_apps.loans.models import LoanRiskSnapshot, PawnLoan
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        self.market_quote()
        saved = self.refresh()
        provenance = dict(saved.source_provenance, calculation_contract="LOAN_RISK_SNAPSHOT_V8")
        LoanRiskSnapshot.objects.filter(pk=saved.pk).update(source_provenance=provenance)
        saved.refresh_from_db()
        self.assertFalse(snapshot_is_current(saved, self.today))
        self.assertEqual(get_risk_portfolio_summary().current_count, 0)
        self.assertTrue(_pending_loans(PawnLoan.objects.all(), self.tenant.pk, self.today).filter(pk=self.loan.pk).exists())
        self.assertTrue(snapshot_is_current(self.refresh(), self.today))

    def test_direct_entry_bronze_price_preflight_and_appraisal_suggestion(self):
        from django.test import RequestFactory
        from apps.tenant_apps.loans.forms import PawnCollateralDraftForm
        from apps.tenant_apps.loans.web.rate_readiness import pawn_valuation_readiness
        from apps.tenant_apps.loans.web.appraisal import collateral_appraisal_suggestion
        self.market_quote()
        self.assertIn("BRONZE", dict(PawnCollateralDraftForm().fields["metal"].choices))
        self.assertNotIn("OTHER", dict(PawnCollateralDraftForm().fields["metal"].choices))
        request = RequestFactory().get("/", dict(series=self.loan.series_id, as_of=self.today, metals="BRONZE", request_key=1))
        request.user, request.workspace = self.actor, self.tenant
        self.assertContains(pawn_valuation_readiness(request), 'data-ready="true"')
        request = RequestFactory().get("/", dict(metal="BRONZE", gross_weight="1", net_weight="1", purity="85.25", as_of=self.today, request_key=2))
        request.user, request.workspace = self.actor, self.tenant
        self.assertContains(collateral_appraisal_suggestion(request), "105.24")


class GoldMonitoringRoundingTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)
    data = monitoring.MonitoringValuationTests.data
    amend = monitoring.MonitoringValuationTests.amend
    valuation = monitoring.MonitoringValuationTests.valuation
    metal = "GOLD"

    @classmethod
    def get_test_schema_name(cls):
        return "reference-grade-precision-" + cls.metal.lower()

    def test_stored_currency_quantum_trailing_zeros_do_not_add_valuation_precision(self):
        fixtures.CollateralReappraisalTests.make_loan(self, metal=self.metal, purity="85.25")
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        Rate.objects.create(rate_source=self.source, metal=self.metal.title(), buying_rate="123.45", selling_rate="130")
        self.loan.policy_snapshot.refresh_from_db()
        self.assertEqual(str(self.loan.policy_snapshot.currency_quantum), "0.0100")
        self.assertEqual(self.valuation().eligible_collateral_value, Decimal("105.24"))


class SilverMonitoringRoundingTests(GoldMonitoringRoundingTests):
    metal = "SILVER"
