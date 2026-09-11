"""Batch/single read parity over persisted, effective-dated evidence."""
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import uuid

from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from apps.orgs.models import Company
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.models import (
    PawnLoan, LoanLicense, LoanSeries, PawnLoanEvent, RepaymentScheduleVersion,
    RepaymentObligation, RepaymentScheduleChange, ObligationAllocation,
)
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.loans.selectors.obligation_state import (
    get_obligation_states_for_loans, get_active_repayment_schedule_as_of,
    calculate_obligation_state_as_of,
)
from apps.tenant_apps.loans.selectors.counter_work import get_workspace_counter_work


class DashboardBatchTests(TestCase):
    def setUp(self):
        self.owner = get_user_model().objects.create_user(username="dashboard-batch")
        self.workspace = Company.objects.create(name="Batch", schema_name="dashboard-batch", owner=self.owner, creator=self.owner)

    def loan(self, workspace):
        party = Party.objects.create(display_name="Batch borrower")
        license = LoanLicense.objects.create(workspace=workspace, name="Batch", license_number=uuid.uuid4().hex,
            issued_on=date(2026, 1, 1), expires_on=date(2027, 1, 1))
        series = LoanSeries.objects.create(license=license, name="Batch", code="B")
        return PawnLoan.objects.create(workspace=workspace, license=license, series=series,
            borrower=party, product_version=ensure_test_product_version(workspace),
            loan_number=uuid.uuid4().hex, state="ACTIVE", principal_amount=1000,
            monthly_interest_rate=2, tenure_months=12, loan_date=date(2026, 1, 1))

    def event(self, loan, day):
        return PawnLoanEvent.objects.create(workspace=loan.workspace, loan=loan,
            event_kind="REPAYMENT", effective_date=date(2026, 1, day), payload={"test": True},
            payload_fingerprint=uuid.uuid4().hex, idempotency_key=uuid.uuid4().hex)

    def schedule(self, loan, version, day):
        schedule = RepaymentScheduleVersion.objects.create(workspace=loan.workspace, loan=loan,
            source_event=self.event(loan, day), version=version, contract_version="TEST",
            fingerprint=uuid.uuid4().hex, disbursed_on=date(2026, 1, 1),
            maturity_date=date(2026, 12, 1), principal=1000, contractual_interest=120)
        for sequence in range(1, 13):
            RepaymentObligation.objects.create(workspace=loan.workspace, loan=loan,
                schedule_version=schedule, sequence=sequence, due_date=date(2026, sequence, 1),
                principal_due=100 if sequence == 1 else 0, interest_due=10,
                opening_principal=1000, closing_principal=900)
        return schedule

    def test_batch_matches_single_reads_for_dates_reversals_and_versions(self):
        with workspace_context(self.workspace.pk):
            loan = self.loan(self.workspace)
            missing = self.loan(self.workspace)
            original = self.schedule(loan, 1, 1)
            replacement = self.schedule(loan, 2, 15)
            obligation = original.obligations.first()
            allocation = ObligationAllocation.objects.create(workspace=self.workspace, loan=loan,
                source_event=self.event(loan, 5), obligation=obligation, component="PRINCIPAL",
                amount=40, allocation_order=1)
            ObligationAllocation.objects.create(workspace=self.workspace, loan=loan,
                source_event=self.event(loan, 10), obligation=obligation, component="PRINCIPAL",
                amount=-40, allocation_order=1, reversal_of=allocation)
            termination = RepaymentScheduleChange.objects.create(workspace=self.workspace, loan=loan,
                schedule_version=replacement, source_event=self.event(loan, 20), kind="TERMINATE",
                effective_date=date(2026, 1, 20), reason="Test termination")
            RepaymentScheduleChange.objects.create(workspace=self.workspace, loan=loan,
                schedule_version=replacement, source_event=self.event(loan, 25), kind="REACTIVATE",
                effective_date=date(2026, 1, 25), reason="Test reversal", reversal_of=termination)
            for day, version, principal in ((1, 1, 100), (5, 1, 60), (10, 1, 100), (15, 2, 100), (20, 1, 100), (25, 2, 100)):
                as_of = date(2026, 1, day)
                with self.subTest(day=day), self.assertNumQueries(4):
                    batch = get_obligation_states_for_loans(workspace=self.workspace,
                        loan_ids=[loan.pk, missing.pk], as_of_date=as_of)
                single = calculate_obligation_state_as_of(get_active_repayment_schedule_as_of(loan, as_of), as_of)
                self.assertEqual(batch[loan.pk], single)
                self.assertEqual(batch[loan.pk].schedule_id, original.pk if version == 1 else replacement.pk)
                self.assertEqual(batch[loan.pk].due_now.principal, Decimal(principal))
                self.assertIsNone(batch[missing.pk].schedule_id)
            with self.assertNumQueries(5):
                work = get_workspace_counter_work(workspace=self.workspace, as_of_date=date(2026, 2, 1))
            self.assertEqual(work["queues"]["review"]["count"], 1)
            self.assertEqual(work["queues"]["due"]["count"], 1)
            self.assertEqual(work["queues"]["overdue"]["count"], 1)

    def test_overallocation_and_terminated_schedules_preserve_findings(self):
        with workspace_context(self.workspace.pk):
            loan = self.loan(self.workspace)
            schedule = self.schedule(loan, 1, 1)
            obligation = schedule.obligations.first()
            ObligationAllocation.objects.create(workspace=self.workspace, loan=loan,
                source_event=self.event(loan, 2), obligation=obligation, component="PRINCIPAL",
                amount=101, allocation_order=1)
            as_of = date(2026, 1, 3)
            batch = get_obligation_states_for_loans(workspace=self.workspace, loan_ids=[loan.pk], as_of_date=as_of)
            self.assertEqual(batch[loan.pk], calculate_obligation_state_as_of(schedule, as_of))
            self.assertTrue(batch[loan.pk].integrity_findings)
            work = get_workspace_counter_work(workspace=self.workspace, as_of_date=as_of)
            self.assertEqual(work["queues"]["review"]["count"], 1)
            RepaymentScheduleChange.objects.create(workspace=self.workspace, loan=loan,
                schedule_version=schedule, source_event=self.event(loan, 4), kind="TERMINATE",
                effective_date=date(2026, 1, 4), reason="Test termination")
            as_of = date(2026, 1, 4)
            batch = get_obligation_states_for_loans(workspace=self.workspace, loan_ids=[loan.pk], as_of_date=as_of)
            self.assertIsNone(batch[loan.pk].schedule_id)
            self.assertIsNone(get_active_repayment_schedule_as_of(loan, as_of))

    def test_empty_and_mismatched_context(self):
        with self.assertNumQueries(0), self.assertRaises(ValueError):
            get_obligation_states_for_loans(workspace=self.workspace, loan_ids=[], as_of_date=date(2026, 1, 1))
        with workspace_context(self.workspace.pk), self.assertNumQueries(0):
            self.assertEqual(get_obligation_states_for_loans(workspace=self.workspace, loan_ids=[], as_of_date=date(2026, 1, 1)), {})
            with self.assertRaises(ValueError):
                get_obligation_states_for_loans(workspace=SimpleNamespace(pk=self.workspace.pk+1), loan_ids=[], as_of_date=date(2026, 1, 1))

    def test_restricted_role_cannot_read_another_workspace_schedule(self):
        other = Company.objects.create(name="Other", schema_name="dashboard-other", owner=self.owner, creator=self.owner)
        with workspace_context(other.pk):
            foreign = self.loan(other)
            self.schedule(foreign, 1, 1)
        with workspace_context(self.workspace.pk):
            own = self.loan(self.workspace)
            self.schedule(own, 1, 1)
            role = connection.ops.quote_name("dashboard_read_" + uuid.uuid4().hex)
            with connection.cursor() as cursor:
                cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
                cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
                cursor.execute(f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {role}")
                cursor.execute(f"SET LOCAL ROLE {role}")
            try:
                batch = get_obligation_states_for_loans(workspace=self.workspace,
                    loan_ids=[own.pk, foreign.pk], as_of_date=date(2026, 2, 1))
                self.assertIsNotNone(batch[own.pk].schedule_id)
                self.assertIsNone(batch[foreign.pk].schedule_id)
                self.assertFalse(RepaymentScheduleVersion.objects.filter(loan_id=foreign.pk).exists())
            finally:
                with connection.cursor() as cursor:
                    cursor.execute("RESET ROLE")
            # TestCase rollback removes the temporary role and grants.
