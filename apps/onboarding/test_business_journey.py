from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.onboarding.navigation import setup_navigation, setup_saved_redirect
from apps.onboarding.services.setup_checklist import build_business_setup
from apps.orgs.models import Membership, Role
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.domain.monthly_contract import anniversary
from apps.tenant_apps.loans.models import (
    LoanLicense, LoanNumberSequence, LoanSeries, LoanMonitoringPolicy, PawnLoan, PawnLoanEvent,
    PawnLoanEconomicPolicy, PawnMetalInterestRatePolicy, PawnLoanFeePolicy,
)
from apps.tenant_apps.loans.selectors.setup import get_pawn_setup_checklist
from apps.tenant_apps.loans.services.setup_examples import calculate_setup_example
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.party.models import Party


class SetupExampleTests(SimpleTestCase):
    def policy(self, **changes):
        values = dict(currency_quantum=Decimal(".01"), advance_interest_periods=1,
            interest_method="SIMPLE", partial_month_method="FULL_MONTH", minimum_first_month=True,
            partial_month_cutoff_days=15, partial_month_lower_fraction=Decimal(".5"))
        return SimpleNamespace(**{**values, **changes})

    def example(self, **changes):
        values = dict(policy=self.policy(), monthly_rate=Decimal("2"), fees=(),
            principal=Decimal("10000"), start=date(2026, 1, 31), end=date(2026, 3, 1))
        return calculate_setup_example(**{**values, **changes})

    def test_month_end_boundary_and_upfront_credit_match_shared_monthly_contract(self):
        result = self.example()
        by_date = {row["date"]: row for row in result["settlements"]}
        self.assertEqual(result["payout"], Decimal("9800"))
        self.assertEqual(by_date[date(2026, 2, 28)]["amount"], Decimal("10000"))
        self.assertEqual(by_date[date(2026, 3, 1)]["amount"], Decimal("10200"))
        april = self.example(end=date(2026, 4, 1))
        self.assertEqual(april["settlements"][0]["amount"], Decimal("10400"))

    def test_fee_scopes_are_resolved_upstream_and_deduction_is_not_charged_twice(self):
        fees = (SimpleNamespace(code="DOC", name="Document", calculation_type="FIXED", value=10, deducted_at_disbursal=True),
                SimpleNamespace(code="OTHER", name="Other", calculation_type="PERCENTAGE", value=1, deducted_at_disbursal=False))
        result = self.example(fees=fees)
        self.assertEqual(result["payout"], Decimal("9790"))
        self.assertEqual(result["separate_fees"], Decimal("100"))
        self.assertEqual(result["settlements"][0]["amount"], Decimal("10200"))

    def test_actual_days_and_whole_rupee_rounding_use_saved_policy(self):
        result = self.example(policy=self.policy(partial_month_method="ACTUAL_DAYS", currency_quantum=Decimal("1")))
        # March 1 is one of 31 days in the second anchored monthly period.
        self.assertEqual(result["settlements"][0]["additional_interest"], Decimal("6"))

    def test_compound_example_never_invents_capitalization(self):
        result = self.example(policy=self.policy(interest_method="COMPOUND"))
        self.assertTrue(result["settlement_unavailable"])
        self.assertEqual(result["settlements"], [])
        self.assertEqual(result["payout"], Decimal("9800"))

    def test_invalid_dates_and_nonpositive_payout_are_rejected(self):
        for values in ({"end": date(2026, 1, 30)}, {"end": date(2030, 1, 1)},
                       {"principal": Decimal("0")}, {"policy": self.policy(advance_interest_periods=12), "monthly_rate": Decimal("10")}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.example(**values)

    def test_navigation_cannot_select_another_workspace_or_open_redirect(self):
        request = RequestFactory().post("/w/acme/loans/setup/", {
            "setup_step": "terms", "setup_path": "https://evil.invalid", "next": "//evil.invalid"})
        request.workspace = SimpleNamespace(slug="acme")
        response = setup_saved_redirect(request, step="review")
        self.assertEqual(response.url, "/w/acme/settings/setup/?step=review&path=new")
        request.workspace = None
        self.assertIsNone(setup_navigation(request))


@override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class BusinessJourneyTests(WorkspaceTestCase):
    @classmethod
    def get_test_schema_name(cls):
        return "guided-business-setup"

    @classmethod
    def setup_tenant(cls, tenant):
        owner = get_user_model().objects.create_user(username="guided-business-owner")
        tenant.owner = owner
        tenant.creator = owner
        tenant.name = "Guided business"
        tenant.save()
        Membership.objects.create(user=owner, company=tenant, role=Role.objects.get_or_create(name="Owner")[0])

    def setUp(self):
        super().setUp()
        self.owner = self.tenant.owner
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.owner)
        self.today = timezone.localdate()
        self.url = reverse("workspace_slug_settings_setup", kwargs={"workspace_slug": self.tenant.slug})

    def configure(self, *, code="A", metal="GOLD", valuation="LATEST_APPRAISAL"):
        licence = LoanLicense.objects.create(workspace=self.tenant, name="Licence " + code, license_number="TEST-" + code,
            issued_on=self.today - timedelta(days=1), expires_on=self.today + timedelta(days=365))
        series = LoanSeries.objects.create(license=licence, name="Series " + code, code=code)
        for kind in ("PAWN_LOAN", "PAWN_LOAN_RELEASE"):
            LoanNumberSequence.objects.create(series=series, document_kind=kind, prefix=code + "-", width=5, maximum_number=1000)
        policy = PawnLoanEconomicPolicy.objects.create(workspace=self.tenant, license=licence,
            effective_from=self.today, valuation_method=valuation, maximum_ltv_ratio=Decimal(".8"),
            interest_method="SIMPLE", partial_month_method="FULL_MONTH", minimum_first_month=True,
            advance_interest_periods=1, default_tenure_months=12)
        PawnMetalInterestRatePolicy.objects.create(workspace=self.tenant, license=licence, metal=metal,
            monthly_interest_rate=2, effective_from=self.today)
        ensure_test_product_version(self.tenant)
        return licence, series, policy

    def test_gold_only_business_is_ready_without_silver_policy_or_borrower(self):
        self.configure()
        self.assertFalse(Party.objects.filter(workspace=self.tenant).exists())
        setup = build_business_setup(workspace=self.tenant)
        self.assertTrue(setup["ready"])
        self.assertNotIn("borrower", [step["key"] for step in setup["steps"]])
        self.assertEqual(["GOLD"], [metal["metal"] for metal in setup["series_rows"][0]["metals"]])

    def monitoring_policy(self, **changes):
        values = dict(workspace=self.tenant, version=1, effective_from=self.today,
            compliance_profile="Reviewed test monitoring", maturity_warning_days=30,
            dpd_watch_threshold=1, dpd_substandard_threshold=90, ltv_warning_ratio=Decimal(".7"),
            ltv_breach_ratio=Decimal(".8"), ltv_critical_ratio=Decimal(".9"),
            rate_freshness_days=7, appraisal_freshness_days=90,
            eligible_custody_states=["IN_VAULT", "WITH_FUNDING_LENDER"], severity_mapping={"strategy":"derived-v1"})
        return LoanMonitoringPolicy.objects.create(**{**values, **changes})

    def test_lending_can_be_ready_without_silently_configuring_monitoring(self):
        self.configure()
        setup = build_business_setup(workspace=self.tenant)
        self.assertTrue(setup["ready"])
        self.assertFalse(setup["monitoring"]["ready"])
        self.assertEqual(setup["monitoring"]["total_count"], 1)
        before = (LoanMonitoringPolicy.objects.count(), PawnLoan.objects.count(), PawnLoanEvent.objects.count())
        page = self.client.get(self.url, {"step":"review"})
        self.assertContains(page,"Monitoring readiness")
        self.assertContains(page,"Create your first loan")
        self.assertEqual(before,(LoanMonitoringPolicy.objects.count(),PawnLoan.objects.count(),PawnLoanEvent.objects.count()))

    def test_monitoring_readiness_resolves_current_workspace_default_and_license_override(self):
        first, _, _ = self.configure()
        second, _, _ = self.configure(code="B")
        default = self.monitoring_policy()
        override = self.monitoring_policy(license=second)
        setup = build_business_setup(workspace=self.tenant)
        by_license = {row["series"].license_id:row["monitoring_policy"] for row in setup["series_rows"]}
        self.assertTrue(setup["monitoring"]["ready"])
        self.assertEqual(by_license[first.pk].pk,default.pk)
        self.assertEqual(by_license[second.pk].pk,override.pk)

    def test_future_monitoring_policy_does_not_make_today_complete(self):
        first, _, _ = self.configure()
        self.configure(code="B")
        self.monitoring_policy(license=first)
        self.monitoring_policy(effective_from=self.today+timedelta(days=1))
        setup = build_business_setup(workspace=self.tenant)
        self.assertEqual(setup["monitoring"],{"ready":False,"available_count":1,"total_count":2})

    def test_readiness_does_not_mix_interest_and_quotes_across_series(self):
        self.configure(valuation="CALCULATED_METAL_VALUE")
        self.configure(code="B", metal="SILVER", valuation="CALCULATED_METAL_VALUE")
        # Gold's quote is stale, silver has a current quote. Only B is ready.
        quotes = [{"metal": metal, "label": metal.title(), "rate": None, "usable": False,
                   "fresh": metal == "SILVER"} for metal in ("GOLD", "SILVER")]
        with patch("apps.tenant_apps.loans.selectors.setup.get_metal_rate_readiness", return_value=quotes):
            setup = get_pawn_setup_checklist(self.tenant)
        self.assertFalse(setup["series_rows"][0]["ready"])
        self.assertTrue(setup["series_rows"][1]["ready"])
        PawnMetalInterestRatePolicy.objects.filter(license__license_number="TEST-B").delete()
        with patch("apps.tenant_apps.loans.selectors.setup.get_metal_rate_readiness", return_value=quotes):
            self.assertFalse(get_pawn_setup_checklist(self.tenant)["ready"])

    def test_all_six_steps_render_without_writing_or_consuming_numbers(self):
        self.configure()
        before = list(LoanNumberSequence.objects.filter(workspace=self.tenant).values())
        policies = PawnLoanEconomicPolicy.objects.filter(workspace=self.tenant).count()
        for step in ("business", "starting", "license", "lending", "terms", "review"):
            with self.subTest(step=step):
                response = self.client.get(self.url, {"step": step, "path": "paper"})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, 'aria-current="step"')
                self.assertContains(response, 'hx-history="false"')
                self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(before, list(LoanNumberSequence.objects.filter(workspace=self.tenant).values()))
        self.assertEqual(policies, PawnLoanEconomicPolicy.objects.filter(workspace=self.tenant).count())
        self.assertFalse(PawnLoan.objects.filter(workspace=self.tenant).exists())
        self.assertFalse(PawnLoanEvent.objects.filter(workspace=self.tenant).exists())

    def test_review_uses_saved_series_rate_and_fee_without_fictitious_customer(self):
        licence, series, policy = self.configure()
        PawnLoanFeePolicy.objects.create(workspace=self.tenant, license=licence, code="DOC", name="Document charge",
            calculation_type="FIXED", value=10, deducted_at_disbursal=True, effective_from=self.today)
        response = self.client.get(self.url, {"step": "review"})
        self.assertEqual(response.context["setup_review"]["example"]["payout"], Decimal("9790"))
        self.assertContains(response, "EXAMPLE · NOT AN ISSUED DOCUMENT")
        self.assertContains(response, "Create your first loan")
        self.assertFalse(Party.objects.filter(workspace=self.tenant).exists())

    def test_multiple_series_require_an_explicit_example_choice(self):
        self.configure()
        self.configure(code="B")
        response = self.client.get(self.url, {"step": "review"})
        self.assertIsNone(response.context["setup_review"]["example"])
        response = self.client.get(self.url, {"step": "review", "example": "1", "series": "999999999",
            "metal": "GOLD", "principal": "10000", "closing_date": self.today.isoformat()})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["setup_review"]["form"].errors)
        self.assertIsNone(response.context["setup_review"]["example"])

    def test_stopped_series_and_legacy_licence_cannot_mark_new_lending_ready(self):
        licence, series, policy = self.configure()
        series.is_active = False
        series.save(update_fields=["is_active"])
        self.assertFalse(build_business_setup(workspace=self.tenant)["ready"])

    def test_guided_workflow_save_returns_to_matching_workspace_and_preserves_path(self):
        url = reverse("workspace_loans:loan_workflow_settings", kwargs={"workspace_slug": self.tenant.slug})
        page = self.client.get(url, {"setup_step": "lending", "setup_path": "paper"})
        self.assertContains(page, 'name="setup_step" value="lending"')
        response = self.client.post(url, {"mode": "SIMPLE", "setup_step": "lending", "setup_path": "paper"})
        self.assertEqual(response.url, self.url + "?step=lending&path=paper")
        self.tenant.refresh_from_db()
        self.assertEqual(self.tenant.loan_workflow, "SIMPLE")

    def test_navigation_marker_does_not_grant_staff_setup_or_owner_actions(self):
        viewer = get_user_model().objects.create_user(username="guided-business-viewer")
        Membership.objects.create(user=viewer, company=self.tenant, role=Role.objects.get_or_create(name="Viewer")[0])
        self.client.force_login(viewer)
        response = self.client.get(self.url, {"step": "review", "setup_step": "review"})
        self.assertEqual(response.status_code, 403)
        url = reverse("workspace_loans:loan_workflow_settings", kwargs={"workspace_slug": self.tenant.slug})
        self.assertEqual(self.client.post(url, {"mode": "SIMPLE", "setup_step": "lending"}).status_code, 403)

    def test_single_metal_configuration_appends_only_chosen_rate_and_audits_it(self):
        from apps.tenant_apps.loans.services.economic_policies import create_pawn_economic_configuration
        from apps.orgs.audit import AuditLog
        old_silver = PawnMetalInterestRatePolicy.objects.create(workspace=self.tenant, metal="SILVER",
            monthly_interest_rate=4, effective_from=self.today - timedelta(days=1))
        result = create_pawn_economic_configuration(workspace=self.tenant, actor=self.owner,
            gold_monthly_interest_rate=Decimal("2"), silver_monthly_interest_rate=None,
            valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal(".8"), effective_from=self.today)
        self.assertIsNotNone(result.gold_rate_policy)
        self.assertIsNone(result.silver_rate_policy)
        self.assertEqual(PawnMetalInterestRatePolicy.objects.filter(workspace=self.tenant, metal="SILVER").count(), 1)
        old_silver.refresh_from_db()
        self.assertEqual(old_silver.monthly_interest_rate, Decimal("4"))
        audit = AuditLog.objects.filter(company=self.tenant, data__economic_policy_id=result.economic_policy.pk).get()
        self.assertIsNone(audit.data["silver_rate_policy_id"])
        count = PawnLoanEconomicPolicy.objects.filter(workspace=self.tenant).count()
        with self.assertRaises(ValueError):
            create_pawn_economic_configuration(workspace=self.tenant, actor=self.owner,
                gold_monthly_interest_rate=None, silver_monthly_interest_rate=None,
                valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal(".8"), effective_from=self.today)
        self.assertEqual(PawnLoanEconomicPolicy.objects.filter(workspace=self.tenant).count(), count)

    def test_guided_single_metal_form_saves_without_an_unrelated_rate(self):
        url = reverse("workspace_loans:pawn_economics_setup", kwargs={"workspace_slug": self.tenant.slug})
        data = {"action": "configuration", "setup_step": "terms", "setup_path": "new",
            "configuration-metals_to_configure": "GOLD", "configuration-gold_monthly_interest_rate": "2",
            "configuration-silver_monthly_interest_rate": "", "configuration-effective_from": self.today.isoformat(),
            "configuration-valuation_method": "LATEST_APPRAISAL", "configuration-maximum_ltv_ratio": ".8",
            "configuration-advance_interest_periods": "1", "configuration-interest_method": "SIMPLE",
            "configuration-partial_month_method": "FULL_MONTH", "configuration-partial_month_cutoff_days": "15",
            "configuration-partial_month_lower_fraction": ".5", "configuration-capitalization_interval_periods": "12",
            "configuration-rounding_method": "PER_ACCRUAL_PERIOD", "configuration-currency_quantum": ".01"}
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        self.assertEqual(response.url, self.url + "?step=terms&path=new")
        self.assertEqual(list(PawnMetalInterestRatePolicy.objects.filter(workspace=self.tenant).values_list("metal", flat=True)), ["GOLD"])
        response = self.client.get(url, {"setup_step": "terms"})
        self.assertEqual(response.context["configuration_form"]["metals_to_configure"].value(), "GOLD")
        self.assertContains(response, "Back to guided setup")

    def test_guided_series_save_returns_to_lending_without_allocating_a_number(self):
        licence = LoanLicense.objects.create(workspace=self.tenant, name="Licence", license_number="TEST-GUIDED",
            issued_on=self.today, expires_on=self.today + timedelta(days=365))
        url = reverse("workspace_loans:series_create", kwargs={"workspace_slug": self.tenant.slug, "license_pk": licence.pk})
        response = self.client.post(url, {"name": "Main", "code": "A", "is_active": "on", "pawn_loan_prefix": "A-",
            "release_prefix": "R-", "number_width": "5", "maximum_number": "1000", "setup_step": "license", "setup_path": "paper"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, self.url + "?step=lending&path=paper")
        self.assertEqual(list(LoanNumberSequence.objects.filter(workspace=self.tenant).values_list("next_number", flat=True)), [1, 1])
