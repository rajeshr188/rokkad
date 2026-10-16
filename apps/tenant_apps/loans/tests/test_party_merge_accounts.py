"""Duplicate consolidation preserves each agreement and financial source row."""
from copy import deepcopy
from unittest.mock import patch
from uuid import uuid4

from django.core.exceptions import ValidationError, PermissionDenied
from django.db import DatabaseError, transaction, connection
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from apps.orgs.audit import AuditLog
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.services.party_merge import merge_parties, repair_merged_party_accounts
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.borrower_corrections import corrected_ticket_source
from apps.tenant_apps.loans.services import khata_accounts
from apps.tenant_apps.loans.tests.test_khata_foundation import draft_args
from apps.tenant_apps.loans.tests import test_recorded_origination as origins
from apps.tenant_apps.loans.tests import test_recorded_history as histories
from apps.tenant_apps.loans.tests import test_closed_position_admission as closed
from apps.tenant_apps.loans.tests.test_khata_opening import OpeningFixture, STORAGES
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance


class PartyMergeAccountTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot

    @classmethod
    def get_test_schema_name(cls):
        return "party-merge-accounts"

    def setUp(self):
        super().setUp()
        self.target = Party.objects.create(display_name="Retained customer")
        self.snapshot = self.make_snapshot()
        self.loan = self.snapshot.loan
        self.source = self.loan.borrower

    def test_merge_moves_recorded_loan_without_changing_any_financial_source(self):
        before = m.PawnLoan.objects.filter(pk=self.loan.pk).values().get()
        event = deepcopy(self.snapshot.loan_event.payload)
        balance = get_pawn_loan_balance(self.loan, as_of_date=timezone.localdate())
        result = merge_parties(source=self.source, target=self.target, actor=self.actor)
        self.assertEqual((result.loans_moved, result.khata_accounts_moved), (1, 0))
        self.loan.refresh_from_db()
        after = m.PawnLoan.objects.filter(pk=self.loan.pk).values().get()
        self.assertEqual(after, dict(before, borrower_id=self.target.pk))
        self.snapshot.loan_event.refresh_from_db()
        self.assertEqual(self.snapshot.loan_event.payload, event)
        self.assertEqual(get_pawn_loan_balance(self.loan, as_of_date=timezone.localdate()), balance)
        log = self.loan.change_log.get(event_kind="BORROWER_CORRECTED")
        self.assertEqual(log.actor_id, self.actor.pk)
        self.assertTrue(log.metadata["borrower_correction"]["party_merge"])
        source, correction = corrected_ticket_source(self.loan, {"borrower_id": self.source.pk})
        self.assertEqual(source["borrower_id"], self.target.pk)
        self.assertEqual(correction.pk, log.pk)
        self.assertEqual(corrected_ticket_source(self.loan, {"borrower_id": self.target.pk})[0]["borrower_id"], self.target.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            self.loan.change_log.filter(pk=log.pk).update(reason="rewrite")

    def test_repair_is_exact_and_idempotent(self):
        # Reproduce the former merge: a profile was archived but its loan stayed.
        with patch("apps.tenant_apps.loans.services.party_merge.transfer_merged_party_accounts", return_value=(0, 0)):
            merge_parties(source=self.source, target=self.target, actor=self.actor)
        self.assertEqual(repair_merged_party_accounts(source=self.source, actor=self.actor), (1, 0))
        self.assertEqual(repair_merged_party_accounts(source=self.source, actor=self.actor), (0, 0))
        self.assertEqual(self.loan.change_log.filter(event_kind="BORROWER_CORRECTED").count(), 1)

    def test_merge_marks_existing_monitoring_stale(self):
        from apps.tenant_apps.loans.services.risk_snapshots import refresh_loan_risk_snapshot
        m.LoanMonitoringPolicy.objects.create(workspace=self.tenant, effective_from=self.loan.loan_date,
            version=1, compliance_profile="Test monitoring", ltv_warning_ratio="0.8",
            ltv_breach_ratio="0.9", ltv_critical_ratio="1", eligible_custody_states=["IN_VAULT"],
            severity_mapping={"WATCH": "LOW", "BREACH": "MEDIUM", "CRITICAL": "HIGH"})
        refresh_loan_risk_snapshot(self.loan.pk, as_of_date=timezone.localdate())
        merge_parties(source=self.source, target=self.target, actor=self.actor)
        self.assertEqual(m.LoanRiskSnapshot.objects.get(loan=self.loan).status, "STALE")

    def test_database_refuses_new_or_reassigned_loans_using_merged_duplicate(self):
        # Retain the stale source instance to emulate an already-open loan form.
        merge_parties(source=self.source, target=self.target, actor=self.actor)
        fields=dict(workspace=self.tenant, license=self.loan.license, series=self.loan.series,
            borrower=self.source, product_version=self.loan.product_version, loan_number=uuid4().hex,
            principal_amount=10000, monthly_interest_rate=2, tenure_months=3, loan_date=self.loan.loan_date)
        with self.assertRaisesMessage(DatabaseError, "retained customer"), transaction.atomic():
            m.PawnLoan.objects.create(**fields)
        with self.assertRaisesMessage(DatabaseError, "retained customer"), transaction.atomic():
            m.PawnLoan.objects.filter(pk=self.loan.pk).update(borrower=self.source)

    def test_khata_database_rejects_stale_duplicate_without_consuming_number(self):
        series = khata_accounts.create_series(workspace=self.tenant, actor=self.actor, code="KH", name="Khata")
        account = khata_accounts.create_draft(**draft_args(self.tenant, self.actor, self.source, series))
        merge_parties(source=self.source, target=self.target, actor=self.actor)
        series.refresh_from_db()
        counter=series.next_number
        with self.assertRaisesMessage(DatabaseError, "retained customer"), transaction.atomic():
            m.KhataAccount.objects.create(workspace=self.tenant, series=series, borrower=self.source,
                account_number="KH00002", created_by=self.actor, request_key=uuid4(), request_sha256="a"*64)
        with self.assertRaisesMessage(DatabaseError, "retained customer"), transaction.atomic():
            m.KhataAccount.objects.filter(pk=account.pk).update(borrower=self.source)
        series.refresh_from_db()
        self.assertEqual(series.next_number,counter)

    def test_draft_and_closed_ordinary_loans_move_without_combining_agreements(self):
        extra = []
        for state in ("DRAFT", "APPROVED", "CLOSED", "CANCELLED"):
            loan = m.PawnLoan.objects.create(workspace=self.tenant, license=self.loan.license,
                series=self.loan.series, borrower=self.source, product_version=self.loan.product_version,
                loan_number=uuid4().hex, state=state, principal_amount=self.loan.principal_amount,
                monthly_interest_rate=self.loan.monthly_interest_rate, tenure_months=self.loan.tenure_months,
                loan_date=self.loan.loan_date)
            extra.append(loan)
        result = merge_parties(source=self.source, target=self.target, actor=self.actor)
        self.assertEqual(result.loans_moved, 5)
        self.assertEqual(set(m.PawnLoan.objects.filter(borrower=self.target).values_list("pk", flat=True)),
            {self.loan.pk, *(loan.pk for loan in extra)})
        for loan in extra:
            loan.refresh_from_db()
            source, _ = corrected_ticket_source(loan, {"borrower_id": self.target.pk})
            self.assertEqual(source["borrower_id"], self.target.pk)

    def test_merge_failure_rolls_back_profile_archive_and_all_account_moves(self):
        with patch("apps.tenant_apps.loans.services.party_merge.PawnLoan.objects.filter", side_effect=ValidationError("failure")):
            with self.assertRaises(ValidationError):
                merge_parties(source=self.source, target=self.target, actor=self.actor)
        self.source.refresh_from_db()
        self.target.refresh_from_db()
        self.loan.refresh_from_db()
        self.assertEqual(self.source.status, "ACTIVE")
        self.assertEqual(self.loan.borrower_id, self.source.pk)
        self.assertFalse(self.target.metadata.get("merged_from_party_ids"))

    def test_khata_moves_only_current_borrower_and_keeps_issued_agreement(self):
        series = khata_accounts.create_series(workspace=self.tenant, actor=self.actor, code="KH", name="Khata")
        account = khata_accounts.create_draft(**draft_args(self.tenant, self.actor, self.source, series))
        before = m.KhataAccount.objects.filter(pk=account.pk).values().get()
        agreement = m.KhataAgreementRevision.objects.filter(account=account).values().get()
        with self.assertRaises(DatabaseError), transaction.atomic():
            m.KhataAccount.objects.filter(pk=account.pk).update(borrower=self.target)
        result = merge_parties(source=self.source, target=self.target, actor=self.actor)
        self.assertEqual(result.khata_accounts_moved, 1)
        self.assertEqual(m.KhataAccount.objects.filter(pk=account.pk).values().get(), dict(before, borrower_id=self.target.pk))
        self.assertEqual(m.KhataAgreementRevision.objects.filter(account=account).values().get(), agreement)
        log = AuditLog.objects.filter(data__party_merge__khata_account_id=account.pk).get()
        with self.assertRaises(DatabaseError), transaction.atomic():
            AuditLog.objects.filter(pk=log.pk).delete()

    def test_chained_new_merges_keep_correction_chain_and_all_accounts(self):
        merge_parties(source=self.source, target=self.target, actor=self.actor)
        final = Party.objects.create(display_name="Final retained customer")
        merge_parties(source=self.target, target=final, actor=self.actor)
        self.loan.refresh_from_db()
        self.assertEqual(corrected_ticket_source(self.loan, {"borrower_id": self.source.pk})[0]["borrower_id"], final.pk)
        self.assertEqual(self.loan.change_log.filter(event_kind="BORROWER_CORRECTED").count(), 2)

    def test_archived_target_and_unrecorded_repair_are_denied(self):
        self.target.status = "ARCHIVED"
        self.target.save(update_fields=["status"])
        with self.assertRaises(ValidationError):
            merge_parties(source=self.source, target=self.target, actor=self.actor)
        with self.assertRaises(ValidationError):
            repair_merged_party_accounts(source=self.source, actor=self.actor)
        with self.assertRaises(PermissionDenied):
            repair_merged_party_accounts(source=self.source, actor=None)


class PartyMergeClosedPositionTests(WorkspaceTestCase):
    setup_tenant = classmethod(origins.RecordedOriginationTests.setup_tenant.__func__)
    make_snapshot = origins.RecordedOriginationTests.make_snapshot
    prepare_history = histories.RecordedHistoryTests.prepare_history
    prepare_position = closed.ClosedPositionAdmissionTests.prepare_position
    admit_position = closed.ClosedPositionAdmissionTests.admit_position

    @classmethod
    def get_test_schema_name(cls):
        return "party-merge-closed"

    def test_closed_position_keeps_original_evidence_and_zero_balance_under_restricted_role(self):
        self.prepare_position()
        loan, _, _ = self.admit_position()
        source = loan.borrower
        target = Party.objects.create(display_name="Retained closed customer")
        before = m.PawnLoan.objects.filter(pk=loan.pk).values().get()
        origin = deepcopy(loan.historical_import.document)
        role = "merge_test_" + uuid4().hex
        with connection.cursor() as cursor:
            cursor.execute(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS')
            cursor.execute(f'GRANT USAGE ON SCHEMA public TO "{role}"')
            cursor.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO "{role}"')
            cursor.execute(f'GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO "{role}"')
            cursor.execute(f'SET LOCAL ROLE "{role}"')
        try:
            merge_parties(source=source, target=target, actor=self.actor)
            loan.refresh_from_db()
            self.assertEqual(m.PawnLoan.objects.filter(pk=loan.pk).values().get(), dict(before, borrower_id=target.pk))
            from apps.tenant_apps.loans.services.closed_position import read_position
            self.assertEqual(read_position(loan)["position"]["principal"], "0")
            self.assertEqual(loan.historical_import.document, origin)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoan.objects.filter(pk=loan.pk).update(principal_amount=100)
        finally:
            with connection.cursor() as cursor:
                cursor.execute('RESET ROLE')
                cursor.execute(f'DROP OWNED BY "{role}"')
                cursor.execute(f'DROP ROLE "{role}"')


@override_settings(STORAGES=STORAGES)
class PartyMergeActiveKhataTests(OpeningFixture, TestCase):
    def test_active_khata_preserves_operations_balances_and_custody(self):
        self.deposit()
        self.approve()
        self.payout()
        before = self.balance()
        from apps.tenancy.context import workspace_context
        with workspace_context(self.workspace.pk):
            target = Party.objects.create(display_name="Retained Khata borrower")
            operations = list(self.account.operations.order_by("pk").values())
            items = list(self.account.collateral.order_by("pk").values())
            result = merge_parties(source=self.borrower, target=target, actor=self.actor)
            self.assertEqual(result.khata_accounts_moved, 1)
            self.account.refresh_from_db()
            self.assertEqual(self.account.borrower_id, target.pk)
            self.assertEqual(list(self.account.operations.order_by("pk").values()), operations)
            self.assertEqual(list(self.account.collateral.order_by("pk").values()), items)
        self.assertEqual(self.balance(), before)


class PartyMergeAdmissionRaceTests(TransactionTestCase):
    def setUp(self):
        from apps.tenant_apps.loans.tests.test_khata_foundation import fixture
        from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
        from apps.tenancy.context import workspace_context
        from datetime import timedelta
        self.workspace,self.actor,self.source=fixture(uuid4().hex[:8])
        with workspace_context(self.workspace.pk):
            self.target=Party.objects.create(display_name="Retained race customer")
            license=m.LoanLicense.objects.create(workspace=self.workspace,name="Race",license_number=uuid4().hex,
                issued_on=timezone.localdate(),expires_on=timezone.localdate()+timedelta(days=365))
            series=m.LoanSeries.objects.create(license=license,name="Race",code="R")
            product=ensure_test_product_version(self.workspace)
            self.fields=dict(workspace_id=self.workspace.pk,license_id=license.pk,series_id=series.pk,
                borrower_id=self.source.pk,product_version_id=product.pk,loan_number=uuid4().hex,
                principal_amount=10000,monthly_interest_rate=2,tenure_months=3,loan_date=timezone.localdate())

    def test_admission_committing_first_is_included_in_merge(self):
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        from threading import Event
        from django.db import connections
        from apps.tenancy.context import workspace_context
        admitted,attempt,release=Event(),Event(),Event()
        def create():
            try:
                with workspace_context(self.workspace.pk):
                    loan=m.PawnLoan.objects.create(**self.fields)
                    admitted.set();assert release.wait(10)
                return loan.pk
            finally:connections.close_all()
        def merge():
            try:
                assert admitted.wait(10);attempt.set()
                with workspace_context(self.workspace.pk):
                    return merge_parties(source=self.source,target=self.target,actor=self.actor).loans_moved
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            created=pool.submit(create);merged=pool.submit(merge)
            try:
                self.assertTrue(attempt.wait(10))
                with self.assertRaises(TimeoutError):merged.result(timeout=0.2)
            finally:release.set()
            pk=created.result(timeout=15)
            self.assertEqual(merged.result(timeout=15),1)
        with workspace_context(self.workspace.pk):
            self.assertEqual(m.PawnLoan.objects.get(pk=pk).borrower_id,self.target.pk)

    def test_merge_committing_first_rejects_waiting_admission(self):
        from concurrent.futures import ThreadPoolExecutor, TimeoutError
        from threading import Event
        from django.db import connections
        from apps.tenancy.context import workspace_context
        merged,attempt,release=Event(),Event(),Event()
        def merge():
            try:
                with workspace_context(self.workspace.pk):
                    merge_parties(source=self.source,target=self.target,actor=self.actor)
                    merged.set();assert release.wait(10)
            finally:connections.close_all()
        def create():
            try:
                assert merged.wait(10);attempt.set()
                try:
                    with workspace_context(self.workspace.pk):m.PawnLoan.objects.create(**self.fields)
                except DatabaseError as exc:return "retained customer" in str(exc)
                return False
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            merging=pool.submit(merge);creating=pool.submit(create)
            try:
                self.assertTrue(attempt.wait(10))
                with self.assertRaises(TimeoutError):creating.result(timeout=0.2)
            finally:release.set()
            merging.result(timeout=15)
            self.assertTrue(creating.result(timeout=15))
        with workspace_context(self.workspace.pk):
            self.assertFalse(m.PawnLoan.objects.filter(borrower=self.source).exists())
