import hashlib
import re
import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.exceptions import PermissionDenied
from django.db import DatabaseError, connection, connections, transaction
from django.http import Http404
from django.test import TestCase, TransactionTestCase, RequestFactory, override_settings

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataSeries, KhataSeriesStatusChange, KhataOperation
from apps.tenant_apps.loans.services import khata_series as service, khata_accounts as accounts
from apps.tenant_apps.loans.services import khata_recovery as recovery
from apps.tenant_apps.loans.web import khata_series as web
from . import test_khata_foundation as foundation, test_khata_opening as opening
from .test_khata_corrections import CorrectionFixture
from . import test_khata_recovery as recovery_tests


class SeriesFixture:
    def setUp(self):
        super().setUp()
        self.workspace, self.actor, self.borrower = foundation.fixture(uuid.uuid4().hex[:8])
        self.series = accounts.create_series(workspace=self.workspace, actor=self.actor, code="KH", name="Status test")

    def preview(self):
        return service.preview(workspace=self.workspace, actor=self.actor, series_id=self.series.pk)

    def change_args(self, to="PAUSED"):
        return dict(workspace=self.workspace, actor=self.actor, series_id=self.series.pk, to_status=to,
                    reason="Reviewed lending availability", request_key=uuid.uuid4(), review_hash=self.preview()["review_hash"])

    def change(self, to="PAUSED"):
        return service.change_status(**self.change_args(to))


@override_settings(STORAGES=opening.STORAGES)
class KhataSeriesTests(SeriesFixture, TestCase):
    def test_pause_resume_preserves_number_and_association_and_retry(self):
        draft = accounts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        args = self.change_args()
        first = service.change_status(**args)
        self.assertEqual(service.change_status(**args).pk, first.pk)
        with self.assertRaisesMessage(ValueError, "different instructions"):
            service.change_status(**{**args, "reason": "Changed"})
        with self.assertRaisesMessage(ValueError, "inactive"):
            accounts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.change("ACTIVE")
        # Old successful retry does not pause again after a later resume.
        self.assertEqual(service.change_status(**args).pk, first.pk)
        next_draft = accounts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.assertEqual((draft.account_number, next_draft.account_number), ("KH00001", "KH00002"))
        with workspace_context(self.workspace.pk):
            self.series.refresh_from_db()
            self.assertTrue(self.series.is_active)
            self.assertIsNone(self.series.license_id)
            self.assertEqual(KhataSeriesStatusChange.objects.count(), 2)
            self.assertEqual(KhataOperation.objects.count(), 0)

    def test_retirement_terminal_and_prefix_cannot_be_reused(self):
        self.change("RETIRED")
        with workspace_context(self.workspace.pk):
            self.series.refresh_from_db()
            self.assertFalse(self.series.is_active)
            self.assertIsNotNone(self.series.retired_at)
            self.assertEqual(service.available_transitions(self.series), ())
        with self.assertRaisesMessage(ValueError, "permanent"):
            self.change("ACTIVE")
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            accounts.create_series(workspace=self.workspace, actor=self.actor, code="NEW", name="Replacement", prefix="KH")

    def test_stale_review_after_transition_or_number_allocation(self):
        args = self.change_args()
        accounts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        with self.assertRaisesMessage(ValueError, "changed after review"):
            service.change_status(**args)
        args = self.change_args("RETIRED")
        self.change()
        with self.assertRaisesMessage(ValueError, "changed after review"):
            service.change_status(**args)

    def test_reason_permissions_and_direct_projection_rewrites(self):
        args = self.change_args()
        for reason in (" ", "x"*2001):
            with self.assertRaises(ValueError):
                service.change_status(**{**args, "reason": reason})
        other, actor, borrower = foundation.fixture(uuid.uuid4().hex[:8])
        with self.assertRaises(PermissionDenied):
            service.change_status(**{**args, "actor": actor})
        self.change()
        with workspace_context(self.workspace.pk):
            for callback in (lambda: KhataSeries.objects.filter(pk=self.series.pk).update(is_active=True),
                             lambda: KhataSeriesStatusChange.objects.all().update(reason="Rewrite"),
                             lambda: KhataSeriesStatusChange.objects.all().delete()):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    callback()

    def request(self, data=None, method="post", actor=None):
        request=getattr(RequestFactory(), method)("/", data or {})
        request.workspace=self.workspace;request.user=actor or self.actor
        with workspace_context(self.workspace.pk):
            return web.status(request,self.series.pk)

    def test_signed_review_confirm_edit_retry_tamper_and_actor(self):
        response=self.request(dict(request_key=uuid.uuid4(),to_status="PAUSED",reason="Temporary halt"))
        self.assertContains(response,"Confirm pause")
        token=re.search(r'name="review_token" value="([^"]+)"',response.content.decode())[1]
        with workspace_context(self.workspace.pk):self.assertFalse(KhataSeriesStatusChange.objects.exists())
        self.assertContains(self.request(dict(review_token=token,edit="1")),"Temporary halt")
        self.assertContains(self.request(dict(review_token=token+"bad")),"review expired or changed")
        for _ in range(2):self.assertEqual(self.request(dict(review_token=token)).status_code,302)
        with workspace_context(self.workspace.pk):self.assertEqual(KhataSeriesStatusChange.objects.count(),1)

    def test_foreign_series_and_viewer_are_denied(self):
        other, actor, _ = foundation.fixture(uuid.uuid4().hex[:8])
        series=accounts.create_series(workspace=other,actor=actor,code="KH",name="Other")
        self.series=series
        with self.assertRaises(Http404):self.request(method="get")
        self.series_id=series.pk
        with self.assertRaises(PermissionDenied):
            service.preview(workspace=self.workspace,actor=actor,series_id=series.pk)


@override_settings(STORAGES=opening.STORAGES)
class KhataSeriesServicingTests(CorrectionFixture, TestCase):
    def status_change(self, to):
        p=service.preview(workspace=self.workspace,actor=self.actor,series_id=self.series.pk)
        return service.change_status(workspace=self.workspace,actor=self.actor,series_id=self.series.pk,to_status=to,
            reason="Control new lending",request_key=uuid.uuid4(),review_hash=p["review_hash"])

    def test_pause_blocks_withdrawal_increase_but_allows_reduction_settlement(self):
        self.status_change("PAUSED")
        from apps.tenant_apps.loans.selectors.khata_summary import account_summary
        from apps.tenant_apps.loans.selectors.khata_workflow import workflow_state
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            state = workflow_state(self.account, summary=account_summary(self.account), actor=self.actor)
            self.assertFalse(state["ready"]["withdraw"])
        with self.assertRaisesMessage(ValueError,"inactive"):self.payout("1")
        self.proposal("20000000")
        with self.assertRaisesMessage(ValueError,"active series"):self.approve_change()
        self.revise(limit="60000",repayment="40000")
        self.settle()

    def test_retirement_preserves_interest_collection_and_custody(self):
        with workspace_context(self.workspace.pk):
            before=set(self.account.collateral.values_list("pk",flat=True))
        self.status_change("RETIRED")
        with self.later(1):
            self.pay("1000")
            self.deposit(description="Later cover received")
            self.settle()
        with workspace_context(self.workspace.pk):
            self.assertTrue(before.issubset(set(self.account.collateral.values_list("pk",flat=True))))

    def test_retired_native_recovery_retains_audit_and_terminal_state(self):
        self.status_change("PAUSED");self.status_change("ACTIVE");self.status_change("RETIRED")
        content=recovery.export_archive(workspace=self.workspace,actor=self.actor)
        manifest=recovery._read(content,hashlib.sha256(content).hexdigest())[0]
        self.assertEqual(len(manifest["tables"]["loans.KhataSeriesStatusChange"]),3)
        recovery_tests.KhataRecoveryTests.empty_test_destination(self)
        recovery.restore_archive(workspace=self.workspace,actor=self.actor,content=content,
            expected_sha256=hashlib.sha256(content).hexdigest(),commit=True)
        with workspace_context(self.workspace.pk):
            self.series.refresh_from_db();self.assertEqual(self.series.lending_status,"RETIRED")
            self.assertEqual(self.series.status_changes.count(),3)
        with self.assertRaisesMessage(ValueError,"inactive"):self.payout("1")


class KhataSeriesRLSTests(TestCase):
    setUpTestData=classmethod(foundation.KhataRLSBoundaryTests.setUpTestData.__func__)
    runtime=foundation.KhataRLSBoundaryTests.runtime

    def test_forced_rls_and_append_only_parent_scope_under_restricted_role(self):
        p=service.preview(workspace=self.workspace,actor=self.actor,series_id=self.series.pk)
        service.change_status(workspace=self.workspace,actor=self.actor,series_id=self.series.pk,to_status="PAUSED",
            reason="Paused",request_key=uuid.uuid4(),review_hash=p["review_hash"])
        with self.runtime():
            self.assertFalse(KhataSeriesStatusChange.objects.exists())
            with workspace_context(self.other_workspace.pk):self.assertFalse(KhataSeriesStatusChange.objects.exists())
            with workspace_context(self.workspace.pk):
                self.assertEqual(KhataSeriesStatusChange.objects.count(),1)
                for callback in (lambda: KhataSeriesStatusChange.objects.all().update(reason="Changed"),
                                 lambda: KhataSeries.objects.filter(pk=self.series.pk).update(is_active=True),
                                 lambda: KhataSeriesStatusChange.objects.bulk_create([KhataSeriesStatusChange(
                                     workspace=self.workspace,series=self.other_series,number=1,from_status="ACTIVE",to_status="PAUSED",
                                     reason="Forged",request_key=uuid.uuid4(),request_sha256="a"*64,created_by=self.actor)])):
                    with self.assertRaises(DatabaseError),transaction.atomic():callback()
                preview=service.preview(workspace=self.workspace,actor=self.actor,series_id=self.series.pk)
                service.change_status(workspace=self.workspace,actor=self.actor,series_id=self.series.pk,to_status="ACTIVE",
                    reason="Restricted-role resume",request_key=uuid.uuid4(),review_hash=preview["review_hash"])
                self.assertEqual(KhataSeriesStatusChange.objects.count(),2)


class KhataSeriesRaceTests(SeriesFixture, TransactionTestCase):
    def test_duplicate_concurrent_confirmation_records_one_transition(self):
        args=self.change_args();ready=Barrier(2)
        def change(_):
            try:
                ready.wait(timeout=15);return service.change_status(**args).pk
            finally:connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(change,range(2)))
        self.assertEqual(results[0],results[1])
        with workspace_context(self.workspace.pk):self.assertEqual(KhataSeriesStatusChange.objects.count(),1)
