"""Independent connections competing to record the same real release."""
import uuid
from concurrent.futures import ThreadPoolExecutor
from tempfile import TemporaryDirectory
from threading import Barrier

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TransactionTestCase, override_settings

from apps.orgs.models import Company, Membership, Role
from apps.tenancy.context import workspace_context
from apps.tenancy.testing import start_workspace_trial
from apps.tenant_apps.loans.models import LoanNumberSequence, PawnLoanRelease, PawnReleaseBatch
from apps.tenant_apps.loans.services.paper_closures import preview_paper_closures, complete_paper_closures
from apps.tenant_apps.loans.tests.test_collateral_reappraisal import CollateralReappraisalTests


@override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
class PaperConcurrencyTests(TransactionTestCase):
    def test_identical_simultaneous_submissions_close_once(self):
        self.enterContext(override_settings(MEDIA_ROOT=self.enterContext(TemporaryDirectory())))
        self.actor = get_user_model().objects.create_user(username=uuid.uuid4().hex)
        self.tenant = Company.objects.create(name="Concurrent paper", schema_name=uuid.uuid4().hex, owner=self.actor, creator=self.actor)
        Membership.objects.create(company=self.tenant, user=self.actor, role=Role.objects.get_or_create(name="Owner")[0])
        start_workspace_trial(self.tenant)
        with workspace_context(self.tenant.pk):
            CollateralReappraisalTests.make_loan(self, method="LATEST_APPRAISAL", age_days=2, product_index=2)
            LoanNumberSequence.objects.create(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE", prefix="R", width=5, maximum_number=10000)
            preview = preview_paper_closures(workspace=self.tenant, actor=self.actor, loan_ids=[self.loan.pk], closure_date=self.today)
            command = dict(workspace=self.tenant, actor=self.actor, request_key=uuid.uuid4(), quote_token=preview["token"],
                confirmed=True, rows=[dict(loan_id=self.loan.pk, amount=str(preview["rows"][0]["amount"]),
                    paid_by="Borrower", collector_name=self.loan.borrower.display_name)])
        barrier = Barrier(2)
        def run():
            try:
                with workspace_context(self.tenant.pk):
                    barrier.wait(timeout=15)
                    return complete_paper_closures(**command).pk
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda _: run(), range(2)))
        self.assertEqual(results[0], results[1])
        with workspace_context(self.tenant.pk):
            self.assertEqual(PawnReleaseBatch.objects.count(), 1)
            self.assertEqual(PawnLoanRelease.objects.count(), 1)
            self.assertEqual(LoanNumberSequence.objects.get(series=self.loan.series, document_kind="PAWN_LOAN_RELEASE").next_number, 2)
