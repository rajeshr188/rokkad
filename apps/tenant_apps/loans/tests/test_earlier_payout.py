from copy import deepcopy
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, override_settings
from django.utils import timezone

from apps.orgs.models import Membership, Role
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures
from apps.tenant_apps.loans.services import approve_pawn_loan, disburse_pawn_loan, reopen_pawn_loan
from apps.tenant_apps.loans.services.loan_workflow import make_earlier_payout_review, record_earlier_payout
from apps.tenant_apps.rates.services import withdraw_quote
from apps.tenant_apps.rates.models import Rate


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class EarlierPayoutTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)
    make_loan = fixtures.CollateralReappraisalTests.make_loan

    @classmethod
    def get_test_schema_name(cls):
        return "earlier-payout"

    def setUp(self):
        self.make_loan(age_days=0, activate=False)
        self.actual_date = self.loan.loan_date
        self.next_day = timezone.now() + timedelta(days=1)
        self.clock = patch("django.utils.timezone.now", return_value=self.next_day)
        self.clock.start()
        self.addCleanup(self.clock.stop)

    def review(self, actor=None):
        return make_earlier_payout_review(self.loan, actor=actor or self.actor)

    def record(self, token, **changes):
        values = dict(actor=self.actor, token=token, reason="Paper ticket issued on the actual date", confirmed=True)
        values.update(changes)
        return record_earlier_payout(self.loan.pk, **values)

    def test_late_recording_preserves_date_history_and_actor_and_is_idempotent(self):
        creator = self.actor
        recorder = get_user_model().objects.create_user(username="recording-admin", first_name="Recording", last_name="Admin", email="recorder@example.test")
        Membership.objects.create(user=recorder, company=self.tenant, role=Role.objects.get_or_create(name="Admin")[0])
        economics, token, quotes, basis = self.review(actor=recorder)
        result = self.record(token, actor=recorder)
        self.assertEqual(result.loan.loan_date, self.actual_date)
        self.assertEqual(result.loan_event.effective_date, self.actual_date)
        self.assertEqual(result.loan_event.created_by, recorder)
        self.assertEqual(result.loan.created_by, creator)
        self.assertEqual(timezone.localdate(result.loan_event.created_at), timezone.localdate())
        approval = result.loan.approval_snapshots.latest("version")
        self.assertEqual(approval.approved_by, recorder)
        self.assertEqual(approval.payload["origination_rates"]["quotes"]["GOLD"]["rate_id"], self.quote.pk)
        self.assertEqual(approval.payload["earlier_payout"]["recorded_by_id"], recorder.pk)
        self.assertTrue(self.record(token, actor=recorder).already_disbursed)
        self.assertEqual(result.loan.loan_events.count(), 1)
        from apps.tenant_apps.loans.web.pawn_reads import pawn_loan_detail
        request = RequestFactory().get("/")
        request.workspace, request.user = self.tenant, self.actor
        response = pawn_loan_detail(request, self.loan.pk)
        self.assertContains(response, "Recording Admin (recorder@example.test)")
        self.assertContains(response, "Payout recorded by")
        self.assertContains(response, creator.username)
        self.assertContains(response, self.actual_date.strftime("%d/%m/%Y"))

    def test_original_approval_quote_wins_over_todays_price(self):
        with patch("django.utils.timezone.now", return_value=self.next_day - timedelta(days=1)):
            original = approve_pawn_loan(self.loan.pk, actor=self.actor)
        before = deepcopy(original.payload)
        reopen_pawn_loan(self.loan.pk, actor=self.actor, reason="Correct a draft")
        self.loan.refresh_from_db()
        Rate.objects.create(rate_source=self.source, buying_rate=100, selling_rate=110)
        economics, token, quotes, basis = self.review()
        self.assertEqual(basis.pk, original.pk)
        self.assertEqual(quotes["GOLD"]["rate_id"], self.quote.pk)
        result = self.record(token)
        original.refresh_from_db()
        self.assertEqual(original.payload, before)
        self.assertEqual(result.loan.approval_snapshots.count(), 2)

    def test_normal_route_still_rejects_past_date(self):
        with self.assertRaisesMessage(ValueError, "Loan date must be today"):
            approve_pawn_loan(self.loan.pk, actor=self.actor)
        self.assertFalse(self.loan.loan_events.exists())

    def test_reason_attestation_and_authenticated_actor_are_required(self):
        token = self.review()[1]
        for changes in ({"reason": " "}, {"confirmed": False}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.record(token, **changes)
        with self.assertRaises(PermissionDenied):
            self.record(token, actor=None)
        self.assertFalse(self.loan.approval_snapshots.exists())
        self.assertFalse(self.loan.loan_events.exists())

    def test_missing_or_withdrawn_historical_quote_does_not_use_today(self):
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=self.quote.pk, reason="Incorrect source")
        with patch("django.utils.timezone.now", return_value=self.next_day + timedelta(seconds=1)):
            Rate.objects.create(rate_source=self.source, buying_rate=3000, selling_rate=3100)
        with self.assertRaisesMessage(ValueError, "existing positive quote"):
            self.review()

    def test_new_backdated_quote_is_not_contemporaneous_evidence(self):
        withdraw_quote(workspace=self.tenant, actor=self.actor, quote_id=self.quote.pk, reason="Wrong source")
        with patch("django.utils.timezone.now", return_value=self.next_day + timedelta(seconds=1)):
            Rate.objects.create(rate_source=self.source, buying_rate=3000, selling_rate=3100,
                effective_at=self.next_day - timedelta(days=1))
        with self.assertRaisesMessage(ValueError, "existing positive quote"):
            self.review()

    def test_stale_review_cannot_record_changed_loan(self):
        token = self.review()[1]
        self.loan.tenure_months = 10
        self.loan.save(update_fields=["tenure_months"])
        with self.assertRaisesMessage(ValueError, "changed"):
            self.record(token)
        self.assertFalse(self.loan.loan_events.exists())

    def test_todays_or_future_draft_does_not_use_historical_action(self):
        for delta in (0, 1):
            self.loan.loan_date = timezone.localdate() + timedelta(days=delta)
            self.loan.save(update_fields=["loan_date"])
            with self.assertRaisesMessage(ValueError, "before today"):
                self.review()

    def test_historical_approval_cannot_use_ordinary_disbursal(self):
        approve_pawn_loan(self.loan.pk, actor=self.actor, earlier_payout_reason="Paid yesterday")
        with self.assertRaisesMessage(ValueError, "earlier-payout review"):
            disburse_pawn_loan(self.loan.pk, actor=self.actor, effective_date=self.actual_date)
        self.assertFalse(self.loan.loan_events.exists())

    def test_recording_view_get_is_read_only_and_explains_identity(self):
        from apps.tenant_apps.loans.web.workflow import pawn_loan_record_earlier_payout
        request = RequestFactory().get("/")
        request.workspace, request.user = self.tenant, self.actor
        response = pawn_loan_record_earlier_payout(request, self.loan.pk)
        self.assertContains(response, "Record an earlier payout")
        self.assertContains(response, "Recording as")
        self.assertContains(response, self.actual_date.strftime("%d/%m/%Y"))
        self.assertFalse(self.loan.loan_events.exists())

    def test_corrected_earlier_payout_retains_original_event_and_schedule(self):
        from apps.tenant_apps.loans.services import reverse_pawn_loan_event
        first = self.record(self.review()[1])
        original_payload = deepcopy(first.loan_event.payload)
        reverse_pawn_loan_event(first.loan_event.pk, actor=self.actor, reason="Correct paper entry")
        reopen_pawn_loan(self.loan.pk, actor=self.actor, reason="Correct recorded terms")
        self.loan.refresh_from_db()
        second = self.record(self.review()[1])
        self.assertNotEqual(second.loan_event.pk, first.loan_event.pk)
        first.loan_event.refresh_from_db()
        self.assertEqual(first.loan_event.payload, original_payload)
        self.assertEqual(second.loan_event.effective_date, self.actual_date)
        self.assertEqual(self.loan.loan_events.count(), 3)
        self.assertEqual(self.loan.repayment_schedules.count(), 2)

    def test_staff_with_loan_permissions_but_no_setup_grant_cannot_record(self):
        from django.contrib.auth.models import Permission
        from django.contrib.contenttypes.models import ContentType
        from apps.tenancy.testing import workspace_role_permissions
        staff = get_user_model().objects.create_user(username="earlier-staff")
        role = Role.objects.create(name="Earlier payout staff")
        Membership.objects.create(user=staff, company=self.tenant, role=role)
        for code in ("data_view", "data_edit", "loan_approve", "loan_disburse"):
            permission, _ = Permission.objects.get_or_create(content_type=ContentType.objects.get_for_model(type(self.tenant)),
                codename=code, defaults={"name": code})
            workspace_role_permissions(role, self.tenant).add(permission)
        with self.assertRaises(PermissionDenied):
            self.review(actor=staff)
        self.assertFalse(self.loan.loan_events.exists())

    def test_actor_bound_token_cannot_be_reused_by_another_admin(self):
        token = self.review()[1]
        other = get_user_model().objects.create_user(username="other-earlier-admin")
        Membership.objects.create(user=other, company=self.tenant, role=Role.objects.get_or_create(name="Admin")[0])
        with self.assertRaisesMessage(ValueError, "signed-in user"):
            self.record(token, actor=other)
        self.assertFalse(self.loan.loan_events.exists())
