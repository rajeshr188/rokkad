"""Available accepted positions do not require an external-book attestation."""
from datetime import timedelta
from uuid import uuid4
from unittest.mock import patch

from django.test import override_settings
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context, without_workspace_context
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.selectors.transaction_coverage import recorded_position_coverage
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness
from apps.tenant_apps.loans.selectors.dashboard_health import get_dashboard_health_summary
from apps.tenant_apps.loans.selectors.risk_portfolio import get_risk_portfolio_summary
from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review
from apps.tenant_apps.loans.services.pawn_repayment import record_pawn_loan_repayment
from . import test_monitoring_input_boundary as native
from . import test_recorded_origination as paper
from .test_opening_release import OpeningReleaseFixture


def review(test, loan, day, *, complete=True):
    data = dict(through_date=day, confirmed_complete=complete,
        source_reference="Fictional optional reconciliation", request_key=uuid4().hex)
    _, token = preview_transaction_review(loan.pk, actor=test.actor, **data)
    return confirm_transaction_review(loan.pk, actor=test.actor, **data,
        review_token=token, acknowledged=True)[0]


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class NativePositionCoverageTests(WorkspaceTestCase):
    setup_tenant = classmethod(native.MonitoringInputBoundaryTests.setup_tenant.__func__)
    setUp = native.MonitoringInputBoundaryTests.setUp
    data = native.MonitoringInputBoundaryTests.data
    amend = native.MonitoringInputBoundaryTests.amend
    legacy_loan = native.MonitoringInputBoundaryTests.legacy_loan

    def test_supported_native_position_needs_no_review_and_does_not_post(self):
        before = list(self.loan.loan_events.values())
        result = recorded_position_coverage(self.loan, self.today)
        self.assertTrue(result.complete)
        self.assertEqual(result.status, "RECORDED_POSITION")
        self.assertEqual(result.book_review.status, "SYSTEM_RECORDED")
        self.assertFalse(self.loan.transaction_reviews.exists())
        self.assertEqual(before, list(self.loan.loan_events.values()))

    def test_aged_or_changed_positive_book_assurance_does_not_block_position(self):
        review(self, self.loan, self.today)
        tomorrow = self.today + timedelta(days=1)
        self.assertEqual(transaction_completeness(self.loan, tomorrow).status, "BEHIND")
        self.assertTrue(recorded_position_coverage(self.loan, tomorrow).complete)
        record_pawn_loan_repayment(self.loan.pk, amount="100", request_key="later-entered", actor=self.actor)
        self.assertEqual(transaction_completeness(self.loan, self.today).status, "CHANGED")
        self.assertTrue(recorded_position_coverage(self.loan, self.today).complete)
        self.assertEqual(self.loan.transaction_reviews.count(), 1)

    def test_known_missing_activity_stays_provisional_until_explicitly_resolved(self):
        self.amend(valuation_basis="CALCULATED_METAL_VALUE")
        review(self, self.loan, self.today, complete=False)
        record_pawn_loan_repayment(self.loan.pk, amount="100", request_key="not-a-resolution", actor=self.actor)
        result = recorded_position_coverage(self.loan, self.today)
        self.assertFalse(result.complete)
        self.assertEqual(result.status, "INCOMPLETE")
        snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.today)
        self.assertIn("TRANSACTIONS_UNCONFIRMED", snapshot.flags)
        self.assertFalse(get_dashboard_health_summary(workspace=self.tenant)["transactions_complete"])
        review(self, self.loan, self.today)
        self.assertTrue(recorded_position_coverage(self.loan, self.today).complete)

    def test_available_recorded_position_does_not_require_a_supported_future_forecast(self):
        loan, _ = self.legacy_loan()
        result = recorded_position_coverage(loan, self.today)
        self.assertTrue(result.complete)
        self.assertEqual(result.status, "RECORDED_POSITION")

    def test_scope_and_prepared_date_are_enforced(self):
        from apps.tenant_apps.loans.selectors.financial_inputs import get_pawn_loan_financial_inputs
        inputs = get_pawn_loan_financial_inputs(self.loan.pk, as_of_date=self.today)
        with self.assertRaisesMessage(ValueError, "Prepared financial inputs"):
            recorded_position_coverage(self.loan, self.today + timedelta(days=1), financial_inputs=inputs)
        with without_workspace_context(), self.assertRaises(ValueError):
            recorded_position_coverage(self.loan, self.today)
        with without_workspace_context():
            other = Company.objects.create(name="Different position Workspace", schema_name="other-position", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises(ValueError):
            recorded_position_coverage(self.loan, self.today)


class PaperPositionCoverageTests(WorkspaceTestCase):
    setup_tenant = classmethod(paper.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = paper.RecordedOriginationTests.make_snapshot

    def test_paper_origin_and_missing_book_check_are_not_evidence_of_missing_activity(self):
        loan = self.make_snapshot().loan
        before = list(loan.loan_events.values())
        result = recorded_position_coverage(loan, timezone.localdate())
        self.assertTrue(result.complete)
        self.assertEqual(result.principal_basis, "ORIGINAL_PAYOUT")
        self.assertEqual(result.book_review.status, "UNCONFIRMED")
        self.assertFalse(loan.transaction_reviews.exists())
        self.assertEqual(list(loan.loan_events.values()), before)
        self.assertFalse(recorded_position_coverage(loan, loan.loan_date - timedelta(days=1)).complete)

    def prepare_notice(self):
        from apps.tenant_apps.loans import models as m
        from apps.tenant_apps.notify_v2.models import NotificationEventType, NotificationTemplate, NotificationJob
        from apps.tenant_apps.loans.services.risk_borrower_notices import preview_risk_borrower_notice, create_risk_borrower_notice
        loan = self.make_snapshot().loan
        loan.borrower.primary_email = "position@example.test"
        loan.borrower.save()
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant, version=1,
            effective_from=loan.loan_date, compliance_profile="Fictional position notice",
            maturity_warning_days=100, ltv_warning_ratio=".7", ltv_breach_ratio=".8", ltv_critical_ratio=".9",
            eligible_custody_states=["IN_VAULT"], severity_mapping={"strategy": "derived-v1"}, created_by=self.actor)
        m.PawnLoanCommunicationConsent.objects.create(workspace=self.tenant, party=loan.borrower,
            channel="EMAIL", service_notices_allowed=True, evidence="Fictional requested reminder", updated_by=self.actor)
        event = NotificationEventType.objects.create(key="pawn_loan.repayment_reminder", name="Repayment", domain="LOAN")
        NotificationTemplate.objects.create(event_type=event, channel="EMAIL", name="Repayment",
            body_template="Amount due {{ loans.0.total_due }}", subject_template="Repayment")
        refresh_loan_risk_snapshot(loan.pk, as_of_date=timezone.localdate())
        alert = m.LoanRiskAlert.objects.get(loan=loan, alert_kind="MATURITY")
        preview = preview_risk_borrower_notice(alert.pk)
        notice = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=preview.fingerprint)
        return loan, alert, notice, NotificationJob.objects.get(pk=notice.notification_job_id)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_unreviewed_paper_position_notice_binds_amount_and_rejects_changes_at_dispatch(self):
        from apps.tenant_apps.notify_v2.services import dispatch_job
        from apps.tenant_apps.loans.services.risk_borrower_notices import preview_risk_borrower_notice, create_risk_borrower_notice, RiskBorrowerNoticeError
        loan, alert, notice, job = self.prepare_notice()
        self.assertIsNone(notice.transaction_review_id)
        self.assertEqual(notice.payload_snapshot["transaction_review"]["contract"], "recorded-position-coverage/1")
        self.assertFalse(loan.transaction_reviews.exists())
        with self.assertRaisesMessage(RiskBorrowerNoticeError, "already"):
            preview_risk_borrower_notice(alert.pk)
        record_pawn_loan_repayment(loan.pk, amount="2000", request_key="receipt-after-intent", actor=self.actor)
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job") as provider:
            self.assertFalse(dispatch_job(job))
            provider.assert_not_called()
        refresh_loan_risk_snapshot(loan.pk, as_of_date=timezone.localdate())
        preview = preview_risk_borrower_notice(alert.pk)
        replacement = create_risk_borrower_notice(alert.pk, actor=self.actor, expected_fingerprint=preview.fingerprint)
        self.assertNotEqual(replacement.pk, notice.pk)
        self.assertNotEqual(replacement.payload_snapshot["transaction_review"]["source_fingerprint"],
            notice.payload_snapshot["transaction_review"]["source_fingerprint"])
        self.assertFalse(loan.transaction_reviews.exists())

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_position_notice_retains_consent_and_known_missing_activity_gates(self):
        from apps.tenant_apps.loans.services.risk_communication_readiness import assess_risk_alert_communication_readiness
        from apps.tenant_apps.loans import models as m
        loan, alert, _notice, _job = self.prepare_notice()
        review(self, loan, timezone.localdate(), complete=False)
        readiness = assess_risk_alert_communication_readiness(alert.pk)
        self.assertFalse(readiness.eligible)
        self.assertIn("TRANSACTION_POSITION_UNAVAILABLE", [row.code for row in readiness.blockers])
        m.PawnLoanCommunicationConsent.objects.filter(party=loan.borrower).update(service_notices_allowed=False)
        readiness = assess_risk_alert_communication_readiness(alert.pk)
        self.assertTrue(any(row.code == "CONSENT_BLOCKED" for channel in readiness.channels for row in channel.blockers))

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_position_notice_content_is_immutable_under_restricted_role(self):
        from django.db import connection, transaction, DatabaseError
        from apps.tenant_apps.loans import models as m
        _loan, _alert, notice, _job = self.prepare_notice()
        role = connection.ops.quote_name("position_notice_" + uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT UPDATE ON loans_pawnloannotice TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            for change in ({"payload_snapshot": {}}, {"transaction_review_id": 999999}):
                with self.subTest(change=change), self.assertRaises(DatabaseError), transaction.atomic():
                    m.PawnLoanNotice.objects.filter(pk=notice.pk).update(**change)
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_optional_positive_review_does_not_invalidate_a_position_bound_notice(self):
        from apps.tenant_apps.notify_v2.services import dispatch_job
        loan, _alert, _notice, job = self.prepare_notice()
        review(self, loan, timezone.localdate())
        refresh_loan_risk_snapshot(loan.pk, as_of_date=timezone.localdate())
        with patch("apps.tenant_apps.notify_v2.services.delivery_service._dispatch_job", return_value=True) as provider:
            self.assertTrue(dispatch_job(job))
            provider.assert_called_once()

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.smtp.EmailBackend", DEFAULT_FROM_EMAIL="test@example.test")
    def test_new_position_intents_are_unique_and_downgrade_refuses_retained_evidence(self):
        from importlib import import_module
        from django.db import DatabaseError, connection, transaction
        from apps.tenant_apps.loans import models as m
        _loan, _alert, notice, _job = self.prepare_notice()
        fields = {f.attname: getattr(notice, f.attname) for f in notice._meta.concrete_fields if not f.primary_key}
        fields["request_key"] = "different-key-same-position"
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.PawnLoanNotice.objects.bulk_create([m.PawnLoanNotice(**fields)])
        reverse = import_module("apps.tenant_apps.loans.migrations.0090_recorded_position_notice").REVERSE
        with self.assertRaisesMessage(DatabaseError, "Retained position notices"), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(reverse)


class OpeningPositionCoverageTests(OpeningReleaseFixture):
    def test_opening_checkpoint_covers_current_position_without_earlier_cash_history(self):
        before = list(self.loan.loan_events.values())
        result = recorded_position_coverage(self.loan, self.day)
        self.assertTrue(result.complete)
        self.assertEqual(result.principal_basis, "OPENING_CHECKPOINT")
        self.assertEqual(result.history_from, self.origin.effective_date)
        self.assertEqual(result.book_review.status, "UNCONFIRMED")
        self.assertFalse(self.loan.transaction_reviews.exists())
        self.assertEqual(list(self.loan.loan_events.values()), before)
        self.assertFalse(recorded_position_coverage(self.loan, self.origin.effective_date - timedelta(days=1)).complete)

    def test_saved_and_live_coverage_agree_without_creating_book_reviews(self):
        from apps.tenant_apps.loans import models as m
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant, version=1,
            effective_from=self.loan.loan_date, compliance_profile="Fictional position monitoring",
            valuation_basis="LATEST_APPRAISAL", ltv_warning_ratio=".7", ltv_breach_ratio=".8", ltv_critical_ratio=".9",
            eligible_custody_states=["IN_VAULT"], severity_mapping={"strategy": "derived-v1"}, created_by=self.actor)
        snapshot = refresh_loan_risk_snapshot(self.loan.pk, as_of_date=self.day)
        self.assertTrue(snapshot.source_provenance["transactions"]["complete"])
        self.assertFalse(snapshot.source_provenance["transactions"]["book_review"]["complete"])
        self.assertNotIn("TRANSACTIONS_UNCONFIRMED", snapshot.flags)
        dashboard = get_dashboard_health_summary(workspace=self.tenant)
        self.assertTrue(dashboard["transactions_complete"])
        self.assertTrue(get_risk_portfolio_summary().totals_complete)
        self.assertFalse(self.loan.transaction_reviews.exists())
