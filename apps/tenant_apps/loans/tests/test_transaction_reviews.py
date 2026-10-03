from datetime import timedelta
from uuid import uuid4
from unittest.mock import Mock, patch
from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from django.urls import reverse
from apps.orgs.models import Company
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from .test_recorded_origination import RecordedOriginationTests
from .test_recorded_history import RecordedHistoryTests


class TransactionReviewTests(RecordedOriginationTests):
    prepare_history = RecordedHistoryTests.prepare_history
    admit = RecordedHistoryTests.admit
    row = RecordedHistoryTests.row

    @classmethod
    def get_test_schema_name(cls):
        return "transaction-review"

    def setUp(self):
        super().setUp()
        self.prepare_history()

    def review(self, loan, **changes):
        data = dict(through_date=self.today, confirmed_complete=True, source_reference="Checked book A and all receipts", request_key=uuid4().hex)
        data.update(changes)
        review, token = preview_transaction_review(loan.pk, actor=self.actor, **data)
        result = confirm_transaction_review(loan.pk, actor=self.actor, **data, review_token=token, acknowledged=True)
        return result, data, token

    def test_admission_confirmation_rollover_and_financial_change(self):
        loan, _, _ = self.admit()
        self.assertTrue(transaction_completeness(loan, self.today).complete)
        self.assertEqual(transaction_completeness(loan, self.today + timedelta(days=1)).status, "BEHIND")
        record_pawn_loan_repayment(loan.pk, amount="2000", request_key="receipt", actor=self.actor)
        self.assertEqual(transaction_completeness(loan, self.today).status, "CHANGED")
        self.review(loan)
        self.assertTrue(transaction_completeness(loan, self.today).complete)
        self.review(loan, confirmed_complete=False)
        self.assertEqual(transaction_completeness(loan, self.today).status, "INCOMPLETE")

    def test_preview_stale_or_changed_inputs_retry_and_no_financial_effect(self):
        loan, _, _ = self.admit()
        before = list(loan.loan_events.values_list("pk", "payload_fingerprint"))
        (review, created), data, token = self.review(loan)
        self.assertTrue(created)
        self.assertEqual(before, list(loan.loan_events.values_list("pk", "payload_fingerprint")))
        self.assertFalse(confirm_transaction_review(loan.pk, actor=self.actor, **data, review_token=token, acknowledged=True)[1])
        for changes in ({"source_reference": "Changed source"}, {"through_date": self.day}, {"confirmed_complete": False}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                confirm_transaction_review(loan.pk, actor=self.actor, **dict(data, **changes), review_token=token, acknowledged=True)
        fresh = dict(data, request_key=uuid4().hex)
        _, token = preview_transaction_review(loan.pk, actor=self.actor, **fresh)
        record_pawn_loan_repayment(loan.pk, amount="2000", request_key="receipt", actor=self.actor)
        with self.assertRaisesMessage(ValueError, "changed"):
            confirm_transaction_review(loan.pk, actor=self.actor, **fresh, review_token=token, acknowledged=True)
        for changes in ({"through_date": self.today + timedelta(days=1)}, {"through_date": self.day-timedelta(days=1)}, {"source_reference": ""}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                preview_transaction_review(loan.pk, actor=self.actor, **dict(data, **changes))

    def test_closed_coverage_does_not_age_and_correction_requires_new_check(self):
        self.data.update(final_state="CLOSED", events=[self.row(kind="CLOSE", amount="10200", number="R-0009", recipient="Borrower")])
        loan, _, _ = self.admit()
        self.assertTrue(transaction_completeness(loan, self.today+timedelta(days=30)).complete)
        self.assertEqual(loan.transaction_reviews.count(), 1)

    def test_isolation_immutable_review_and_foreign_parent_guards(self):
        loan, _, _ = self.admit()
        review = loan.transaction_reviews.get()
        other = Company.objects.create(name="Other", schema_name=uuid4().hex, owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("transaction_review_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanTransactionReview.objects.filter(pk=review.pk).update(confirmed_complete=False)
            with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute("DELETE FROM loans_loantransactionreview WHERE id=%s", [review.pk])
            with without_workspace_context(), workspace_context(other.pk):
                self.assertFalse(m.LoanTransactionReview.objects.filter(pk=review.pk).exists())
                with self.assertRaises(DatabaseError), transaction.atomic():
                    m.LoanTransactionReview.objects.create(workspace=other, loan_id=loan.pk, through_date=self.today,
                        confirmed_complete=True, source_reference="Forged", source_fingerprint="a"*64,
                        request_key="foreign", reviewed_by=self.actor)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    def test_risk_stays_visible_but_portfolio_totals_are_provisional(self):
        loan, _, _ = self.admit()
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant, version=1, effective_from=self.day,
            compliance_profile="test", ltv_warning_ratio="0.7", ltv_breach_ratio="0.8", ltv_critical_ratio="0.9",
            eligible_custody_states=["IN_VAULT"], severity_mapping={"strategy":"derived-v1"}, created_by=self.actor)
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio_summary
        from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
        snapshot = refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today)
        self.assertTrue(snapshot.source_provenance["transactions"]["complete"])
        value = snapshot.exposure
        self.review(loan, confirmed_complete=False)
        snapshot.refresh_from_db()
        self.assertEqual(snapshot.status, "STALE")
        snapshot = refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today)
        self.assertEqual(snapshot.exposure, value)
        self.assertIn("TRANSACTIONS_UNCONFIRMED", snapshot.flags)
        self.assertEqual(get_risk_portfolio_summary().provisional_count, 1)
        self.assertFalse(get_risk_portfolio_summary().totals_complete)
        self.assertFalse(get_dashboard_health_summary(workspace=self.tenant)["financial_complete"])

    def test_unprivileged_actor_and_concurrent_review_invalidate_preview(self):
        from django.contrib.auth import get_user_model
        loan, _, _ = self.admit()
        actor = get_user_model().objects.create_user(username="unprivileged")
        data = dict(through_date=self.today, confirmed_complete=True, source_reference="Book A", request_key=uuid4().hex)
        with self.assertRaises(PermissionDenied):
            preview_transaction_review(loan.pk, actor=actor, **data)
        _, token = preview_transaction_review(loan.pk, actor=self.actor, **data)
        self.review(loan)
        with self.assertRaisesMessage(ValueError, "previous review changed"):
            confirm_transaction_review(loan.pk, actor=self.actor, **data, review_token=token, acknowledged=True)

    def test_reports_export_dates_and_provisional_status(self):
        loan, _, _ = self.admit()
        self.review(loan, through_date=self.day)
        from apps.tenant_apps.loans.selectors.reports import get_pawn_loan_reports
        from apps.tenant_apps.loans.services.report_exports import build_pawn_loan_report_dataset
        report = get_pawn_loan_reports(as_of_date=self.today)
        dataset = build_pawn_loan_report_dataset(report, "active")
        row = next(row for row in dataset.rows if row[0] == loan.loan_number)
        self.assertEqual(row[-2:], ("BEHIND", self.day))
        self.assertIn("provisional", dataset.notes)
        from apps.tenant_apps.loans.selectors.reports import get_pawn_party_statement
        from apps.tenant_apps.loans.services.report_exports import build_party_statement_dataset, render_report_dataset
        statement = get_pawn_party_statement(party_id=loan.borrower_id, as_of_date=self.today)
        exported = build_party_statement_dataset(statement)
        self.assertEqual(next(row for row in exported.rows if row[0] == "LOAN POSITION" and row[1] == loan.loan_number)[-2:], ("BEHIND", self.day))
        for name, source in (("coverage-report", dataset), ("coverage-statement", exported)):
            pdf, _ = render_report_dataset(source, "pdf")
            import fitz, os
            document = fitz.open(stream=pdf, filetype="pdf")
            self.assertIn("BEHIND", " ".join(page.get_text() for page in document))
            if os.environ.get("PAPER_QA_CAPTURE"):
                from pathlib import Path
                Path(f"/qa/{name}.pdf").write_bytes(pdf)
                for index, page in enumerate(document):
                    page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).save(f"/qa/{name}-{index}.png")

    def prepare_notice(self):
        self.data["tenure"] = 1
        loan, _, _ = self.admit()
        loan.borrower.primary_email = "borrower@example.test"
        loan.borrower.save()
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant, version=1, effective_from=self.day,
            compliance_profile="test", ltv_warning_ratio="0.7", ltv_breach_ratio="0.8", ltv_critical_ratio="0.9",
            eligible_custody_states=["IN_VAULT"], severity_mapping={"strategy":"derived-v1"}, created_by=self.actor)
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today)
        alert = m.LoanRiskAlert.objects.get(loan=loan, alert_kind="MATURITY")
        m.PawnLoanCommunicationConsent.objects.create(workspace=self.tenant, party=loan.borrower, channel="EMAIL",
            service_notices_allowed=True, evidence="Borrower requested reminder", updated_by=self.actor)
        from apps.tenant_apps.notify_v2.models import NotificationEventType, NotificationTemplate
        event = NotificationEventType.objects.create(key="pawn_loan.repayment_reminder", name="Repayment", domain="LOAN")
        NotificationTemplate.objects.create(event_type=event, channel="EMAIL", name="Repayment",
            body_template="Amount due {{ loans.0.total_due }}", subject_template="Repayment")
        from apps.tenant_apps.loans.services.risk_borrower_notices import preview_risk_borrower_notice, create_risk_borrower_notice
        preview = preview_risk_borrower_notice(alert.pk)
        self.assertEqual(preview.balance.interest_outstanding, 200)
        self.assertIn("10200", preview.body)
        notice = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=preview.fingerprint)
        from apps.tenant_apps.notify_v2.models import NotificationJob
        return loan, notice, NotificationJob.objects.get(pk=notice.notification_job_id)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_direct_notify_dispatch_blocks_changed_receipt_and_does_not_call_provider(self):
        loan, notice, job = self.prepare_notice()
        record_pawn_loan_repayment(loan.pk, amount="2000", request_key="after-queue", actor=self.actor)
        from apps.tenant_apps.notify_v2.services import dispatch_job
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job") as deliver:
            self.assertFalse(dispatch_job(job))
            deliver.assert_not_called()
        job.refresh_from_db()
        self.assertEqual(job.status, "FAILED")
        self.assertIn("review", job.failure_reason)
        self.review(loan)
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        from apps.tenant_apps.loans.services.risk_borrower_notices import preview_risk_borrower_notice, create_risk_borrower_notice
        refresh_loan_risk_snapshot(loan.pk, as_of_date=self.today)
        preview = preview_risk_borrower_notice(notice.source_risk_alert_id)
        replacement = create_risk_borrower_notice(notice.source_risk_alert_id, actor=self.actor, expected_fingerprint=preview.fingerprint)
        self.assertNotEqual(notice.pk, replacement.pk)
        self.assertEqual(preview.balance.total_due, 8200)
        self.assertEqual(m.PawnLoanNotice.objects.filter(loan=loan).count(), 2)
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job") as deliver:
            self.assertFalse(dispatch_job(job))
            deliver.assert_not_called()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_delivery_allows_unchanged_confirmation_and_blocks_withdrawn_consent(self):
        loan, notice, job = self.prepare_notice()
        from apps.tenant_apps.notify_v2.services import dispatch_job
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job", return_value=True) as deliver:
            self.assertTrue(dispatch_job(job))
            deliver.assert_called_once()
        m.PawnLoanCommunicationConsent.objects.filter(party=loan.borrower).update(service_notices_allowed=False)
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job") as deliver:
            self.assertFalse(dispatch_job(job))
            deliver.assert_not_called()
        self.assertIn("consent", job.failure_reason)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_stale_worker_does_not_send_already_sent_job_again(self):
        loan, notice, job = self.prepare_notice()
        from apps.tenant_apps.notify_v2.models import NotificationJob
        NotificationJob.objects.filter(pk=job.pk).update(status="SENT")
        from apps.tenant_apps.notify_v2.services import dispatch_job
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job") as deliver:
            self.assertTrue(dispatch_job(job))
            deliver.assert_not_called()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_changed_template_cannot_send_a_different_message(self):
        loan, notice, job = self.prepare_notice()
        job.template.body_template = "Different unreviewed text"
        job.template.save()
        from apps.tenant_apps.notify_v2.services import dispatch_job
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job") as deliver:
            self.assertFalse(dispatch_job(job))
            deliver.assert_not_called()
        self.assertIn("confirmed preview", job.failure_reason)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_notice_review_and_confirmed_content_cannot_be_replaced(self):
        loan, notice, job = self.prepare_notice()
        for changes in ({"transaction_review_id": None}, {"payload_snapshot": {}}):
            with self.subTest(changes=changes), self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanNotice.objects.filter(pk=notice.pk).update(**changes)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_day_rollover_blocks_queued_reminder_even_after_new_confirmation(self):
        loan, notice, job = self.prepare_notice()
        from apps.tenant_apps.notify_v2.services import dispatch_job
        with patch("django.utils.timezone.localdate", return_value=self.today+timedelta(days=1)), patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job") as deliver:
            self.assertFalse(dispatch_job(job))
            deliver.assert_not_called()

    def test_receipt_correction_does_not_silently_refresh_completeness(self):
        self.data["events"] = [self.row()]
        loan, _, _ = self.admit()
        from apps.tenant_apps.loans.services.recorded_corrections import preview_correction, record_correction
        data = dict(operation="REPLACE", target=loan.loan_events.get(event_kind="REPAYMENT").pk,
            date=(self.day+timedelta(days=2)).isoformat(), amount="1000", reference="Corrected receipt", before=None,
            reason="Correct the transcribed amount", request_key=uuid4().hex)
        _, token = preview_correction(loan.pk, actor=self.actor, data=data)
        record_correction(loan.pk, actor=self.actor, data=data, review_token=token, confirmed=True)
        self.assertEqual(transaction_completeness(loan, self.today).status, "CHANGED")

    @override_settings(ROOT_URLCONF="django_project.workspace_urls", STORAGES={"default":{"BACKEND":"django.core.files.storage.FileSystemStorage"}, "staticfiles":{"BACKEND":"django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_ordinary_review_form_preview_confirmation_retry_and_detail(self):
        self.start_active_trial()
        loan, _, _ = self.admit()
        client = self.make_workspace_client()
        client.force_login(self.actor)
        url = reverse("workspace_loans:pawn_loan_review_transactions", kwargs=dict(workspace_slug=self.tenant.slug, pk=loan.pk))
        response = client.get(url)
        self.assertEqual(response.status_code, 200)
        post = dict(through_date=self.today.isoformat(), confirmed_complete="complete", source_reference="Checked Book A", request_key=response.context["form"].initial["request_key"], action="preview")
        response = client.post(url, post)
        self.assertFalse(response.context["form"].errors)
        self.assertTrue(response.context["review"])
        import os
        if os.environ.get("PAPER_QA_CAPTURE"):
            from pathlib import Path
            Path("/qa/transaction-review.html").write_bytes(response.content)
        post.update(action="confirm", acknowledged="on", review_token=response.context["form"].data["review_token"])
        response = client.post(url, post)
        self.assertEqual(response.status_code, 302)
        self.assertContains(client.get(response.url), "Transaction coverage: CONFIRMED")
        self.assertEqual(client.post(url, post).status_code, 302)


from django.test import TransactionTestCase
from .test_recorded_history import RecordedHistoryConcurrencyTests


class TransactionReviewConcurrencyTests(TransactionTestCase):
    make_snapshot = RecordedOriginationTests.make_snapshot

    def setUp(self):
        RecordedHistoryConcurrencyTests.setUp(self)
        from apps.tenant_apps.loans.services.recorded_history import admit_recorded_history
        with workspace_context(self.tenant.pk):
            self.loan, _ = admit_recorded_history(**self.commit)
            self.review_data = dict(through_date=self.today, confirmed_complete=True,
                source_reference="Checked paper records", request_key=uuid4().hex)
            _, self.token = preview_transaction_review(self.loan.pk, actor=self.actor, **self.review_data)

    def race(self, submissions):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.db import connections
        ready = Barrier(2)
        def submit(values):
            try:
                ready.wait(timeout=15)
                with workspace_context(self.tenant.pk):
                    review, created = confirm_transaction_review(self.loan.pk, actor=self.actor, acknowledged=True, **values)
                    return review.pk, created
            except ValueError:
                return None
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as workers:
            return list(workers.map(submit, submissions))

    def test_same_review_is_recorded_once(self):
        values = dict(**self.review_data, review_token=self.token)
        results = self.race([values, values])
        self.assertEqual(results[0][0], results[1][0])
        self.assertEqual(sorted(row[1] for row in results), [False, True])

    def test_different_reviews_cannot_both_confirm_same_predecessor(self):
        other = dict(self.review_data, request_key=uuid4().hex, confirmed_complete=False)
        with workspace_context(self.tenant.pk):
            _, token = preview_transaction_review(self.loan.pk, actor=self.actor, **other)
        results = self.race([dict(**self.review_data, review_token=self.token), dict(**other, review_token=token)])
        self.assertEqual(sum(result is not None for result in results), 1)


from . import test_opening_release as opening_fixtures


class OpeningTransactionReviewTests(opening_fixtures.OpeningReleaseFixture):
    def test_review_covers_checkpoint_forward_and_notice_uses_continuation_interest(self):
        self.assertEqual(transaction_completeness(self.loan, self.day).status, "UNCONFIRMED")
        data = dict(through_date=self.day, confirmed_complete=True, source_reference="Checked receipts after checkpoint", request_key=uuid4().hex)
        _, token = preview_transaction_review(self.loan.pk, actor=self.actor, **data)
        confirm_transaction_review(self.loan.pk, actor=self.actor, **data, review_token=token, acknowledged=True)
        self.assertTrue(transaction_completeness(self.loan, self.day).complete)
        from apps.tenant_apps.loans.services.notice_delivery_readiness import notice_balance
        self.assertEqual(notice_balance(self.loan, self.day).total_due, 1010)
        with self.assertRaises(ValueError):
            preview_transaction_review(self.loan.pk, actor=self.actor, **dict(data, through_date=self.loan.loan_date))
        record_pawn_loan_repayment(self.loan.pk, amount="210", request_key="after-review", actor=self.actor)
        self.assertEqual(transaction_completeness(self.loan, self.day).status, "CHANGED")
        self.assertEqual(notice_balance(self.loan, self.day).total_due, 800)
