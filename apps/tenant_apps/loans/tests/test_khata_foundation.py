import uuid
from contextlib import contextmanager
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import start_workspace_trial, expire_workspace_trial
from apps.tenant_apps.loans.models import (
    KhataSeries, KhataAccount, KhataAgreementRevision, LoanLicense, LoanSeries,
    LoanNumberSequence, PawnLoan,
)
from apps.tenant_apps.loans.selectors.khata import preview_draft_interest
from apps.tenant_apps.loans.services import khata_accounts as service
from apps.tenant_apps.party.models import Party


def fixture(suffix):
    actor = get_user_model().objects.create_user(username="khata-owner-" + suffix)
    workspace = Company.objects.create(name="Fictional khata " + suffix, schema_name="khata-" + suffix, owner=actor, creator=actor)
    role, _ = Role.objects.get_or_create(name="Owner")
    Membership.objects.get_or_create(user=actor, company=workspace, defaults={"role": role})
    start_workspace_trial(workspace)
    with workspace_context(workspace.pk):
        borrower = Party.objects.create(display_name="Fictional khata borrower")
    return workspace, actor, borrower


def draft_args(workspace, actor, borrower, series):
    return dict(workspace=workspace, actor=actor, borrower_id=borrower.pk, series_id=series.pk,
        request_key=uuid.uuid4(), intended_on=timezone.localdate(), agreed_limit="10000000", monthly_rate="1",
        ltv="0.75", frequency="MONTHLY", lender_name="Fictional lender", lender_address="Fictional address")


class KhataFoundationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.workspace, cls.actor, cls.borrower = fixture(uuid.uuid4().hex[:8])
        cls.other_workspace, cls.other_actor, cls.other_borrower = fixture(uuid.uuid4().hex[:8])
        cls.series = service.create_series(workspace=cls.workspace, actor=cls.actor, code="KH", name="Independent")
        cls.other_series = service.create_series(workspace=cls.other_workspace, actor=cls.other_actor, code="KH", name="Other")
        with workspace_context(cls.other_workspace.pk):
            cls.other_license = LoanLicense.objects.create(workspace=cls.other_workspace, name="Other licence", license_number="OTHER",
                issued_on=timezone.localdate() - timedelta(days=1), expires_on=timezone.localdate() + timedelta(days=365))

    def args(self, **changes):
        return dict(draft_args(self.workspace, self.actor, self.borrower, self.series), **changes)

    def test_independent_numbering_preview_idempotence_and_other_workspace(self):
        for _ in range(2):
            self.assertEqual(service.preview_number(workspace=self.workspace, actor=self.actor, series_id=self.series.pk), "KH00001")
        args = self.args()
        account = service.create_draft(**args)
        self.assertEqual(service.create_draft(**args).pk, account.pk)
        with self.assertRaisesMessage(ValueError, "different instructions"):
            service.create_draft(**{**args, "monthly_rate": "2"})
        with workspace_context(self.workspace.pk):
            self.series.refresh_from_db()
            self.assertEqual(self.series.next_number, 2)
            self.assertTrue(self.series.has_issued_number)
            self.assertEqual(KhataAgreementRevision.objects.count(), 1)
            self.assertEqual(LoanNumberSequence.objects.count(), 0)
            self.assertEqual(PawnLoan.objects.count(), 0)
        other = service.create_draft(**draft_args(self.other_workspace, self.other_actor, self.other_borrower, self.other_series))
        self.assertEqual(other.account_number, account.account_number)

    def test_licence_associated_series_uses_own_counter_and_scope(self):
        with workspace_context(self.workspace.pk):
            license = LoanLicense.objects.create(workspace=self.workspace, name="Fictional licence", license_number="TEST",
                issued_on=timezone.localdate() - timedelta(days=1), expires_on=timezone.localdate() + timedelta(days=365))
        series = service.create_series(workspace=self.workspace, actor=self.actor, code="KHA", name="Associated", prefix="KHA", license_id=license.pk)
        account = service.create_draft(**{**self.args(), "series_id": series.pk})
        self.assertEqual(account.account_number, "KHA00001")
        with self.assertRaisesMessage(ValueError, "this workspace"):
            service.create_series(workspace=self.workspace, actor=self.actor, code="BAD", name="Wrong", prefix="BAD", license_id=self.other_license.pk)
        with workspace_context(self.workspace.pk):
            LoanLicense.objects.filter(pk=license.pk).update(is_active=False)
        with self.assertRaisesMessage(ValueError, "licence"):
            service.create_draft(**{**self.args(), "series_id": series.pk})
        self.assertEqual(service.create_draft(**self.args()).account_number, "KH00001")

    def test_invalid_terms_roll_back_number_and_account(self):
        with self.assertRaises(ValidationError):
            service.create_draft(**{**self.args(), "lender_address": "x" * 1001})
        with workspace_context(self.workspace.pk):
            self.series.refresh_from_db()
            self.assertEqual(self.series.next_number, 1)
            self.assertFalse(self.series.has_issued_number)
            self.assertEqual(KhataAccount.objects.count(), 0)

    def test_cancellation_never_recycles_number_or_unfreezes_series(self):
        first = service.create_draft(**self.args())
        service.cancel_draft(workspace=self.workspace, actor=self.actor, account_id=first.pk, reason="Borrower cancelled")
        service.cancel_draft(workspace=self.workspace, actor=self.actor, account_id=first.pk, reason="Borrower cancelled")
        self.assertEqual(service.create_draft(**self.args()).account_number, "KH00002")
        with workspace_context(self.workspace.pk):
            with self.assertRaises(DatabaseError), transaction.atomic():
                KhataSeries.objects.filter(pk=self.series.pk).update(prefix="NEW")
            with self.assertRaises(DatabaseError), transaction.atomic():
                KhataAccount.objects.filter(pk=first.pk).update(state="DRAFT", cancelled_at=None, cancelled_by=None, cancellation_reason="")

    def test_association_freezes_in_both_modes(self):
        with workspace_context(self.workspace.pk):
            license = LoanLicense.objects.create(workspace=self.workspace, name="Local licence", license_number="LOCAL",
                issued_on=timezone.localdate(), expires_on=timezone.localdate() + timedelta(days=365))
        associated = service.create_series(workspace=self.workspace, actor=self.actor, code="LINK", name="Linked", prefix="LINK", license_id=license.pk)
        service.create_draft(**self.args())
        service.create_draft(**{**self.args(), "series_id": associated.pk})
        with workspace_context(self.workspace.pk):
            for series_id, license_id in ((self.series.pk, license.pk), (associated.pk, None)):
                with self.assertRaisesMessage(DatabaseError, "association"), transaction.atomic():
                    KhataSeries.objects.filter(pk=series_id).update(license_id=license_id)

    def test_number_ceiling_and_ordinary_prefix_collision(self):
        series = service.create_series(workspace=self.workspace, actor=self.actor, code="ONE", name="One", prefix="ONE", width=1, maximum_number=1)
        service.create_draft(**{**self.args(), "series_id": series.pk})
        with self.assertRaisesMessage(ValueError, "exhausted"):
            service.create_draft(**{**self.args(), "series_id": series.pk})
        with self.assertRaises(ValueError):
            service.create_series(workspace=self.workspace, actor=self.actor, code="BAD", name="Bad", width=2, maximum_number=100)
        with self.assertRaises(ValidationError):
            service.create_series(workspace=self.workspace, actor=self.actor, code="DUP", name="Duplicate", prefix="KH")
        with workspace_context(self.workspace.pk):
            license = LoanLicense.objects.create(workspace=self.workspace, name="Existing ordinary licence", license_number="PAWN",
                issued_on=timezone.localdate(), expires_on=timezone.localdate() + timedelta(days=365))
            ordinary = LoanSeries.objects.create(workspace=self.workspace, license=license, code="PAWN", name="Ordinary")
            sequence = LoanNumberSequence.objects.create(workspace=self.workspace, series=ordinary, document_kind="PAWN_LOAN", prefix="PN")
        with self.assertRaisesMessage(ValueError, "ordinary-loan"):
            service.create_series(workspace=self.workspace, actor=self.actor, code="PN", name="Conflict", prefix="PN")
        service.create_draft(**self.args())
        with workspace_context(self.workspace.pk):
            sequence.refresh_from_db()
            self.assertEqual(sequence.next_number, 1)

    def test_proposals_append_and_preview_uses_latest_only(self):
        account = service.create_draft(**self.args())
        args = self.args()
        args.pop("series_id"); args.pop("borrower_id")
        args.update(account_id=account.pk, expected_revision=1, monthly_rate="2", reason="Agreed revised proposal")
        revision = service.propose_revision(**args)
        self.assertEqual(revision.number, 2)
        self.assertEqual(service.propose_revision(**args).pk, revision.pk)
        with self.assertRaisesMessage(ValueError, "changed"):
            service.propose_revision(**{**args, "request_key": uuid.uuid4()})
        periods = preview_draft_interest(workspace=self.workspace, actor=self.actor, account_id=account.pk, through=timezone.localdate())
        self.assertEqual(periods[0].charge, 200000)
        with workspace_context(self.workspace.pk):
            self.assertEqual(account.agreement_revisions.count(), 2)
            self.assertEqual(account.agreement_revisions.get(number=1).monthly_rate, 1)
            for action in (lambda: KhataAgreementRevision.objects.filter(pk=revision.pk).update(monthly_rate=3),
                           lambda: KhataAgreementRevision.objects.filter(pk=revision.pk).delete()):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    action()

    def test_permissions_date_and_commercial_gate(self):
        outsider = get_user_model().objects.create_user(username="khata-outsider")
        with self.assertRaises(PermissionDenied):
            service.create_draft(**{**self.args(), "actor": outsider})
        with self.assertRaises(PermissionDenied):
            service.create_series(workspace=self.workspace, actor=outsider, code="NO", name="No", prefix="NO")
        with self.assertRaisesMessage(ValueError, "today"):
            service.create_draft(**{**self.args(), "intended_on": timezone.localdate() - timedelta(days=1)})
        with self.assertRaises(ValueError):
            service.create_draft(**{**self.args(), "borrower_id": self.other_borrower.pk})
        expire_workspace_trial(self.workspace, days_ago=30)
        with self.assertRaises(PermissionDenied):
            service.create_draft(**self.args())


class KhataRLSBoundaryTests(TestCase):
    """Raw DML uses a restricted role; service behavior is covered above."""

    @classmethod
    def setUpTestData(cls):
        KhataFoundationTests.setUpTestData.__func__(cls)
        cls.account = service.create_draft(**draft_args(cls.workspace, cls.actor, cls.borrower, cls.series))
        cls.other_account = service.create_draft(**draft_args(cls.other_workspace, cls.other_actor, cls.other_borrower, cls.other_series))
        cls.runtime_role = "khata_rls_" + uuid.uuid4().hex
        quoted = connection.ops.quote_name(cls.runtime_role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {quoted} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {quoted}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {quoted}")

    @contextmanager
    def runtime(self):
        with connection.cursor() as cursor:
            cursor.execute(f"SET LOCAL ROLE {connection.ops.quote_name(self.runtime_role)}")
        try:
            yield
        finally:
            with connection.cursor() as cursor:
                cursor.execute("RESET ROLE")

    def test_forced_rls_unset_foreign_and_forged_parent_scope(self):
        models = (KhataSeries, KhataAccount, KhataAgreementRevision)
        with self.runtime():
            for model in models:
                self.assertEqual(model.objects.count(), 0)
            with self.assertRaises(DatabaseError), transaction.atomic():
                KhataSeries.objects.bulk_create([KhataSeries(workspace=self.workspace,
                    code="UNSET", name="No context", prefix="UNSET", created_by=self.actor)])
            with workspace_context(self.workspace.pk):
                for model in models:
                    self.assertEqual(model.objects.count(), 1)
                    with self.assertRaises(DatabaseError), transaction.atomic():
                        model.objects.all().update(workspace_id=self.other_workspace.pk)
                self.assertFalse(KhataAccount.objects.filter(pk=self.other_account.pk).exists())
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataSeries.objects.bulk_create([KhataSeries(workspace=self.workspace, license=self.other_license,
                        code="FORGED", name="Forged", prefix="FORGED", created_by=self.actor)])
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataAccount.objects.bulk_create([KhataAccount(workspace=self.workspace, series=self.other_series,
                        borrower=self.borrower, account_number="KH00002", created_by=self.actor,
                        request_key=uuid.uuid4(), request_sha256="a" * 64)])
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataAccount.objects.bulk_create([KhataAccount(workspace=self.workspace, series=self.series,
                        borrower=self.other_borrower, account_number="KH00002", created_by=self.actor,
                        request_key=uuid.uuid4(), request_sha256="a" * 64)])
                with self.assertRaises(DatabaseError), transaction.atomic():
                    KhataAgreementRevision.objects.bulk_create([KhataAgreementRevision(workspace=self.workspace,
                        account=self.other_account, number=2, intended_on=timezone.localdate(), agreed_limit=100,
                        monthly_rate=1, ltv="0.75", frequency="MONTHLY", lender_name="Fictional", lender_address="Fictional",
                        reason="Forged parent", request_key=uuid.uuid4(), request_sha256="a" * 64, created_by=self.actor)])

    def test_raw_immutability_counters_and_lifecycle_guard(self):
        with workspace_context(self.workspace.pk), self.runtime():
            changes = [
                lambda: KhataSeries.objects.filter(pk=self.series.pk).update(has_issued_number=False),
                lambda: KhataSeries.objects.filter(pk=self.series.pk).update(next_number=1),
                lambda: KhataSeries.objects.filter(pk=self.series.pk).update(license_id=self.other_license.pk),
                lambda: KhataAccount.objects.filter(pk=self.account.pk).update(state="ACTIVE"),
                lambda: KhataAccount.objects.filter(pk=self.account.pk).update(account_number="EDITED"),
                lambda: KhataAgreementRevision.objects.all().update(agreed_limit=1),
                lambda: KhataAgreementRevision.objects.all().delete(),
            ]
            for change in changes:
                with self.assertRaises(DatabaseError), transaction.atomic():
                    change()
            self.assertEqual(KhataAccount.objects.get(pk=self.account.pk).state, "DRAFT")
