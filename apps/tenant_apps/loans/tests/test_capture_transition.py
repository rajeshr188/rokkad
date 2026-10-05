"""Explicit future capture changes coverage expectations, never debt or origin."""
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch
from django.db import DatabaseError, connection, transaction
from django.urls import reverse
from django.test import override_settings
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from apps.tenant_apps.loans.services.pawn_release import preview_pawn_loan_full_release, release_pawn_loan_in_full
from apps.tenant_apps.loans.services.paper_repayments import preview_paper_repayment, record_paper_repayment
from . import test_recorded_origination as origins, test_recorded_history as histories, test_transaction_reviews as reviews


@override_settings(STORAGES={"default":{"BACKEND":"django.core.files.storage.InMemoryStorage"}, "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
class CaptureTransitionTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    row = histories.RecordedHistoryTests.row
    admit = histories.RecordedHistoryTests.admit
    prepare_notice = reviews.TransactionReviewTests.prepare_notice

    def setUp(self):
        self.prepare_history()
        self.loan, _, _ = self.admit()

    def facts(self, **changes):
        return dict(through_date=self.today, confirmed_complete=True, source_reference="Checked complete loan book; future activity directly in Rokkad",
            request_key=uuid4().hex, future_capture="ROKKAD_ONLY", **changes)

    def transition(self, facts=None):
        facts = facts or self.facts()
        _, token = preview_transaction_review(self.loan.pk, actor=self.actor, **facts)
        return confirm_transaction_review(self.loan.pk, actor=self.actor, **facts, review_token=token, acknowledged=True), facts, token

    def test_explicit_transition_current_receipt_rollover_and_full_settlement(self):
        before = list(self.loan.loan_events.values_list("pk", "payload_fingerprint"))
        (review, created), facts, token = self.transition()
        self.assertTrue(created)
        self.assertEqual(before, list(self.loan.loan_events.values_list("pk", "payload_fingerprint")))
        self.assertFalse(confirm_transaction_review(self.loan.pk, actor=self.actor, **facts, review_token=token, acknowledged=True)[1])
        record_pawn_loan_repayment(self.loan.pk, amount="2000", request_key="current", actor=self.actor)
        coverage = transaction_completeness(self.loan, self.today + timedelta(days=31))
        self.assertEqual((coverage.status, coverage.complete, coverage.review_id), ("ROKKAD_ONLY", True, review.pk))
        quote = preview_pawn_loan_full_release(self.loan.pk)
        release_pawn_loan_in_full(self.loan.pk, settlement_amount=quote.minimum_settlement,
            request_key="current-close", actor=self.actor)
        self.loan.refresh_from_db()
        self.assertTrue(transaction_completeness(self.loan, self.today+timedelta(days=40)).complete)

    def test_paper_payment_invalidates_transition_and_fresh_mixed_review_does_not_inherit_it(self):
        self.transition()
        data = dict(amount="1000", received_on=self.today, receipt_reference="New paper receipt", request_key=uuid4().hex, actor=self.actor)
        review = preview_paper_repayment(self.loan.pk, **data)
        record_paper_repayment(self.loan.pk, **data, review_token=review.review_token, confirmed_received=True)
        self.assertEqual(transaction_completeness(self.loan, self.today).status, "CHANGED")
        mixed = dict(self.facts(), request_key=uuid4().hex, future_capture="PAPER_MIXED")
        self.transition(mixed)
        self.assertEqual(transaction_completeness(self.loan, self.today).status, "CONFIRMED")
        self.assertEqual(transaction_completeness(self.loan, self.today+timedelta(days=1)).status, "BEHIND")

    def test_reviewed_receipt_correction_holds_future_capture_until_another_review(self):
        from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
        self.transition()
        payment = record_pawn_loan_repayment(self.loan.pk, amount="1000", request_key="current-to-correct", actor=self.actor)
        data = dict(operation="REPLACE", target=payment.loan_event.pk, date=self.today.isoformat(),
            amount="500", reference="Correct actual receipt amount", before=None,
            reason="Transcription corrected against the retained receipt", request_key=uuid4().hex)
        _, token = preview_correction(self.loan.pk, actor=self.actor, data=data)
        record_correction(self.loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertEqual(transaction_completeness(self.loan, self.today).status, "CHANGED")
        self.transition()
        self.assertTrue(transaction_completeness(self.loan, self.today+timedelta(days=1)).complete)

    def test_incomplete_old_date_stale_or_changed_choice_is_rejected(self):
        for changes in ({"confirmed_complete":False}, {"through_date":self.today-timedelta(days=1)}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                preview_transaction_review(self.loan.pk, actor=self.actor, **dict(self.facts(), **changes))
        facts = self.facts()
        _, token = preview_transaction_review(self.loan.pk, actor=self.actor, **facts)
        with self.assertRaises(ValueError):
            confirm_transaction_review(self.loan.pk, actor=self.actor, **dict(facts, future_capture="PAPER_MIXED"), review_token=token, acknowledged=True)
        record_pawn_loan_repayment(self.loan.pk, amount="1000", request_key="after-preview", actor=self.actor)
        with self.assertRaises(ValueError):
            confirm_transaction_review(self.loan.pk, actor=self.actor, **facts, review_token=token, acknowledged=True)

    def test_restricted_role_immutability_foreign_binding_and_invalid_checkpoint(self):
        (review, _), _, _ = self.transition()
        other = Company.objects.create(name="Other", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("capture_"+uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanTransactionReview.objects.filter(pk=review.pk).update(future_capture="PAPER_MIXED")
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanTransactionReview.objects.create(loan=self.loan, through_date=self.today, confirmed_complete=True,
                    source_reference="Wrong prefix", source_fingerprint="a"*64, request_key="wrong",
                    future_capture="ROKKAD_ONLY", capture_state="ACTIVE", capture_event_id=review.capture_event_id+100,
                    capture_contract_fingerprint=review.capture_contract_fingerprint,
                    reviewed_by=self.actor)
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.LoanTransactionReview.objects.filter(pk=review.pk).exists())
                with self.assertRaises(m.PawnLoan.DoesNotExist):
                    preview_transaction_review(self.loan.pk, actor=self.actor, **self.facts())
                with self.assertRaises(DatabaseError), transaction.atomic():
                    m.LoanTransactionReview.objects.create(workspace=other, loan_id=self.loan.pk,
                        through_date=self.today, confirmed_complete=True, source_reference="Foreign capture claim",
                        source_fingerprint=review.source_fingerprint, request_key="foreign-capture",
                        future_capture="ROKKAD_ONLY", capture_state="ACTIVE", capture_event_id=review.capture_event_id,
                        capture_contract_fingerprint=review.capture_contract_fingerprint, reviewed_by=self.actor)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE"); cursor.execute(f"DROP OWNED BY {role}"); cursor.execute(f"DROP ROLE {role}")

    def test_transition_and_current_activity_survive_exact_recovery_but_old_portable_wire_holds(self):
        from hashlib import sha256
        from .test_pawn_recovery import PawnRecoveryTests
        from apps.tenant_apps.loans.services import pawn_recovery as recovery
        from apps.tenant_apps.loans.services.history_export import export_history
        self.transition()
        record_pawn_loan_repayment(self.loan.pk, amount="2000", request_key="current", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "Future-capture"):
            export_history(workspace_id=self.tenant.pk, actor=self.actor, loan_id=self.loan.pk)
        content = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        original, _ = recovery._read(content, sha256(content).hexdigest())
        PawnRecoveryTests.empty(self)
        recovery.restore_archive(workspace=self.tenant, actor=self.actor, content=content,
            expected_sha256=sha256(content).hexdigest(), commit=True)
        new_content = recovery.export_archive(workspace=self.tenant, actor=self.actor)
        restored, _ = recovery._read(new_content, sha256(new_content).hexdigest())
        self.assertEqual(original["tables"], restored["tables"])
        self.loan.refresh_from_db()
        self.assertEqual(transaction_completeness(self.loan, self.today+timedelta(days=10)).status, "ROKKAD_ONLY")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls")
    def test_ui_requires_signed_review_and_displays_future_recording_choice(self):
        self.start_active_trial()
        self.client = self.make_workspace_client()
        self.client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_review_transactions", args=[self.tenant.slug,self.loan.pk])
        response = self.client.get(url)
        self.assertContains(response, "every transaction will be entered directly in Rokkad")
        data = dict(self.facts(), through_date=self.today.isoformat(), confirmed_complete="complete", action="preview")
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Every future transaction entered directly in Rokkad")
        token = response.context["form"].data["review_token"]
        self.assertEqual(self.client.post(url, dict(data, action="confirm", review_token=token, acknowledged="on")).status_code, 302)
        self.assertEqual(transaction_completeness(self.loan, self.today).status, "ROKKAD_ONLY")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_reminder_rejects_stale_amount_even_when_future_capture_remains_complete(self):
        # Reuse real risk intent/Notify commands, replacing only the provider attempt.
        self.data["number"] = "P-0011"
        from apps.tenant_apps.loans.services.recorded_history import new_recording_intent
        self.args["intent_token"] = new_recording_intent(workspace=self.tenant, actor=self.actor)
        self.data["source_reference"] = "Separate notice loan"
        loan, _, _ = self.prepare_notice()
        self.loan = loan
        self.transition()
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        from apps.tenant_apps.loans.services.risk_borrower_notices import preview_risk_borrower_notice, create_risk_borrower_notice
        from apps.tenant_apps.notify_v2.models import NotificationJob
        from apps.tenant_apps.notify_v2.services import dispatch_job
        refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today)
        alert = m.LoanRiskAlert.objects.get(loan=loan, alert_kind="MATURITY")
        preview = preview_risk_borrower_notice(alert.pk)
        notice = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=preview.fingerprint)
        job = NotificationJob.objects.get(pk=notice.notification_job_id)
        record_pawn_loan_repayment(loan.pk, amount="1000", request_key="changed-current", actor=self.actor)
        self.assertTrue(transaction_completeness(loan, self.today).complete)
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job") as provider:
            self.assertFalse(dispatch_job(job)); provider.assert_not_called()
        refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today)
        preview = preview_risk_borrower_notice(alert.pk)
        new = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=preview.fingerprint)
        self.assertEqual(new.payload_snapshot["transaction_review"]["status"], "ROKKAD_ONLY")
        self.assertNotEqual(new.payload_snapshot["transaction_review"]["source_fingerprint"],
                            new.payload_snapshot["transaction_review"]["checked_source_fingerprint"])


from . import test_shared_monthly_contract as monthly


class NativeCaptureTransitionTests(monthly.SharedNativeContractTests):
    def test_current_monthly_receipt_recognizes_old_eligible_periods_without_missing_paper_claim(self):
        from django.utils import timezone
        today = timezone.localdate()
        facts = dict(through_date=today, confirmed_complete=True, future_capture="ROKKAD_ONLY",
            source_reference="Original history checked; no off-system activity", request_key=uuid4().hex)
        _, token = preview_transaction_review(self.loan.pk, actor=self.actor, **facts)
        confirm_transaction_review(self.loan.pk, actor=self.actor, **facts, review_token=token, acknowledged=True)
        record_pawn_loan_repayment(self.loan.pk, amount="200", request_key="current-after-review", actor=self.actor)
        self.assertTrue(self.loan.loan_events.filter(event_kind="INTEREST_ACCRUAL", effective_date__lt=today).exists())
        self.assertTrue(transaction_completeness(self.loan, today+timedelta(days=1)).complete)
