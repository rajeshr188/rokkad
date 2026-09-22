import importlib
import uuid
from contextlib import contextmanager
from datetime import date

from django.apps import apps
from django.contrib.auth import get_user_model
from django.db import connection, transaction, DatabaseError
from django.test import TestCase

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.models import (
    LoanLicense, LoanSeries, PawnLoan, PawnLoanEvent, PawnLoanApprovalSnapshot,
    RepaymentScheduleVersion, RepaymentObligation, LoanDocumentIssue,
)
from .factories import ensure_test_product_version


class HistoryEvidenceGuardTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.role = connection.ops.quote_name("history_guard_" + uuid.uuid4().hex)
        with connection.cursor() as c:
            c.execute(f"CREATE ROLE {cls.role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            c.execute(f"GRANT USAGE ON SCHEMA public TO {cls.role}")
            c.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {cls.role}")
            c.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {cls.role}")

    @classmethod
    def tearDownClass(cls):
        with connection.cursor() as c:
            c.execute("RESET ROLE")
            c.execute(f"DROP OWNED BY {cls.role}")
            c.execute(f"DROP ROLE {cls.role}")
        super().tearDownClass()

    @contextmanager
    def scoped(self, workspace):
        with transaction.atomic():
            with connection.cursor() as c: c.execute(f"SET LOCAL ROLE {self.role}")
            try:
                with workspace_context(workspace.pk): yield
            finally:
                with connection.cursor() as c: c.execute("RESET ROLE")

    def setUp(self):
        self.actor = get_user_model().objects.create_user(username=uuid.uuid4().hex)
        self.a, self.b = [Company.objects.create(name=x, schema_name=uuid.uuid4().hex,
            owner=self.actor, creator=self.actor) for x in ("History A", "History B")]
        self.loans = []
        for workspace in (self.a, self.b):
            with self.scoped(workspace):
                license = LoanLicense.objects.create(workspace=workspace, name="License", license_number="L",
                    issued_on=date(2020, 1, 1), expires_on=date(2030, 1, 1))
                series = LoanSeries.objects.create(license=license, name="Main", code="A")
                party = Party.objects.create(display_name="Borrower")
                product = ensure_test_product_version(workspace)
                for number in ("1", "2"):
                    self.loans.append(PawnLoan.objects.create(workspace=workspace, license=license,
                        series=series, borrower=party, product_version=product, loan_number=number,
                        principal_amount=1000, monthly_interest_rate=1))
        with self.scoped(self.a):
            self.event = self.make_event(self.loans[0])
            self.approval = PawnLoanApprovalSnapshot.objects.create(loan=self.loans[0], version=1,
                payload={"original": True}, fingerprint="a" * 64, approved_by=self.actor)
            self.schedule = RepaymentScheduleVersion.objects.create(workspace=self.a, loan=self.loans[0],
                source_event=self.event, version=1, contract_version="REPAYMENT-SCHEDULE-V1", fingerprint="b" * 64,
                disbursed_on=date(2026, 1, 1), maturity_date=date(2026, 4, 1), principal=1000,
                contractual_interest=30, created_by=self.actor)
            self.obligation = RepaymentObligation.objects.create(workspace=self.a, loan=self.loans[0],
                schedule_version=self.schedule, sequence=1, due_date=date(2026, 4, 1), principal_due=1000,
                interest_due=30, opening_principal=1000, closing_principal=0)

    def make_event(self, loan):
        return PawnLoanEvent.objects.create(loan=loan, event_kind="DISBURSAL",
            effective_date=date(2026, 1, 1), payload={"principal": "1000"},
            payload_fingerprint="c" * 64, idempotency_key=uuid.uuid4().hex, created_by=self.actor)

    def test_template_activation_under_restricted_role_rejects_foreign_inputs(self):
        from django.core.exceptions import ObjectDoesNotExist
        from apps.tenant_apps.loans.documents import starter_layout, built_in_print_profile
        from apps.tenant_apps.loans.services import LoanDocumentLayoutService, LoanDocumentPrintProfileService
        from apps.tenant_apps.loans.services.ticket_template_activation import use_ticket_template
        pairs = []
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        for workspace in (self.a, self.b):
            with self.scoped(workspace):
                Membership.objects.create(user=self.actor, company=workspace, role=owner_role)
                revision = LoanDocumentLayoutService.create_layout(workspace=workspace, document_type="loan_ticket",
                    name="Ticket", definition=starter_layout("loan_ticket", schema_version=4, layout_mode="ABSOLUTE_OVERLAY").canonical_dict(), actor=self.actor)
                definition = built_in_print_profile("LEGACY_BOTH_SIMPLEX").canonical_dict()
                profile = LoanDocumentPrintProfileService.create_profile(workspace=workspace, document_type="loan_ticket",
                    name=definition["name"], definition=definition, actor=self.actor)
                pairs.append((revision, profile))
        local, local_profile = pairs[0]
        foreign, foreign_profile = pairs[1]
        with self.scoped(self.a):
            for revision, profile, series in ((foreign, local_profile, None), (local, foreign_profile, None),
                                             (local, local_profile, self.loans[2].series)):
                with self.assertRaises(ObjectDoesNotExist):
                    use_ticket_template(workspace=self.a, revision=revision, profile_revision=profile, series=series,
                        actor=self.actor, layout_hash=revision.content_hash, profile_hash=profile.content_hash)
            use_ticket_template(workspace=self.a, revision=local, profile_revision=local_profile,
                actor=self.actor, layout_hash=local.content_hash, profile_hash=local_profile.content_hash)
            self.assertEqual(LoanDocumentLayoutService.resolve(workspace=self.a, document_type="loan_ticket"), local)
        with self.scoped(self.b):
            foreign.refresh_from_db()
            foreign_profile.refresh_from_db()
            self.assertEqual((foreign.state, foreign_profile.state), ("DRAFT", "DRAFT"))
            self.assertIsNone(LoanDocumentLayoutService.resolve(workspace=self.b, document_type="loan_ticket"))

    def test_document_snapshot_is_required_immutable_and_workspace_scoped(self):
        def record(**changes):
            values = dict(workspace=self.a, document_type="loan_ticket", source_type="PawnLoan",
                source_id=str(self.loans[0].pk), source_fingerprint=uuid.uuid4().hex,
                payload_schema_version=2, payload_hash="a" * 64, pdf_hash="b" * 64,
                artifact="test-evidence.pdf", issued_by=self.actor, source_snapshot={"schema_version": 2, "workspace_id": self.a.pk})
            values.update(changes)
            return LoanDocumentIssue(**values)

        with self.scoped(self.a):
            issue = record()
            issue.save()
            for snapshot in (None, {}, {"schema_version": 2, "workspace_id": self.b.pk}):
                with self.subTest(snapshot=snapshot), self.assertRaises(DatabaseError), transaction.atomic():
                    LoanDocumentIssue.objects.bulk_create([record(source_snapshot=snapshot)])
            with self.assertRaises(DatabaseError), transaction.atomic():
                LoanDocumentIssue.objects.filter(pk=issue.pk).update(source_snapshot=None)
            with self.assertRaises(DatabaseError), transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute("DELETE FROM loans_loandocumentissue WHERE id=%s", [issue.pk])
            legacy = record(payload_schema_version=1, source_snapshot=None)
            legacy.save()
            legacy.refresh_from_db()
            self.assertIsNone(legacy.source_snapshot)
            with self.assertRaises(DatabaseError), transaction.atomic():
                LoanDocumentIssue.objects.filter(pk=legacy.pk).update(source_snapshot=issue.source_snapshot)
        with self.scoped(self.b):
            self.assertFalse(LoanDocumentIssue.objects.filter(pk=issue.pk).exists())
            self.assertEqual(LoanDocumentIssue.objects.filter(pk=issue.pk).update(source_snapshot=None), 0)

    def test_party_document_selector_cannot_read_another_workspace(self):
        from django.core.exceptions import PermissionDenied
        from apps.tenant_apps.party.document_selectors import document_identity

        role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.create(company=self.a, user=self.actor, role=role)
        with self.scoped(self.a):
            with self.assertRaises(Party.DoesNotExist):
                document_identity(workspace=self.a, party_id=self.loans[2].borrower_id, actor=self.actor)
            with self.assertRaises(PermissionDenied):
                document_identity(workspace=self.b, party_id=self.loans[2].borrower_id, actor=self.actor)

    def test_all_profile_tables_have_enabled_guards_and_forced_rls(self):
        names = importlib.import_module("apps.tenant_apps.loans.migrations.0008_immutable_history_evidence").MODELS
        self.assertEqual(len(names), 15)
        with connection.cursor() as c:
            for name in names:
                table = apps.get_model("loans", name)._meta.db_table
                c.execute("SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE oid=%s::regclass", [table])
                self.assertEqual(c.fetchone(), (True, True), name)
                c.execute("SELECT tgenabled, tgtype FROM pg_trigger WHERE tgrelid=%s::regclass AND tgname='loans_history_evidence_guard'", [table])
                self.assertEqual(c.fetchone(), ("O", 31), name)

    def test_raw_update_delete_and_actor_clearing_are_denied(self):
        with self.scoped(self.a):
            for obj in (self.event, self.approval, self.schedule, self.obligation):
                table = connection.ops.quote_name(obj._meta.db_table)
                for sql in (f"UPDATE {table} SET workspace_id=workspace_id WHERE id=%s", f"DELETE FROM {table} WHERE id=%s"):
                    with self.subTest(table=table, sql=sql), self.assertRaises(DatabaseError), transaction.atomic():
                        with connection.cursor() as c: c.execute(sql, [obj.pk])
            with self.assertRaises(DatabaseError), transaction.atomic():
                PawnLoanApprovalSnapshot.objects.filter(pk=self.approval.pk).update(approved_by=None)
            self.assertTrue(PawnLoanEvent.objects.filter(pk=self.event.pk).exists())

    def test_insert_rejects_foreign_workspace_reference(self):
        with self.scoped(self.a), self.assertRaises(DatabaseError), transaction.atomic():
            PawnLoanEvent.objects.bulk_create([PawnLoanEvent(workspace=self.a, loan=self.loans[2],
                event_kind="DISBURSAL", effective_date=date(2026, 1, 1), payload={},
                payload_fingerprint="x" * 64, idempotency_key=uuid.uuid4().hex)])

    def test_insert_rejects_same_workspace_wrong_loan_schedule(self):
        with self.scoped(self.a), self.assertRaises(DatabaseError), transaction.atomic():
            RepaymentObligation.objects.bulk_create([RepaymentObligation(workspace=self.a, loan=self.loans[1],
                schedule_version=self.schedule, sequence=2, due_date=date(2026, 4, 1), principal_due=100,
                interest_due=0, opening_principal=100, closing_principal=0)])

    def test_other_workspace_cannot_see_or_change_evidence(self):
        with self.scoped(self.b):
            self.assertFalse(PawnLoanEvent.objects.filter(pk=self.event.pk).exists())
            self.assertEqual(PawnLoanEvent.objects.filter(pk=self.event.pk).update(payload={}), 0)
            with connection.cursor() as c:
                c.execute("DELETE FROM loans_pawnloanevent WHERE id=%s", [self.event.pk])
                self.assertEqual(c.rowcount, 0)

    def test_append_reversal_does_not_mutate_original_and_loans_remain_mutable(self):
        with self.scoped(self.a):
            reversal = PawnLoanEvent.objects.create(loan=self.loans[0], event_kind="REVERSAL",
                effective_date=date(2026, 1, 2), payload={"reversal": True}, payload_fingerprint="r" * 64,
                idempotency_key=uuid.uuid4().hex, reversal_of=self.event, created_by=self.actor)
            self.assertEqual(reversal.reversal_of_id, self.event.pk)
            self.assertEqual(PawnLoan.objects.filter(pk=self.loans[0].pk).update(monthly_interest_rate=2), 1)
            self.event.refresh_from_db()
            self.assertEqual(self.event.payload, {"principal": "1000"})
