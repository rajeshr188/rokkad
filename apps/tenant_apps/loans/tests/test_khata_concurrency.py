import uuid
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.db import connections
from django.test import TransactionTestCase

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataAccount, KhataAgreementRevision
from apps.tenant_apps.loans.services import khata_accounts as service
from .test_khata_foundation import fixture, draft_args


class KhataNumberConcurrencyTests(TransactionTestCase):
    def setUp(self):
        self.workspace, self.actor, self.borrower = fixture(uuid.uuid4().hex[:8])
        self.series = service.create_series(workspace=self.workspace, actor=self.actor, code="KH", name="Concurrent")

    def race(self, args):
        ready = Barrier(len(args))

        def create(kwargs):
            try:
                ready.wait(timeout=15)
                return service.create_draft(**kwargs).account_number
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=len(args)) as pool:
            return list(pool.map(create, args))

    def test_duplicate_submission_consumes_one_number(self):
        args = draft_args(self.workspace, self.actor, self.borrower, self.series)
        self.assertEqual(self.race([args, args]), ["KH00001", "KH00001"])
        with workspace_context(self.workspace.pk):
            self.series.refresh_from_db()
            self.assertEqual(self.series.next_number, 2)
            self.assertEqual(KhataAccount.objects.count(), 1)
            self.assertEqual(KhataAgreementRevision.objects.count(), 1)

    def test_distinct_submissions_get_distinct_consecutive_numbers(self):
        results = self.race([draft_args(self.workspace, self.actor, self.borrower, self.series) for _ in range(2)])
        self.assertEqual(sorted(results), ["KH00001", "KH00002"])
        with workspace_context(self.workspace.pk):
            self.series.refresh_from_db()
            self.assertEqual(self.series.next_number, 3)
