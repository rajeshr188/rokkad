import copy
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import override_settings
from django.urls import reverse

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import workspace_role_permissions

from apps.tenant_apps.loans.models import LoanPolicySnapshot, LoanNumberSequence, PawnLoanEvent, PawnLoanRelease, CollateralAppraisal
from apps.tenant_apps.loans.services.opening_obligations import persist_opening_repayment_schedule
from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full
from apps.tenant_apps.loans.services.pawn_reversal import reverse_pawn_loan_event
from apps.tenant_apps.loans.services.pawn_interest import finalize_pawn_loan_accrual
from apps.tenant_apps.loans.services.event_recording import record_loan_event, LoanEventRecordingError
from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure
from apps.tenant_apps.loans.selectors.obligation_state import get_active_repayment_schedule_as_of
from apps.tenant_apps.loans.tests.test_opening_continuation import collection_review
from apps.tenant_apps.loans.tests.test_opening_event_storage import OpeningEventFixture


class OpeningReleaseFixture(OpeningEventFixture):
    release_day = date(2021, 2, 2)
    def review_document(self):
        doc = collection_review()
        doc["obligations"][0]["interest"] = "0"
        return doc

    def setUp(self):
        super().setUp()
        self.day = self.release_day
        self.enterContext(patch("django.utils.timezone.localdate", side_effect=lambda *a, **kw: self.day))
        LoanPolicySnapshot.objects.create(loan=self.loan, interest_method="SIMPLE", partial_month_method="FULL_MONTH",
            valuation_method="LATEST_APPRAISAL", rounding_method="PER_ACCRUAL_PERIOD")
        CollateralAppraisal.objects.create(workspace=self.tenant, collateral_item=self.item, version=1,
            effective_at=datetime(2021, 1, 20, tzinfo=timezone.utc), appraised_value=2000,
            method="MIGRATION_REVIEW", evidence_reference="Synthetic cutover appraisal", created_by=self.actor)
        LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE",
            prefix="OR-", width=5, maximum_number=10000)
        self.schedule = persist_opening_repayment_schedule(self.loan.pk, actor=self.actor)

    def release(self, **kwargs):
        quote = preview_pawn_loan_full_release(self.loan.pk)
        values = dict(settlement_amount=quote.minimum_settlement, request_key="opening-release", actor=self.actor)
        values.update(kwargs)
        return release_pawn_loan_in_full(self.loan.pk, **values)


class OpeningReleaseTests(OpeningReleaseFixture):

    def test_full_release_posts_only_new_interest_and_closes_every_item(self):
        quote = preview_pawn_loan_full_release(self.loan.pk)
        self.assertEqual(quote.minimum_settlement, 1010)
        self.assertEqual(PawnLoanEvent.objects.count(), 1)
        result = self.release()
        self.assertEqual(result.release.interest_amount, 10)
        self.assertEqual(Decimal(result.loan_event.payload["release"]["unscheduled_interest_paid"]), 10)
        self.assertEqual(result.release.catch_up_accrual.recognized_interest, 10)
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=self.day)
        self.assertTrue(balance.closure_ready)
        self.assertEqual((balance.principal_disbursed, balance.opening_principal, balance.interest_accrued), (0, 1000, 10))
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan)[0].principal_outstanding, 0)
        self.assertIsNone(get_active_repayment_schedule_as_of(self.loan, self.day))
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2021, 5, 1)).total_economic_exposure, 0)
        self.assertEqual(self.loan.loan_events.count(), 3)
        from apps.tenant_apps.loans.services.history_export import export_history
        with self.assertRaisesMessage(ValueError, "require an opening-aware export"):
            export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=self.loan.pk)

    def test_release_concession_and_coupled_reversal_then_release_again(self):
        result = self.release(settlement_amount=1005, interest_concession=5, concession_reason="Accepted shortfall")
        frozen = copy.deepcopy(result.loan_event.payload)
        self.assertEqual(get_pawn_loan_balance(self.loan.pk, as_of_date=self.day).interest_conceded, 5)
        with self.assertRaisesMessage(ValueError, "only be reversed with"):
            reverse_pawn_loan_event(result.release.catch_up_accrual.loan_event_id, actor=self.actor, reason="Wrong standalone correction")
        self.day = date(2021, 2, 3)
        reversed_result = reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Return cancelled")
        self.assertIsNotNone(reversed_result.catch_up_reversal_event)
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=self.day)
        self.assertEqual((balance.principal_outstanding, balance.interest_outstanding, balance.interest_conceded), (1000, 0, 0))
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan, as_of_date=date(2021, 2, 2))[0].principal_outstanding, 0)
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan)[0].principal_outstanding, 1000)
        self.assertEqual(get_active_repayment_schedule_as_of(self.loan, self.day).pk, self.schedule.pk)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2021, 2, 2)).total_economic_exposure, 0)
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.day).total_economic_exposure, 1010)
        result.loan_event.refresh_from_db()
        self.assertEqual(result.loan_event.payload, frozen)
        self.assertTrue(reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Return cancelled").already_reversed)
        again = self.release(request_key="opening-second-release")
        self.assertEqual(again.release.catch_up_accrual.period_number, 2)
        self.assertTrue(get_pawn_loan_balance(self.loan.pk, as_of_date=self.day).closure_ready)

    def test_first_month_release_does_not_recharge_advance_interest(self):
        self.day = date(2021, 1, 21)
        result = self.release()
        self.assertEqual(result.release.settlement_amount, 1000)
        self.assertIsNone(result.release.catch_up_accrual)
        reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Cancelled")
        self.assertEqual(get_pawn_loan_balance(self.loan.pk, as_of_date=self.day).total_due, 1000)

    def test_retry_reauthorizes_and_conflicting_cash_is_rejected(self):
        result = self.release()
        kwargs = dict(settlement_amount=1010, request_key="opening-release", actor=self.actor)
        self.assertTrue(release_pawn_loan_in_full(self.loan.pk, **kwargs).already_released)
        with self.assertRaises(PermissionDenied):
            release_pawn_loan_in_full(self.loan.pk, **{**kwargs, "actor": None})
        with self.assertRaises(ValueError):
            release_pawn_loan_in_full(self.loan.pk, **{**kwargs, "settlement_amount": 1000})
        self.assertEqual(PawnLoanRelease.objects.count(), 1)
        self.assertEqual(result.loan_event.pk, PawnLoanRelease.objects.get().loan_event_id)

    def test_failure_after_interest_post_rolls_back_interest_receipt_and_counter(self):
        counter = LoanNumberSequence.objects.get(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE")
        before = copy.deepcopy(counter.__dict__)
        with patch("apps.tenant_apps.loans.services.pawn_release.remove_collateral_from_storage", side_effect=RuntimeError("synthetic custody failure")):
            with self.assertRaisesMessage(RuntimeError, "synthetic custody failure"):
                self.release()
        self.assertEqual(self.loan.loan_events.count(), 1)
        self.assertFalse(self.loan.interest_accruals.exists())
        self.assertFalse(self.loan.releases.exists())
        counter.refresh_from_db()
        for key in before:
            if not key.startswith("_"):
                self.assertEqual(getattr(counter, key), before[key])
        self.assertEqual(get_active_repayment_schedule_as_of(self.loan, self.day).pk, self.schedule.pk)

    def test_cutover_native_accrual_and_generic_posting_remain_blocked(self):
        self.day = date(2021, 1, 20)
        with self.assertRaisesMessage(ValueError, "after cutover"):
            self.release()
        self.day = date(2021, 2, 2)
        with self.assertRaises(ValueError):
            finalize_pawn_loan_accrual(self.loan.pk, period_number=1, actor=self.actor)
        with self.assertRaises(LoanEventRecordingError):
            record_loan_event(self.loan.pk, event_kind="REPAYMENT", effective_date=self.day, payload={"values": {"principal": "100"}}, actor=self.actor)
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_failed_coupled_reversal_rolls_back_both_events_and_schedule_reactivation(self):
        result = self.release()
        with patch("apps.tenant_apps.loans.services.pawn_reversal._restore_release_custody", side_effect=RuntimeError("synthetic reversal failure")):
            with self.assertRaisesMessage(RuntimeError, "synthetic reversal failure"):
                reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Cancelled")
        self.assertEqual(self.loan.loan_events.count(), 3)
        self.assertFalse(self.loan.loan_events.filter(event_kind="REVERSAL").exists())
        self.assertIsNone(get_active_repayment_schedule_as_of(self.loan, self.day))
        self.assertTrue(get_pawn_loan_balance(self.loan.pk, as_of_date=self.day).closure_ready)

    def test_release_staff_cannot_grant_concession_or_reverse_or_cross_workspace(self):
        user = get_user_model().objects.create_user(username="opening-release-staff")
        role = Role.objects.create(name="Opening release staff")
        Membership.objects.create(company=self.tenant, user=user, role=role)
        workspace_role_permissions(role, self.tenant).set(Permission.objects.filter(
            content_type__app_label="orgs", content_type__model="company", codename__in=["data_view", "loan_release"]))
        with self.assertRaises(PermissionDenied):
            self.release(actor=user, settlement_amount=1005, interest_concession=5, concession_reason="Not authorized")
        other = Company.objects.create(name="Other", schema_name="opening-release-other", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises(ValueError):
            self.release()
        result = self.release(actor=user)
        with self.assertRaisesMessage(ValueError, "requires an administrator"):
            reverse_pawn_loan_event(result.loan_event.pk, actor=user, reason="Not authorized")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    })
    def test_existing_full_release_form_and_closed_detail_support_opening(self):
        self.start_active_trial()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_release_full", kwargs={"workspace_slug": self.tenant.slug, "pk": self.loan.pk})
        detail = client.get(reverse("workspace_loans:pawn_loan_detail", kwargs={"workspace_slug": self.tenant.slug, "pk": self.loan.pk}))
        self.assertContains(detail, "Collect and release")
        self.assertNotContains(detail, reverse("workspace_loans:pawn_loan_auction_initiate", kwargs={"workspace_slug": self.tenant.slug, "pk": self.loan.pk}))
        self.assertContains(client.get(url), "1010.00")
        response = client.post(url, {"settlement_amount": "1010", "request_key": "http-opening-release", "confirm_collateral_handoff": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get(response.url), "Collection catch-up")


class OpeningCoveredReleaseTests(OpeningReleaseFixture):
    release_day = date(2021, 4, 2)

    def review_document(self):
        doc = collection_review(cutover=date(2021, 3, 15), unpaid="15")
        doc["balances"]["fees"] = "5"
        return doc

    def test_opening_unpaid_interest_and_fees_are_settled_without_recharging_covered_baseline(self):
        self.assertEqual(preview_pawn_loan_full_release(self.loan.pk).minimum_settlement, 1030)
        result = self.release(settlement_amount=1025, interest_concession=5, concession_reason="Accepted shortfall")
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=self.day)
        self.assertEqual((balance.opening_interest, balance.interest_accrued, balance.interest_paid, balance.interest_conceded, balance.fees_paid), (15, 10, 20, 5, 5))
        self.assertTrue(balance.closure_ready)
        reverse_pawn_loan_event(result.loan_event.pk, actor=self.actor, reason="Cancelled")
        balance = get_pawn_loan_balance(self.loan.pk, as_of_date=self.day)
        self.assertEqual((balance.total_due, balance.interest_outstanding, balance.fees_outstanding), (1020, 15, 5))


class OpeningRoundedReleaseTests(OpeningReleaseFixture):
    release_day = date(2021, 4, 2)

    def review_document(self):
        return collection_review(cutover=date(2021, 2, 2), rate="14.82")

    def test_posted_catch_up_preserves_cumulative_rounding_across_cutover(self):
        result = self.release()
        catch_up = result.release.catch_up_accrual
        self.assertEqual((catch_up.unrounded_interest, catch_up.recognized_interest), (Decimal("296.4"), 297))
        self.assertEqual(result.release.settlement_amount, 1445)
        self.assertEqual(catch_up.loan_event.payload["opening_collection"]["baseline_as_of"], "445")
        self.assertEqual(get_pawn_loan_exposure(self.loan.pk, as_of_date=self.day).total_economic_exposure, 0)
