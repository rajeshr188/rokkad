"""LC-06 prospective eligibility, immutable reviews and owner configuration."""
from copy import deepcopy
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction, DatabaseError
from django.test import RequestFactory, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.configuration.models import PreferenceAuditLog
from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import LoanOriginationSettings, PawnLoan, LoanMonitoringPolicy
from apps.tenant_apps.loans.selectors.origination_rates import get_origination_quote_rows, LEGACY_RULE, RULE
from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan
from apps.tenant_apps.loans.services.loan_workflow import make_review, review_and_disburse
from apps.tenant_apps.loans.services.origination_settings import maximum_quote_age_days, set_maximum_quote_age
from apps.tenant_apps.loans.tests import test_origination_rates as fixtures
from apps.tenant_apps.rates.services import withdraw_quote


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class QuoteAgeTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.OriginationRateTests.setup_tenant.__func__)
    make_loan = fixtures.OriginationRateTests.make_loan
    setUp = fixtures.OriginationRateTests.setUp
    approve = fixtures.OriginationRateTests.approve
    disburse = fixtures.OriginationRateTests.disburse
    new_quote = fixtures.OriginationRateTests.new_quote

    @classmethod
    def get_test_schema_name(cls):
        return "quote-age-lc06"

    def limit(self, days):
        return set_maximum_quote_age(workspace=self.tenant, days=days, actor=self.actor)

    def rows(self, **changes):
        return get_origination_quote_rows(workspace_id=self.tenant.pk,
            loan_date=self.today, metals=("GOLD",), **changes)

    def aged_quote(self, days):
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=self.quote.pk, reason="Replace test source")
        self.quote = self.new_quote(effective_at=timezone.now() - timedelta(days=days))
        return self.quote

    def test_missing_setting_defaults_to_seven_without_a_write_and_zero_is_preserved(self):
        self.assertFalse(LoanOriginationSettings.objects.exists())
        self.assertEqual(maximum_quote_age_days(self.tenant.pk), 7)
        self.assertEqual(self.rows()[0]["maximum_age_days"], 7)
        self.assertFalse(LoanOriginationSettings.objects.exists())
        self.limit(0)
        self.assertEqual(maximum_quote_age_days(self.tenant.pk), 0)

    def test_seven_day_quote_is_approved_and_paid_with_applied_evidence(self):
        quote = self.aged_quote(7)
        approval = self.approve()
        evidence = deepcopy(approval.payload["origination_rates"])
        self.assertEqual(evidence["rule"], RULE)
        self.assertEqual(evidence["maximum_quote_age_days"], 7)
        self.assertEqual(evidence["age_basis"], "LOCAL_CALENDAR_DAYS")
        self.assertEqual(evidence["quote_ages_days"], {"GOLD": 7})
        self.assertEqual(evidence["quotes"]["GOLD"]["rate_id"], quote.pk)
        self.assertEqual(evidence["quotes"]["GOLD"]["source_snapshot"]["name"], "Market")
        self.assertNotIn("maximum_quote_age_days", evidence["quotes"]["GOLD"])
        self.assertFalse(self.disburse().already_disbursed)
        approval.refresh_from_db()
        self.assertEqual(approval.payload["origination_rates"], evidence)

    def test_eight_day_quote_cannot_create_approval_or_appraisals(self):
        self.aged_quote(8)
        with self.assertRaisesMessage(ValueError, "no older than 7 calendar days"):
            self.approve()
        self.assertFalse(self.loan.approval_snapshots.exists())
        self.assertFalse(self.item.appraisals.exists())
        self.assertFalse(self.loan.loan_events.exists())

    def test_owner_can_extend_or_tighten_inclusive_age_limit(self):
        self.aged_quote(8)
        self.limit(8)
        self.assertTrue(self.rows()[0]["fresh"])
        self.limit(7)
        self.assertFalse(self.rows()[0]["fresh"])
        self.limit(0)
        self.assertFalse(self.rows()[0]["fresh"])
        self.new_quote()
        self.assertTrue(self.rows()[0]["fresh"])

    def test_seven_day_limit_expires_at_local_midnight(self):
        with timezone.override("Asia/Kolkata"):
            midnight = timezone.make_aware(datetime.combine(timezone.localdate(self.quote.effective_at)
                + timedelta(days=8), datetime.min.time()))
            before = self.rows(at=midnight - timedelta(seconds=1))[0]
            after = self.rows(at=midnight)[0]
        self.assertEqual((before["age_days"], before["fresh"]), (7, True))
        self.assertEqual((after["age_days"], after["fresh"]), (8, False))

    def test_latest_quote_identity_wins_even_when_older_quote_remains_eligible(self):
        first = self.aged_quote(7)
        latest = self.new_quote(effective_at=timezone.now() - timedelta(days=2), buying_rate=3200)
        future = self.new_quote(effective_at=timezone.now() + timedelta(hours=1), buying_rate=9000)
        row = self.rows()[0]
        self.assertEqual(row["rate"].pk, latest.pk)
        self.assertEqual(row["age_days"], 2)
        self.assertNotIn(row["rate"].pk, (first.pk, future.pk))

    def test_each_required_metal_must_meet_age_limit(self):
        from apps.tenant_apps.loans.selectors.origination_rates import require_fresh_quotes
        self.new_quote(metal="Silver", effective_at=timezone.now() - timedelta(days=8))
        rows = get_origination_quote_rows(workspace_id=self.tenant.pk, loan_date=self.today,
            metals=("GOLD", "SILVER"))
        self.assertEqual([row["fresh"] for row in rows], [True, False])
        with self.assertRaisesMessage(ValueError, "Silver requires"):
            require_fresh_quotes(rows)
        self.assertFalse(self.loan.approval_snapshots.exists())

    def test_setting_write_is_audited_and_rejects_invalid_values(self):
        self.limit(3)
        audit = PreferenceAuditLog.objects.get(workspace=self.tenant, key="loans.maximum_quote_age_days")
        self.assertEqual((audit.old_value, audit.new_value, audit.changed_by_id), ("7", "3", self.actor.pk))
        for invalid in (-1, 32768, True, None, "7", Decimal("7")):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                self.limit(invalid)
        self.assertEqual(maximum_quote_age_days(self.tenant.pk), 3)
        self.assertEqual(PreferenceAuditLog.objects.filter(key="loans.maximum_quote_age_days").count(), 1)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls")
    def test_setup_admin_cannot_change_owner_limit_or_post_it(self):
        self.start_active_trial()
        from apps.tenant_apps.loans.services.origination_settings import set_collateral_photo_requirement
        admin = get_user_model().objects.create_user(username="quote-age-admin")
        Membership.objects.create(user=admin, company=self.tenant, role=Role.objects.get_or_create(name="Admin")[0])
        # Existing photo administration is still available to this role.
        set_collateral_photo_requirement(workspace=self.tenant, required=True, actor=admin)
        with self.assertRaises(PermissionDenied):
            set_maximum_quote_age(workspace=self.tenant, days=30, actor=admin)
        client = self.make_workspace_client()
        client.force_login(admin)
        url = reverse("workspace_loans:origination_settings", args=[self.tenant.slug])
        page = client.get(url)
        self.assertContains(page, "Only the Workspace owner can change this limit")
        self.assertNotContains(page, "Save quote-age limit")
        self.assertEqual(client.post(url, {"action": "quote_age", "maximum_quote_age_days": 30}).status_code, 403)
        self.assertEqual(maximum_quote_age_days(self.tenant.pk), 7)

    @override_settings(ROOT_URLCONF="django_project.workspace_urls")
    def test_owner_form_can_save_zero_and_invalid_submission_cannot_change_photos(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:origination_settings", args=[self.tenant.slug])
        self.assertContains(client.get(url), "Save quote-age limit")
        self.assertEqual(client.post(url, {"action": "quote_age", "maximum_quote_age_days": 0}).status_code, 302)
        self.assertContains(client.get(url), "no older than 0 calendar days")
        page = client.post(url, {"action": "quote_age", "maximum_quote_age_days": -1, "require_collateral_photos": "on"})
        self.assertEqual(page.status_code, 200)
        self.assertEqual(maximum_quote_age_days(self.tenant.pk), 0)
        self.assertFalse(LoanOriginationSettings.objects.get().require_collateral_photos)

    def test_setting_change_invalidates_simple_review_even_if_quote_still_eligible(self):
        self.tenant.loan_workflow = "SIMPLE"
        self.tenant.save(update_fields=["loan_workflow"])
        _, token = make_review(self.loan)
        self.limit(8)
        with self.assertRaisesMessage(ValueError, "changed"):
            review_and_disburse(self.loan.pk, actor=self.actor, token=token, effective_date=self.today)
        self.assertFalse(self.loan.approval_snapshots.exists())
        self.assertFalse(self.loan.loan_events.exists())

    def test_setting_change_invalidates_unpaid_approval_and_paid_retry_keeps_original(self):
        approval = self.approve()
        frozen = deepcopy(approval.payload)
        self.limit(8)
        with self.assertRaisesMessage(ValueError, "Return to draft"):
            self.disburse()
        self.assertFalse(self.loan.loan_events.exists())
        # Restoring the exact approved setting makes the same identities valid.
        self.limit(7)
        self.disburse()
        self.limit(0)
        self.assertTrue(self.disburse().already_disbursed)
        approval.refresh_from_db()
        self.assertEqual(approval.payload, frozen)

    def test_setting_change_during_approval_rolls_back_all_evidence(self):
        from apps.tenant_apps.loans.services import pawn_lifecycle
        original = pawn_lifecycle._freeze_approved_appraisals
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.limit(8)
            return result
        with patch.object(pawn_lifecycle, "_freeze_approved_appraisals", side_effect=changed):
            with self.assertRaisesMessage(ValueError, "Return to draft"):
                self.approve()
        self.assertFalse(self.loan.approval_snapshots.exists())
        self.assertFalse(self.item.appraisals.exists())
        self.assertEqual(maximum_quote_age_days(self.tenant.pk), 7)

    def test_setting_change_during_payout_rolls_back_financial_records(self):
        from apps.tenant_apps.loans.services import pawn_disbursal
        self.approve()
        original = pawn_disbursal.persist_disbursal_repayment_schedule
        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            self.limit(8)
            return result
        with patch.object(pawn_disbursal, "persist_disbursal_repayment_schedule", side_effect=changed):
            with self.assertRaisesMessage(ValueError, "Return to draft"):
                self.disburse()
        self.assertFalse(self.loan.loan_events.exists())
        self.assertFalse(self.loan.repayment_schedules.exists())
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "APPROVED")

    def test_legacy_approval_keeps_same_day_meaning_without_rewriting(self):
        from apps.tenant_apps.loans.services import pawn_lifecycle
        original = pawn_lifecycle.approval_quote_evidence
        def legacy(*args):
            evidence = original(*args)
            evidence["rule"] = LEGACY_RULE
            for key in ("maximum_quote_age_days", "age_basis", "quote_ages_days"):
                evidence.pop(key, None)
            return evidence
        with patch.object(pawn_lifecycle, "approval_quote_evidence", side_effect=legacy):
            approval = self.approve()
        from apps.tenant_apps.loans.web.pawn_reads import pawn_loan_detail
        request = RequestFactory().get("/")
        request.workspace, request.user = self.tenant, self.actor
        self.assertContains(pawn_loan_detail(request, self.loan.pk), "Applied approval limit: 0 calendar days")
        self.limit(30)
        frozen = deepcopy(approval.payload)
        self.disburse()
        approval.refresh_from_db()
        self.assertEqual(approval.payload, frozen)

    def test_monitoring_limit_remains_independent_and_reads_do_not_post(self):
        from apps.tenant_apps.loans.selectors.collateral_valuation import get_pawn_loan_collateral_valuation
        self.aged_quote(7)
        self.approve(); self.disburse()
        values = {f.attname: getattr(self.policy, f.attname) for f in self.policy._meta.concrete_fields
            if f.attname not in {"id", "created_at", "version"}}
        values.update(version=2, supersedes_id=self.policy.pk, amendment_reason="Monitoring needs today's price", rate_freshness_days=0)
        LoanMonitoringPolicy.objects.create(**values)
        count = self.loan.loan_events.count()
        before = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today)
        self.assertIn("STALE_RATE", before.items[0].blockers)
        self.limit(30)
        after = get_pawn_loan_collateral_valuation(self.loan.pk, as_of_date=self.today)
        self.assertEqual(before, after)
        self.assertEqual(self.loan.loan_events.count(), count)

    def test_legacy_rule_cannot_borrow_the_new_seven_day_allowance(self):
        from apps.tenant_apps.loans.selectors.origination_rates import assert_approved_quotes_current
        self.aged_quote(1)
        evidence = {"rule": LEGACY_RULE, "valuation_method": "LOWER_OF_CALCULATED_AND_APPRAISAL",
            "loan_date": self.today.isoformat(), "quotes": {"GOLD": self.rows()[0]["evidence"]}}
        with self.assertRaisesMessage(ValueError, "Return to draft"):
            assert_approved_quotes_current(workspace_id=self.tenant.pk,
                method=evidence["valuation_method"], evidence=evidence, effective_date=self.today)

    def test_malformed_new_age_evidence_cannot_authorize_payout(self):
        from apps.tenant_apps.loans.selectors.origination_rates import assert_approved_quotes_current
        approval = self.approve()
        original = approval.payload["origination_rates"]
        for malformed in ({}, {"GOLD": True}, {"GOLD": -1}, {"GOLD": 8}, {"GOLD": 1}):
            evidence = dict(original, quote_ages_days=malformed)
            with self.subTest(ages=malformed), self.assertRaisesMessage(ValueError, "quote-age evidence"):
                assert_approved_quotes_current(workspace_id=self.tenant.pk,
                    method=evidence["valuation_method"], evidence=evidence, effective_date=self.today)
        self.assertFalse(self.loan.loan_events.exists())

    def test_setting_change_invalidates_updated_valuation_review(self):
        from apps.tenant_apps.loans.services.valuation_review import preview_updated_valuation, confirm_updated_valuation
        self.approve()
        self.loan.refresh_from_db()
        preview = preview_updated_valuation(self.loan, actor=self.actor)
        self.limit(8)
        with self.assertRaisesMessage(ValueError, "changed"):
            confirm_updated_valuation(self.loan.pk, actor=self.actor, token=preview["token"], unpaid=True)
        self.assertEqual(self.loan.approval_snapshots.count(), 1)
        self.assertFalse(self.loan.loan_events.exists())

    def test_retained_historical_payout_review_does_not_depend_on_current_age_setting(self):
        from apps.tenant_apps.loans.services import reopen_pawn_loan
        from apps.tenant_apps.loans.services.loan_workflow import make_earlier_payout_review, record_earlier_payout
        approval = self.approve()
        original = deepcopy(approval.payload)
        reopen_pawn_loan(self.loan.pk, actor=self.actor, reason="Record actual earlier payout")
        self.loan.refresh_from_db()
        tomorrow = timezone.now() + timedelta(days=1)
        with patch("django.utils.timezone.now", return_value=tomorrow):
            _, token, _, _ = make_earlier_payout_review(self.loan, actor=self.actor)
            self.limit(0)
            result = record_earlier_payout(self.loan.pk, actor=self.actor, token=token,
                reason="Original approved ticket already paid", confirmed=True)
        self.assertEqual(result.loan_event.effective_date, self.today)
        latest = result.loan.approval_snapshots.latest("version").payload["origination_rates"]
        self.assertEqual(latest["rule"], "earlier-payout-v1")
        self.assertNotIn("maximum_quote_age_days", latest)
        approval.refresh_from_db()
        self.assertEqual(approval.payload, original)

    def test_quote_guidance_shows_source_age_limit_and_approval_displays_frozen_age(self):
        from apps.tenant_apps.loans.web.rate_readiness import pawn_valuation_readiness
        from apps.tenant_apps.loans.web.pawn_reads import pawn_loan_detail
        self.aged_quote(7)
        request = RequestFactory().get("/", {"series": self.loan.series_id, "as_of": self.today,
            "metals": "GOLD", "request_key": 1})
        request.workspace, request.user = self.tenant, self.actor
        page = pawn_valuation_readiness(request)
        for text in ("7 calendar days old", "limit 7", "Market", f"Quote #{self.quote.pk}", "Within approval age limit"):
            self.assertContains(page, text)
        self.approve()
        self.assertContains(pawn_loan_detail(request, self.loan.pk), "7 calendar days old at approval")
        self.assertFalse(self.loan.loan_events.exists())

    def test_renewal_owner_limit_change_invalidates_review_without_partial_successor(self):
        from apps.tenant_apps.loans.services.pawn_renewals import RetainedCollateralInput, preview_pawn_loan_renewal_plan, renew_pawn_loan
        self.approve(); self.disburse()
        values = dict(mode="PAY_AND_RENEW", principal_paid=Decimal(0), top_up_amount=Decimal(0),
            successor_license_id=self.loan.license_id, successor_series_id=self.loan.series_id, tenure_months=12,
            retained_collateral=(RetainedCollateralInput(self.item.pk, Decimal(1000)),))
        preview = preview_pawn_loan_renewal_plan(self.loan.pk, **values)
        count = PawnLoan.objects.count()
        self.limit(8)
        with self.assertRaisesMessage(ValueError, "changed"):
            renew_pawn_loan(self.loan.pk, **values, renewal_date=self.today, request_key="age-renewal",
                actor=self.actor, expected_preview_fingerprint=preview.fingerprint)
        self.assertEqual(PawnLoan.objects.count(), count)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")

    def test_restricted_settings_rls_and_database_range_checks(self):
        self.limit(7)
        other = Company.objects.create(name="Other quote owner", schema_name="quote-other", owner=self.actor, creator=self.actor)
        with self.assertRaises(PermissionDenied):
            maximum_quote_age_days(other.pk)
        role = connection.ops.quote_name("quote_age_rls_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, UPDATE ON loans_loanoriginationsettings TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid='loans_loanoriginationsettings'::regclass")
                self.assertEqual(cursor.fetchone(), (True, True))
            self.assertEqual(LoanOriginationSettings.objects.get().maximum_quote_age_days, 7)
            for invalid in (-1, 32768):
                with self.subTest(value=invalid), self.assertRaises(DatabaseError), transaction.atomic():
                    LoanOriginationSettings.objects.update(maximum_quote_age_days=invalid)
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(LoanOriginationSettings.objects.filter(workspace_id=self.tenant.pk).exists())
                self.assertEqual(LoanOriginationSettings.objects.filter(workspace_id=self.tenant.pk).update(maximum_quote_age_days=30), 0)
            with without_workspace_context():
                self.assertFalse(LoanOriginationSettings.objects.exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
