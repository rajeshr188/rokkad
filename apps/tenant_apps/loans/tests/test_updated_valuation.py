from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.db import connection, connections, transaction
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.loans.models import LoanNumberSequence
from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan
from apps.tenant_apps.loans.services.valuation_review import (
    preview_updated_valuation, confirm_updated_valuation, valuation_refresh_reason,
)
from apps.tenant_apps.rates.models import Rate


@override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class UpdatedValuationTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)
    make_loan = fixtures.CollateralReappraisalTests.make_loan

    @classmethod
    def get_test_schema_name(cls):
        return "updated-valuation"

    def setUp(self):
        self.make_loan(age_days=0, activate=False)
        self.original = approve_pawn_loan(self.loan.pk, actor=self.actor)
        self.loan.refresh_from_db()
        self.previous_date = self.loan.loan_date
        self.now = timezone.now() + timedelta(days=1)
        self.clock = patch("django.utils.timezone.now", return_value=self.now)
        self.clock.start()
        self.addCleanup(self.clock.stop)
        self.current = Rate.objects.create(rate_source=self.source, effective_at=timezone.now(), buying_rate=1800, selling_rate=1900)
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.actor)
        self.url = reverse("loans:pawn_loan_review_updated_valuation", args=[self.loan.pk])

    def review(self):
        self.loan.refresh_from_db()
        return preview_updated_valuation(self.loan, actor=self.actor)

    def confirm(self, token, **changes):
        values = dict(actor=self.actor, token=token, unpaid=True)
        values.update(changes)
        return confirm_updated_valuation(self.loan.pk, **values)

    def test_review_is_read_only_and_compares_prices_limits_dates_and_cash(self):
        before = deepcopy(self.original.payload)
        photos = list(self.item.photos.values())
        review = self.review()
        self.assertEqual(review["quotes"][0]["old"]["buying_rate"], "3000.00")
        self.assertEqual(review["quotes"][0]["current"]["buying_rate"], "1800.00")
        self.assertEqual(review["item_rows"][0]["old"]["maximum_principal"], "1600.00")
        self.assertEqual(review["resolved"].economics.tranches[0].maximum_principal, Decimal("1440"))
        self.assertEqual(review["totals"][0]["old"], "1000.00")
        self.assertTrue(review["token"])
        response = self.client.get(self.url)
        self.assertContains(response, "3,000")
        self.assertContains(response, "1,800")
        self.assertContains(response, "No cash has been paid")
        self.assertContains(response, "Confirm updated approval")
        self.assertContains(response, self.previous_date.strftime("%d/%m/%Y"))
        self.assertContains(response, timezone.localdate().strftime("%d/%m/%Y"))
        self.assertEqual(self.loan.approval_snapshots.count(), 1)
        self.assertFalse(self.loan.loan_events.exists())
        self.assertEqual(list(self.item.photos.values()), photos)
        self.original.refresh_from_db()
        self.assertEqual(self.original.payload, before)

    def test_confirmation_reapproves_same_number_and_keeps_disbursal_separate(self):
        before = deepcopy(self.original.payload)
        number = self.loan.loan_number
        sequence = LoanNumberSequence.objects.get(series=self.loan.series, document_kind="PAWN_LOAN").next_number
        photos = list(self.item.photos.values())
        token = self.review()["token"]
        loan, changed = self.confirm(token)
        self.assertTrue(changed)
        self.assertEqual(loan.state, "APPROVED")
        self.assertEqual(loan.loan_date, timezone.localdate())
        self.assertEqual(loan.loan_number, number)
        self.assertEqual(loan.approval_snapshots.count(), 2)
        self.assertFalse(loan.loan_events.exists())
        self.assertEqual(list(self.item.photos.values()), photos)
        self.assertEqual(LoanNumberSequence.objects.get(series=loan.series, document_kind="PAWN_LOAN").next_number, sequence)
        approval = loan.approval_snapshots.latest("version")
        self.assertEqual(approval.approved_by, self.actor)
        self.assertEqual(approval.payload["valuation_review"]["previous_approval_id"], self.original.pk)
        self.assertEqual(approval.payload["origination_rates"]["quotes"]["GOLD"]["rate_id"], self.current.pk)
        self.original.refresh_from_db()
        self.assertEqual(self.original.payload, before)
        self.assertFalse(self.confirm(token)[1])
        disburse_pawn_loan(loan.pk, actor=self.actor, effective_date=timezone.localdate())
        self.assertFalse(self.confirm(token)[1])
        self.assertEqual(loan.loan_events.count(), 1)
        self.assertEqual(loan.approval_snapshots.count(), 2)

    def test_changed_price_or_terms_or_day_rejects_stale_confirmation(self):
        token = self.review()["token"]
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(seconds=1)):
            Rate.objects.create(rate_source=self.source, effective_at=timezone.now(), buying_rate=1900, selling_rate=2000)
            with self.assertRaisesMessage(ValueError, "changed"):
                self.confirm(token)
        token = self.review()["token"]
        self.loan.tenure_months = 10
        self.loan.save(update_fields=["tenure_months"])
        with self.assertRaisesMessage(ValueError, "changed"):
            self.confirm(token)
        token = self.review()["token"]
        with patch("django.utils.timezone.localdate", return_value=timezone.localdate() + timedelta(days=1)):
            with self.assertRaisesMessage(ValueError, "day changed"):
                self.confirm(token)
        self.assertEqual(self.loan.approval_snapshots.count(), 1)

    def test_missing_prices_and_excess_ltv_never_change_approval(self):
        token = self.review()["token"]
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(seconds=1)):
            Rate.objects.create(rate_source=self.source, effective_at=timezone.now(), buying_rate=1000, selling_rate=1100)
            review = self.review()
            self.assertIn("maximum 800.00", review["error"])
            self.assertIsNone(review["token"])
            with self.assertRaises(ValueError): self.confirm(token)
            page = self.client.get(self.url)
            self.assertContains(page, "No amount is reduced automatically")
            self.assertNotContains(page, "Confirm updated approval")
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(days=1)):
            self.assertIn("maximum 800.00", self.review()["error"])
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "APPROVED")
        self.assertEqual(self.loan.loan_date, self.previous_date)

    def test_authorization_signature_unpaid_and_workspace_binding(self):
        token = self.review()["token"]
        with self.assertRaisesMessage(ValueError, "Confirm that no cash"):
            self.confirm(token, unpaid=False)
        with self.assertRaises(ValueError): self.confirm(token + "tampered")
        with self.assertRaises(PermissionDenied): self.confirm(token, actor=None)
        other = get_user_model().objects.create_user(username="review-admin")
        membership = Membership.objects.create(user=other, company=self.tenant, role=Role.objects.get_or_create(name="Admin")[0])
        with self.assertRaises(PermissionDenied): self.confirm(token, actor=other)
        other_token = preview_updated_valuation(self.loan, actor=other)["token"]
        membership.delete()
        with self.assertRaises(PermissionDenied): self.confirm(other_token, actor=other)
        self.assertFalse(self.loan.loan_events.exists())

    def test_approval_failure_rolls_back_date_state_terms_and_audit(self):
        token = self.review()["token"]
        history = list(self.loan.change_log.values())
        items = list(self.loan.collateral_items.values())
        with patch("apps.tenant_apps.loans.services.valuation_review.approve_pawn_loan", side_effect=ValueError("Approval failed")):
            with self.assertRaisesMessage(ValueError, "Approval failed"):
                self.confirm(token)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "APPROVED")
        self.assertEqual(self.loan.loan_date, self.previous_date)
        self.assertEqual(list(self.loan.change_log.values()), history)
        self.assertEqual(list(self.loan.collateral_items.values()), items)

    def test_restricted_role_and_cross_workspace_token_guard(self):
        from django.core import signing
        from apps.tenant_apps.loans.services.valuation_review import SALT
        token = self.review()["token"]
        payload = signing.loads(token, salt=SALT)
        payload["workspace"] += 1
        with self.assertRaises(PermissionDenied):
            self.confirm(signing.dumps(payload, salt=SALT))
        role = connection.ops.quote_name("valuation_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            self.assertTrue(self.confirm(token)[1])
            self.assertFalse(self.confirm(token)[1])
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_policy_change_changes_comparison_and_invalidates_review(self):
        from apps.tenant_apps.loans.services.economic_policies import create_pawn_metal_interest_rate_policy
        token = self.review()["token"]
        create_pawn_metal_interest_rate_policy(workspace=self.tenant, license=self.loan.license,
            metal="GOLD", monthly_interest_rate=Decimal("3"), effective_from=timezone.localdate(), actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed"):
            self.confirm(token)
        review = self.review()
        self.assertEqual(review["resolved"].economics.monthly_interest, Decimal("30"))
        loan, _ = self.confirm(review["token"])
        self.assertEqual(loan.monthly_interest_rate, Decimal("3"))

    def test_permissions_allow_comparison_but_not_unauthorized_reapproval(self):
        user = get_user_model().objects.create_user(username="review-reader")
        role = Role.objects.get_or_create(name="Viewer")[0]
        Membership.objects.create(user=user, company=self.tenant, role=role)
        self.client.force_login(user)
        page = self.client.get(self.url)
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Confirm updated approval")
        token = page.context["preview"]["token"]
        self.assertEqual(self.client.post(self.url, {"review_token": token, "unpaid": "on"}).status_code, 403)
        self.assertEqual(self.loan.approval_snapshots.count(), 1)

    def test_stale_approval_is_discoverable_before_payment_and_post_redirects_to_disbursal(self):
        self.assertTrue(valuation_refresh_reason(self.loan))
        detail = self.client.get(reverse("loans:pawn_loan_detail", args=[self.loan.pk]))
        self.assertEqual(detail.context["primary_action"]["label"], "Review updated valuation")
        disbursal = self.client.get(reverse("loans:pawn_loan_disburse", args=[self.loan.pk]))
        self.assertContains(disbursal, "Review updated valuation")
        self.assertTrue(disbursal.context["review_error"])
        page = self.client.get(self.url)
        response = self.client.post(self.url, {"review_token": page.context["preview"]["token"], "unpaid": "on"})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.endswith("/disburse/"))
        self.loan.refresh_from_db()
        self.assertIsNone(valuation_refresh_reason(self.loan))
        self.assertFalse(self.loan.loan_events.exists())

    def test_unchanged_amount_new_daily_quote_still_gets_explicit_review(self):
        with patch("django.utils.timezone.now", return_value=self.now + timedelta(seconds=1)):
            Rate.objects.create(rate_source=self.source, effective_at=timezone.now(), buying_rate=3000, selling_rate=3100)
            self.assertTrue(valuation_refresh_reason(self.loan))
            self.confirm(self.review()["token"])
        self.assertEqual(self.loan.approval_snapshots.count(), 2)

    def test_draft_active_and_historical_approval_are_not_repriced(self):
        from apps.tenant_apps.loans.services import reopen_pawn_loan
        from apps.tenant_apps.loans.services.loan_workflow import make_earlier_payout_review, record_earlier_payout
        reopen_pawn_loan(self.loan.pk, actor=self.actor, reason="Actually paid yesterday")
        self.loan.refresh_from_db()
        with self.assertRaises(ValueError): self.review()
        _, token, _, _ = make_earlier_payout_review(self.loan, actor=self.actor)
        record_earlier_payout(self.loan.pk, actor=self.actor, token=token, reason="Cash was paid yesterday", confirmed=True)
        with self.assertRaises(ValueError): self.review()
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.loan_date, self.previous_date)


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class UpdatedValuationConcurrencyTests(TransactionTestCase):
    make_loan = fixtures.CollateralReappraisalTests.make_loan

    def test_simultaneous_confirmations_append_one_approval_and_no_payment(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from tempfile import TemporaryDirectory
        self.actor = get_user_model().objects.create_user(username="valuation-concurrency")
        self.tenant = Company.objects.create(name="Review concurrency", schema_name=uuid.uuid4().hex,
            owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            with workspace_context(self.tenant.pk):
                self.make_loan(age_days=0, activate=False)
                approve_pawn_loan(self.loan.pk, actor=self.actor)
                self.loan.refresh_from_db()
                token = preview_updated_valuation(self.loan, actor=self.actor)["token"]
            barrier = Barrier(2)
            def confirm(_):
                try:
                    with workspace_context(self.tenant.pk):
                        barrier.wait(timeout=10)
                        loan, changed = confirm_updated_valuation(self.loan.pk, actor=self.actor, token=token, unpaid=True)
                        return loan.pk, changed
                finally:
                    connections.close_all()
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(confirm, range(2)))
            self.assertEqual({result[1] for result in results}, {True, False})
            self.assertEqual({result[0] for result in results}, {self.loan.pk})
            with workspace_context(self.tenant.pk):
                self.assertEqual(self.loan.approval_snapshots.count(), 2)
                self.assertFalse(self.loan.loan_events.exists())
