"""A reversed disbursal retains evidence and permits a corrected new attempt."""
from copy import deepcopy
from decimal import Decimal
from datetime import timedelta
from tempfile import TemporaryDirectory
from unittest.mock import patch
import uuid

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, connections, transaction
from django.test import TransactionTestCase, override_settings

from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.services import (
    CollateralDraftInput, UpdatePawnDraftCommand, approve_pawn_loan,
    disburse_pawn_loan, reopen_pawn_loan, reverse_pawn_loan_event, update_pawn_draft,
    preview_pawn_loan_accruals,
)
from apps.tenant_apps.loans.services.obligations import reconcile_loan_obligations
from apps.tenant_apps.loans.services.pawn_tranches import get_pawn_principal_tranche_balances
from apps.tenant_apps.loans.tests import test_collateral_reappraisal as fixtures


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RedisbursementTests(WorkspaceTestCase):
    setup_tenant = classmethod(fixtures.CollateralReappraisalTests.setup_tenant.__func__)
    make_loan = fixtures.CollateralReappraisalTests.make_loan

    @classmethod
    def get_test_schema_name(cls):
        return "redisbursement"

    def setUp(self):
        self.media = TemporaryDirectory()
        self.addCleanup(self.media.cleanup)
        setting = override_settings(MEDIA_ROOT=self.media.name)
        setting.enable()
        self.addCleanup(setting.disable)
        age = 1 if self._testMethodName == "test_historical_tranches_use_the_attempt_effective_on_that_day" else 0
        self.make_loan(method="LATEST_APPRAISAL", age_days=age, product_index=2)
        self.loan.refresh_from_db()
        self.first = self.loan.disbursal_snapshot
        self.original_event = deepcopy(self.first.loan_event.payload)
        self.original_evidence = deepcopy(self.first.evidence)

    def correct(self, amount="1100", *, approve=True):
        reversal = reverse_pawn_loan_event(self.loan.disbursal_snapshot.loan_event_id,
            actor=self.actor, reason="Correct amount entered in error")
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan), ())
        self.assertEqual(reconcile_loan_obligations(self.loan).principal_remaining, 0)
        reopen_pawn_loan(self.loan.pk, reason="Correct original amount", actor=self.actor)
        item = self.loan.collateral_items.get()
        self.loan = update_pawn_draft(self.loan.pk, UpdatePawnDraftCommand(
            borrower_id=self.loan.borrower_id, principal_amount=Decimal(amount),
            monthly_interest_rate=Decimal("2"), loan_date=self.today, tenure_months=12,
            collateral=(CollateralDraftInput(collateral_item_id=item.pk, description=item.description,
                metal=item.metal, gross_weight=item.gross_weight, net_weight=item.net_weight,
                purity_percentage=item.purity_percentage, latest_appraised_value=Decimal("2000"),
                allocated_principal=Decimal(amount)),)), actor=self.actor)
        if approve:
            approve_pawn_loan(self.loan.pk, actor=self.actor)
        return reversal

    def disburse(self):
        return disburse_pawn_loan(self.loan.pk, effective_date=self.today, actor=self.actor)

    def test_corrected_disbursal_preserves_original_and_uses_new_amount_everywhere(self):
        reversal = self.correct()
        result = self.disburse()
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "ACTIVE")
        self.assertNotEqual(result.loan_event.pk, self.first.loan_event_id)
        self.assertEqual(self.loan.loan_number, result.loan.loan_number)
        self.assertEqual(self.loan.disbursal_snapshot_id, result.disbursal_snapshot.pk)
        self.assertEqual(self.loan.policy_snapshot_id, result.policy_snapshot.pk)
        self.assertEqual(self.loan.disbursal_snapshots.count(), 2)
        self.assertEqual(self.loan.policy_snapshots.count(), 2)
        self.first.refresh_from_db()
        self.assertEqual(self.first.loan_event.payload, self.original_event)
        self.assertEqual(self.first.evidence, self.original_evidence)
        self.assertEqual(reversal.original_event.pk, self.first.loan_event_id)
        self.assertEqual(list(self.loan.repayment_schedules.order_by("version").values_list("version", "principal")),
                         [(1, Decimal("1000")), (2, Decimal("1100"))])
        self.assertEqual(reconcile_loan_obligations(self.loan).principal_remaining, Decimal("1100"))
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.today).principal_outstanding, Decimal("1100"))
        self.assertEqual(get_pawn_principal_tranche_balances(self.loan)[0].initial_principal, Decimal("1100"))
        accrual = preview_pawn_loan_accruals(self.loan.pk, as_of_date=self.today)[0]
        self.assertEqual(accrual.lines[0].principal_base, Decimal("1100"))
        retried = self.disburse()
        self.assertTrue(retried.already_disbursed)
        self.assertEqual(retried.loan_event.pk, result.loan_event.pk)
        self.assertEqual(self.loan.loan_events.count(), 3)

    def test_equal_amount_same_day_is_a_new_attempt_and_can_be_corrected_again(self):
        self.correct("1000")
        second = self.disburse()
        self.loan.refresh_from_db()
        self.assertNotEqual(second.loan_event.idempotency_key, self.first.loan_event.idempotency_key)
        self.correct("1200")
        third = self.disburse()
        self.assertEqual(third.disbursal_snapshot.gross_principal, Decimal("1200"))
        self.assertEqual(self.loan.repayment_schedules.count(), 3)
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=self.today).principal_outstanding, Decimal("1200"))

    def test_partial_failure_rolls_back_new_evidence_and_current_pointers(self):
        self.correct()
        with patch("apps.tenant_apps.loans.services.pawn_disbursal.persist_disbursal_repayment_schedule", side_effect=ValueError("failure")):
            with self.assertRaisesMessage(ValueError, "failure"):
                self.disburse()
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, "APPROVED")
        self.assertEqual(self.loan.policy_snapshot_id, self.first.policy_snapshot_id)
        self.assertEqual(self.loan.disbursal_snapshot_id, self.first.pk)
        self.assertEqual(self.loan.policy_snapshots.count(), 1)
        self.assertEqual(self.loan.loan_events.count(), 2)
        self.assertEqual(self.loan.repayment_schedules.count(), 1)
        self.assertFalse(self.disburse().already_disbursed)

    def test_disbursal_permission_is_still_required(self):
        self.correct()
        from django.contrib.auth import get_user_model
        outsider = get_user_model().objects.create_user(username="not-member")
        with self.assertRaises(PermissionDenied):
            disburse_pawn_loan(self.loan.pk, effective_date=self.today, actor=outsider)
        self.assertEqual(self.loan.disbursal_snapshots.count(), 1)

    def test_historical_tranches_use_the_attempt_effective_on_that_day(self):
        self.correct()
        self.disburse()
        historical = get_pawn_principal_tranche_balances(self.loan, as_of_date=self.today - timedelta(days=1))
        current = get_pawn_principal_tranche_balances(self.loan, as_of_date=self.today)
        self.assertEqual(historical[0].initial_principal, Decimal("1000"))
        self.assertEqual(current[0].initial_principal, Decimal("1100"))

    def test_owner_combined_review_corrects_and_ticket_uses_new_approval(self):
        from apps.tenant_apps.loans.services.loan_workflow import make_review, review_and_disburse
        from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
        self.correct(approve=False)
        self.tenant.loan_workflow = "SIMPLE"
        self.tenant.save(update_fields=["loan_workflow"])
        _, token = make_review(self.loan)
        result = review_and_disburse(self.loan.pk, actor=self.actor, effective_date=self.today, token=token)
        self.assertEqual(result.disbursal_snapshot.approval_snapshot.version, 2)
        self.assertEqual(result.disbursal_snapshot.gross_principal, Decimal("1100"))
        payload = PawnLoanDocumentProjectionBuilder.loan_ticket(result.loan)
        self.assertIn(result.disbursal_snapshot.approval_snapshot.fingerprint, str(payload))
        retry = review_and_disburse(self.loan.pk, actor=self.actor, effective_date=self.today, token=token)
        self.assertTrue(retry.already_disbursed)
        self.assertEqual(retry.loan_event.pk, result.loan_event.pk)

    def test_restricted_runtime_can_correct_but_cannot_cross_link_snapshots(self):
        self.correct()
        other = PawnLoan.objects.create(workspace=self.tenant, license=self.loan.license,
            series=self.loan.series, borrower=self.loan.borrower, product_version=self.loan.product_version,
            loan_number="OTHER", principal_amount=1000, monthly_interest_rate=2, loan_date=self.today)
        role = connection.ops.quote_name("redisbursement_" + uuid.uuid4().hex)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {role}")
            cursor.execute(f"SET LOCAL ROLE {role}")
        try:
            for field, pk in (("policy_snapshot_id", self.first.policy_snapshot_id), ("disbursal_snapshot_id", self.first.pk)):
                with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(f"UPDATE loans_pawnloan SET {field}=%s WHERE id=%s", [pk, other.pk])
            result = self.disburse()
            self.assertEqual(result.disbursal_snapshot.gross_principal, Decimal("1100"))
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")
                cursor.execute(f"DROP OWNED BY {role}")
                cursor.execute(f"DROP ROLE {role}")


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                           "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class RedisbursementConcurrencyTests(TransactionTestCase):
    make_loan = fixtures.CollateralReappraisalTests.make_loan
    correct = RedisbursementTests.correct

    def test_competing_corrections_activate_once(self):
        from concurrent.futures import ThreadPoolExecutor
        from threading import Barrier
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Company, Membership, Role
        from apps.tenancy.context import workspace_context

        self.actor = get_user_model().objects.create_user(username=uuid.uuid4().hex)
        self.tenant = Company.objects.create(name="Concurrent correction", schema_name=uuid.uuid4().hex,
            owner=self.actor, creator=self.actor)
        Membership.objects.create(user=self.actor, company=self.tenant, role=Role.objects.get_or_create(name="Owner")[0])
        with TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            with workspace_context(self.tenant.pk):
                self.make_loan(method="LATEST_APPRAISAL", age_days=0, product_index=2)
                self.correct()
            barrier = Barrier(2)

            def issue():
                try:
                    with workspace_context(self.tenant.pk):
                        barrier.wait(timeout=10)
                        result = disburse_pawn_loan(self.loan.pk, effective_date=self.today, actor=self.actor)
                        return result.loan_event.pk, result.already_disbursed
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _: issue(), range(2)))
            self.assertEqual(results[0][0], results[1][0])
            self.assertEqual({result[1] for result in results}, {False, True})
            with workspace_context(self.tenant.pk):
                self.assertEqual(self.loan.loan_events.count(), 3)
                self.assertEqual(self.loan.disbursal_snapshots.count(), 2)
                self.assertEqual(self.loan.repayment_schedules.count(), 2)
