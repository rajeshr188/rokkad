from datetime import date, datetime, timedelta
from decimal import Decimal
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.domain.interest import partial_period_fraction, calculate_period_interest
from apps.tenant_apps.loans.domain.policies import DisbursalPolicySnapshot, resolve_policy
from apps.tenant_apps.loans.models import LoanSeries, PawnLoanEconomicPolicy
from apps.tenant_apps.loans.services.economic_policies import (
    create_pawn_loan_economic_policy, resolve_pawn_loan_economic_policy,
    PawnEconomicPolicyError,
)
from apps.tenant_apps.loans.services.pawn_interest import _partial_fraction, _add_months
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.loans.tests import test_economic_policy_services as scope_fixtures


class PartialMonthMathTests(SimpleTestCase):
    def test_accepted_thirty_day_table_and_first_month_minimum(self):
        expected = {
            "FULL_MONTH": [300, 300, 300, 300, 300],
            "SLAB": [150, 150, 150, 300, 300],
            "STARTED_WEEKS": [70, 140, 210, 210, 300],
            "ACTUAL_DAYS": [10, 80, 150, 160, 290],
        }
        for method, amounts in expected.items():
            for day, amount in zip((1, 8, 15, 16, 29), amounts):
                for period in (1, 2):
                    with self.subTest(method=method, day=day, period=period):
                        fraction = partial_period_fraction(method=method, elapsed_days=day,
                            period_days=30, minimum_first_month=True, period_number=period)
                        _, charge = calculate_period_interest(calculation_base=15000,
                            monthly_interest_rate=2, period_fraction=fraction, currency_quantum="0.01")
                        self.assertEqual(charge, Decimal(300 if period == 1 else amount))

    def test_february_leap_year_month_end_and_week_boundaries(self):
        from types import SimpleNamespace
        for start, length in ((date(2026, 2, 1), 28), (date(2028, 2, 1), 29),
                              (date(2026, 1, 1), 31), (date(2026, 1, 31), 28)):
            self.assertEqual((_add_months(start, 1) - start).days, length)
            for method in ("STARTED_WEEKS", "ACTUAL_DAYS"):
                policy = SimpleNamespace(partial_month_method=method, minimum_first_month=True,
                    partial_month_cutoff_days=15, partial_month_lower_fraction=Decimal("0.5"))
                for elapsed in (1, 7, 8, 14, 15, 21, 22, length):
                    fraction = _partial_fraction(policy, start, start + timedelta(days=elapsed-1), period_number=2)
                    days = min(((elapsed + 6)//7)*7, length) if method == "STARTED_WEEKS" else elapsed
                    self.assertEqual(fraction, Decimal(days)/Decimal(length))
                    self.assertLessEqual(fraction, 1)

    def test_old_snapshot_missing_minimum_remains_unchanged(self):
        payload = resolve_policy().to_disbursal_snapshot().to_dict()
        payload.pop("minimum_first_month")
        payload["partial_month_method"] = "SLAB"
        policy = DisbursalPolicySnapshot.from_dict(payload)
        self.assertFalse(policy.minimum_first_month)
        self.assertEqual(partial_period_fraction(method="SLAB", elapsed_days=1,
            period_days=30, minimum_first_month=policy.minimum_first_month), Decimal("0.5"))
        with self.assertRaises(ValueError):
            DisbursalPolicySnapshot.from_dict(payload | {"minimum_first_month": "false"})


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class SeriesCalculationPolicyTests(WorkspaceTestCase):
    setup_tenant = classmethod(scope_fixtures.PawnEconomicPolicyServiceTests.setup_tenant.__func__)
    configuration = scope_fixtures.PawnEconomicPolicyServiceTests.configuration

    def setUp(self):
        super().setUp()
        from apps.tenant_apps.loans.services import create_license
        from apps.orgs.models import Membership, Role
        self.user = self.tenant.owner
        Membership.objects.get_or_create(user=self.user, company=self.tenant,
            defaults={"role": Role.objects.get_or_create(name="Owner")[0]})
        self.license = create_license(workspace=self.tenant, name="Policy test", license_number="POLICY",
            issued_on=date(2026, 1, 1), expires_on=date(2028, 1, 1), actor=self.user)

    def test_series_precedence_dates_revisions_and_atomic_rates(self):
        workspace = self.configuration()
        license_policy = self.configuration(license=self.license)
        series = LoanSeries.objects.create(license=self.license, name="WH", code="WH")
        other = LoanSeries.objects.create(license=self.license, name="Other", code="OTHER")
        weekly = self.configuration(license=self.license, series=series,
            partial_month_method="STARTED_WEEKS", effective_from=date(2026, 9, 30))
        self.assertTrue(weekly.economic_policy.minimum_first_month)
        def resolve(series_id=None, day=date(2026, 9, 30), license_id=None):
            return resolve_pawn_loan_economic_policy(workspace_id=self.tenant.pk,
                license_id=license_id or self.license.pk, series_id=series_id, as_of_date=day)
        self.assertEqual(resolve(series.pk), weekly.economic_policy)
        self.assertEqual(resolve(other.pk), license_policy.economic_policy)
        self.assertEqual(resolve(series.pk, date(2026, 9, 29)), license_policy.economic_policy)
        self.assertEqual(resolve(), license_policy.economic_policy)
        daily = self.configuration(license=self.license, series=series,
            partial_month_method="ACTUAL_DAYS", effective_from=date(2026, 9, 30),
            effective_until=date(2026, 10, 1))
        self.assertEqual(daily.economic_policy.revision, 2)
        self.assertEqual(resolve(series.pk), daily.economic_policy)
        self.assertEqual(resolve(series.pk, date(2026, 10, 2)), weekly.economic_policy)
        self.assertEqual(daily.gold_rate_policy.series_id, series.pk)
        self.assertEqual(resolve_pawn_loan_economic_policy(workspace_id=self.tenant.pk,
            license_id=None, as_of_date=date(2026, 9, 30)), workspace.economic_policy)
        count = PawnLoanEconomicPolicy.objects.count()
        with self.assertRaises(ValidationError):
            self.configuration(license=self.license, series=series, silver_monthly_interest_rate=101)
        self.assertEqual(PawnLoanEconomicPolicy.objects.count(), count)

    def test_series_scope_validation_and_form(self):
        from apps.tenant_apps.loans.web.economic_forms import PawnEconomicConfigurationForm
        series = LoanSeries.objects.create(license=self.license, name="WH", code="WH")
        with self.assertRaises(PawnEconomicPolicyError):
            resolve_pawn_loan_economic_policy(workspace_id=self.tenant.pk, license_id=None,
                series_id=series.pk, as_of_date=date(2026, 9, 30))
        with self.assertRaises(ValidationError):
            self.configuration(series=series)
        data = dict(series=series.pk, valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio="0.8",
            advance_interest_periods=1, interest_method="SIMPLE", partial_month_method="STARTED_WEEKS",
            partial_month_cutoff_days=15, partial_month_lower_fraction="0.5", capitalization_interval_periods=12,
            rounding_method="PER_ACCRUAL_PERIOD", currency_quantum="0.01", gold_monthly_interest_rate=2,
            silver_monthly_interest_rate=4, effective_from="2026-09-30")
        form = PawnEconomicConfigurationForm(data, workspace=self.tenant)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["license"], self.license)
        self.assertTrue(form.cleaned_data["minimum_first_month"])
        self.assertEqual(len(form.fields["partial_month_method"].choices), 4)

    def test_series_setup_http_copies_correct_rates_and_renders_all_options(self):
        from django.test import RequestFactory
        from django.contrib.messages.storage.fallback import FallbackStorage
        from apps.tenant_apps.loans.web.economic_setup import pawn_economics_setup
        from django.forms.models import model_to_dict
        series = LoanSeries.objects.create(license=self.license, name="WH", code="WH")
        saved = self.configuration(license=self.license, series=series,
            partial_month_method="STARTED_WEEKS", gold_monthly_interest_rate=Decimal("1.1"))
        path = f"/w/{self.tenant.slug}/loans/setup/economics/"
        request = RequestFactory().get(path, {"copy_economics": saved.economic_policy.pk})
        request.user, request.workspace, request.session = self.user, self.tenant, {}
        response = pawn_economics_setup(request)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="STARTED_WEEKS" selected')
        self.assertContains(response, 'value="ACTUAL_DAYS"')
        self.assertContains(response, 'value="1.100000"')
        self.assertContains(response, "Full first month minimum")
        values = model_to_dict(saved.economic_policy)
        values.update(gold_monthly_interest_rate="1.1", silver_monthly_interest_rate="4",
            effective_from="2026-09-30", effective_until="", partial_month_method="ACTUAL_DAYS")
        request = RequestFactory().post(path, {"action": "configuration",
            **{f"configuration-{k}": v for k, v in values.items() if v is not None}})
        request.user, request.workspace, request.session = self.user, self.tenant, {}
        request._messages = FallbackStorage(request)
        self.assertEqual(pawn_economics_setup(request).status_code, 302)
        latest = PawnLoanEconomicPolicy.objects.filter(series=series).order_by("-pk").first()
        self.assertEqual(latest.partial_month_method, "ACTUAL_DAYS")
        self.assertTrue(latest.minimum_first_month)


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PartialMonthLifecycleTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)
    make_loan = fixtures.CollateralReappraisalTests.make_loan

    def setUp(self):
        super().setUp()
        media = TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name)
        settings.enable()
        self.addCleanup(settings.disable)
        now = timezone.make_aware(datetime(2026, 8, 1, 10))
        clock = patch("django.utils.timezone.now", return_value=now)
        clock.start()
        self.addCleanup(clock.stop)

    def originate(self, *, method="STARTED_WEEKS", minimum=True, advance=1, activate=True):
        original = create_pawn_loan_economic_policy
        def create(**kwargs):
            return original(**(kwargs | dict(partial_month_method=method,
                minimum_first_month=minimum, advance_interest_periods=advance)))
        with patch.object(fixtures, "create_pawn_loan_economic_policy", side_effect=create):
            self.make_loan(method="LATEST_APPRAISAL", age_days=0, activate=activate)

    def test_approval_freezes_minimum_and_method_before_later_revision(self):
        from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan
        self.originate(activate=False)
        approval = approve_pawn_loan(self.loan.pk, actor=self.actor)
        self.assertTrue(approval.payload["collateral_economics"]["minimum_first_month"])
        create_pawn_loan_economic_policy(workspace=self.tenant, license=self.loan.license,
            valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal("0.8"),
            partial_month_method="ACTUAL_DAYS", actor=self.actor)
        result = disburse_pawn_loan(self.loan.pk, effective_date=self.today, actor=self.actor)
        self.assertEqual(result.policy_snapshot.partial_month_method, "STARTED_WEEKS")
        self.assertTrue(result.policy_snapshot.minimum_first_month)

    def test_first_month_advance_consumed_once_then_weekly_charge_and_finalization(self):
        from apps.tenant_apps.loans.services import preview_pawn_loan_accruals, finalize_pawn_loan_accrual
        self.originate()
        first = preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 8, 1))[0]
        self.assertEqual((first.calculated_interest, first.advance_interest_applied, first.recognized_interest),
                         (Decimal("20"), Decimal("20"), Decimal("0")))
        preview = preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 9, 8))
        self.assertEqual(preview[1].period_fraction, Decimal(7)/30)
        self.assertEqual(preview[1].recognized_interest, Decimal("4.67"))
        with patch("django.utils.timezone.now", return_value=timezone.make_aware(datetime(2026, 9, 8, 10))):
            finalized = finalize_pawn_loan_accrual(self.loan.pk, period_number=1, actor=self.actor)
        self.assertEqual(finalized.accrual.lines.get().advance_interest_applied, Decimal("20"))
        after = preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 9, 8))[0]
        self.assertEqual(after, preview[1])

    def test_early_release_charges_first_month_with_or_without_advance(self):
        from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release
        # A full month is due even when nothing was collected upfront.
        self.originate(advance=0)
        result = preview_pawn_loan_full_release(self.loan.pk, as_of_date=self.today)
        self.assertEqual(result.release_day_accrual.period_fraction, 1)
        self.assertEqual(result.release_day_catch_up_interest, Decimal("20"))

    def test_legacy_half_month_policy_and_daily_policy_are_independent(self):
        from apps.tenant_apps.loans.services import preview_pawn_loan_accruals
        self.originate(method="SLAB", minimum=False, advance=0)
        legacy = self.loan
        old = preview_pawn_loan_accruals(legacy.pk, as_of_date=self.today)[0]
        self.assertEqual(old.recognized_interest, Decimal("10"))
        create_pawn_loan_economic_policy(workspace=self.tenant, license=legacy.license,
            valuation_method="LATEST_APPRAISAL", maximum_ltv_ratio=Decimal("0.8"),
            partial_month_method="ACTUAL_DAYS", actor=self.actor)
        self.assertEqual(preview_pawn_loan_accruals(legacy.pk, as_of_date=self.today)[0], old)

    def test_daily_proration_after_first_month(self):
        from apps.tenant_apps.loans.services import preview_pawn_loan_accruals
        self.originate(method="ACTUAL_DAYS", advance=0)
        periods = preview_pawn_loan_accruals(self.loan.pk, as_of_date=date(2026, 9, 8))
        self.assertEqual(periods[0].recognized_interest, Decimal("20"))
        self.assertEqual(periods[1].recognized_interest, Decimal("4.67"))

    def test_weekly_release_persists_exact_event_and_retries_without_double_charge(self):
        from apps.tenant_apps.loans.models import LoanNumberSequence
        from apps.tenant_apps.loans.services import finalize_pawn_loan_accrual, release_pawn_loan_in_full
        from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release
        self.originate()
        LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE",
            prefix="REL-", width=5, maximum_number=10000)
        with patch("django.utils.timezone.now", return_value=timezone.make_aware(datetime(2026, 9, 8, 10))):
            finalize_pawn_loan_accrual(self.loan.pk, period_number=1, actor=self.actor)
            preview = preview_pawn_loan_full_release(self.loan.pk)
            self.assertEqual(preview.release_day_catch_up_interest, Decimal("4.67"))
            result = release_pawn_loan_in_full(self.loan.pk, settlement_amount="1004.67",
                request_key="weekly-close", actor=self.actor)
            again = release_pawn_loan_in_full(self.loan.pk, settlement_amount="1004.67",
                request_key="weekly-close", actor=self.actor)
        self.assertEqual(result.loan_event.pk, again.loan_event.pk)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "CLOSED")
        self.assertEqual(self.loan.interest_accruals.count(), 2)
        catch_up = self.loan.interest_accruals.get(period_number=2)
        self.assertEqual(catch_up.recognized_interest, Decimal("4.67"))
        self.assertEqual(Decimal(catch_up.loan_event.payload["accrual"]["period_fraction"]), Decimal(7)/30)
