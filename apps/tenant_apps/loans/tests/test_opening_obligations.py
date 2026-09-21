import uuid
from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, transaction

from apps.orgs.models import Company
from apps.tenancy.context import without_workspace_context, workspace_context
from apps.tenant_apps.loans.models import RepaymentScheduleVersion, RepaymentObligation
from apps.tenant_apps.loans.services.opening_obligations import persist_opening_repayment_schedule
from apps.tenant_apps.loans.services.opening_evidence import OpeningEvidenceError
from apps.tenant_apps.loans.services.event_recording import record_loan_event, LoanEventRecordingError
from apps.tenant_apps.loans.selectors.exposure import get_pawn_loan_exposure, PawnLoanExposureError
from apps.tenant_apps.loans.selectors.delinquency import get_pawn_loan_delinquency
from apps.tenant_apps.loans.selectors.obligation_state import get_active_repayment_schedule_as_of, calculate_obligation_state_as_of
from apps.tenant_apps.loans.tests.test_opening_event_storage import OpeningEventFixture
from apps.tenant_apps.loans.tests.test_opening_continuation import collection_review


class OpeningObligationsTests(OpeningEventFixture):
    product_grace_days = 30

    def review_document(self):
        doc = collection_review()
        doc["obligations"][0]["due"] = "2021-01-05"
        return doc

    def persist(self, actor=None):
        return persist_opening_repayment_schedule(self.loan.pk, actor=actor or self.actor)

    def test_schedule_keeps_original_dates_and_cutover_visibility(self):
        schedule = self.persist()
        self.assertEqual(schedule.source_event_id, self.origin.pk)
        self.assertEqual(schedule.disbursed_on, date(2021, 1, 1))
        self.assertEqual(schedule.maturity_date, date(2021, 4, 30))
        self.assertIsNone(get_active_repayment_schedule_as_of(self.loan, date(2021, 1, 19)))
        self.assertEqual(get_active_repayment_schedule_as_of(self.loan, date(2021, 1, 20)).pk, schedule.pk)
        state = calculate_obligation_state_as_of(schedule, date(2021, 1, 20))
        self.assertEqual((state.remaining.principal, state.remaining.interest, state.overdue.principal), (1000, 100, 1000))
        self.assertEqual(state.integrity_findings, ())
        assessment = get_pawn_loan_delinquency(self.loan.pk, as_of_date=date(2021, 1, 20)).assessment
        self.assertEqual(assessment.days_past_due, 15)
        self.assertTrue(assessment.escalation_eligible)  # Reviewed grace is 3, not today's product default 30.
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_exposure_uses_collection_rule_and_does_not_replay_daily_interest(self):
        with self.assertRaisesMessage(PawnLoanExposureError, "requires remaining obligations"):
            get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2021, 1, 20))
        self.persist()
        for day, extra in ((date(2021, 1, 20), 0), (date(2021, 2, 1), 0), (date(2021, 2, 2), 10)):
            with self.subTest(day=day):
                exposure = get_pawn_loan_exposure(self.loan.pk, as_of_date=day)
                self.assertEqual((exposure.original_principal, exposure.recorded_interest, exposure.projected_interest), (1000, 0, extra))
                self.assertEqual(exposure.total_economic_exposure, 1000 + extra)
                self.assertIn("projection:original-anniversary-upfront-inclusive/2", exposure.provenance)
        with self.assertRaises(LoanEventRecordingError):
            record_loan_event(self.loan.pk, actor=self.actor, event_kind="REPAYMENT", effective_date=date(2021, 2, 2), payload={"values": {"principal": "10"}})

    def test_replay_is_identical_and_reauthorizes_before_returning_existing_schedule(self):
        schedule = self.persist()
        self.assertEqual(self.persist().pk, schedule.pk)
        self.assertEqual(RepaymentObligation.objects.count(), 1)
        with self.assertRaises(PermissionDenied):
            persist_opening_repayment_schedule(self.loan.pk, actor=None)
        other = Company.objects.create(name="Other", schema_name="opening-obligation-other", owner=self.actor, creator=self.actor)
        with without_workspace_context(), workspace_context(other.pk), self.assertRaises((OpeningEvidenceError, PermissionDenied)):
            self.persist()

    def test_partial_schedule_creation_rolls_back(self):
        with patch.object(RepaymentObligation.objects, "create", side_effect=RuntimeError("synthetic failure")):
            with self.assertRaisesMessage(RuntimeError, "synthetic failure"):
                self.persist()
        self.assertFalse(RepaymentScheduleVersion.objects.exists())
        self.assertFalse(RepaymentObligation.objects.exists())
        self.assertEqual(self.loan.loan_events.count(), 1)

    def test_conflicting_existing_schedule_is_rejected_without_overwrite(self):
        existing = RepaymentScheduleVersion.objects.create(
            workspace=self.tenant, loan=self.loan, source_event=self.origin, version=1,
            contract_version="OTHER", fingerprint="f" * 64, disbursed_on=self.loan.loan_date,
            maturity_date=date(2021, 4, 30), principal=999, contractual_interest=100, created_by=self.actor,
        )
        with self.assertRaisesMessage(OpeningEvidenceError, "differs from the frozen"):
            self.persist()
        existing.refresh_from_db()
        self.assertEqual(existing.principal, 999)
        self.assertFalse(RepaymentObligation.objects.exists())

    def test_post_cutover_events_require_servicing_integration(self):
        self.event("REPAYMENT", date(2021, 1, 21), {"values": {"principal": "100"}})
        with self.assertRaisesMessage(OpeningEvidenceError, "before servicing"):
            self.persist()
        with self.assertRaisesMessage(PawnLoanExposureError, "subsequent servicing"):
            get_pawn_loan_exposure(self.loan.pk, as_of_date=date(2021, 1, 21))

    def test_obligations_remain_immutable_and_workspace_scoped_under_restricted_role(self):
        schedule = self.persist()
        other = Company.objects.create(name="Other", schema_name="opening-schedule-rls", owner=self.actor, creator=self.actor)
        role = connection.ops.quote_name("opening_obligations_" + uuid.uuid4().hex)
        connection.check_constraints()
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, UPDATE, DELETE ON loans_repaymentscheduleversion, loans_repaymentobligation TO {role}")
        try:
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {role}")
            self.assertTrue(RepaymentScheduleVersion.objects.filter(pk=schedule.pk).exists())
            for model in (RepaymentScheduleVersion, RepaymentObligation):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    model.objects.update(loan_id=self.loan.pk)
            with without_workspace_context():
                self.assertFalse(RepaymentObligation.objects.exists())
                with workspace_context(other.pk):
                    self.assertFalse(RepaymentScheduleVersion.objects.exists())
                    self.assertFalse(RepaymentObligation.objects.exists())
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")
