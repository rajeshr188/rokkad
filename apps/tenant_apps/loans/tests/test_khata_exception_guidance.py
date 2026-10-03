"""Source-scoped correction guidance is read-only and does not bypass commands."""
import uuid

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.services import khata_corrections as corrections
from apps.tenant_apps.loans.web import khata_views, khata_workflows
from .test_khata_corrections import CorrectionFixture
from .test_khata_foundation import fixture
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataExceptionGuidanceTests(CorrectionFixture, TestCase):
    def request(self, data=None, *, method="get", actor=None):
        request = getattr(RequestFactory(), method)("/", data or {})
        request.user = actor or self.actor
        request.workspace = self.workspace
        return request

    def history(self, operation, actor=None):
        with workspace_context(self.workspace.pk):
            return khata_views.detail(self.request({"history-operation": operation.pk}, actor=actor), self.account.pk)

    def test_supported_source_guidance_prefills_admin_review_but_viewer_cannot_post(self):
        with self.later(1):
            receipt = self.pay("25000")
            before = self.balance()
            response = self.history(receipt)
            self.assertContains(response, "supports correction review")
            self.assertContains(response, f'/actions/correct/?source={receipt.pk}')
            with workspace_context(self.workspace.pk):
                response = khata_workflows.operate(self.request(dict(source=receipt.pk)), self.account.pk, "correct")
                self.assertContains(response, f'<option value="{receipt.pk}" selected>')
                viewer = self.staff()
            self.assertNotContains(self.history(receipt, viewer), ">Review correction</a>")
            with workspace_context(self.workspace.pk), self.assertRaises(PermissionDenied):
                khata_workflows.operate(self.request(dict(source=receipt.pk), actor=viewer), self.account.pk, "correct")
            self.assertEqual(self.balance(), before)

    def test_blocked_preview_and_history_link_exact_later_sources_without_correction(self):
        with self.later(1):
            receipt = self.pay("25000")
            later = self.deposit(description="Later custody evidence")
            before = self.balance()
            with self.assertRaises(corrections.KhataCorrectionBlocked) as caught:
                corrections.preview_correction(**self.args(), source_id=receipt.pk)
            self.assertEqual(caught.exception.operation_ids, (later.received_operation_id,))
            response = self.history(receipt)
            self.assertContains(response, f'history-operation={later.received_operation_id}#operation-{later.received_operation_id}')
            self.assertNotContains(response, ">Review correction</a>")
            with workspace_context(self.workspace.pk):
                count = self.account.operations.count()
                response = khata_workflows.operate(self.request(dict(request_key=uuid.uuid4(), source=receipt.pk,
                    cash_resolution="NOT_RECEIVED", reason="Wrong receipt", resolution_reference="Reviewed actual cash"),
                    method="post"), self.account.pk, "correct")
                self.assertContains(response, 'id="correction-blockers"')
                self.assertContains(response, f'history-operation={later.received_operation_id}#operation-{later.received_operation_id}')
                self.assertEqual(self.account.operations.count(), count)
            self.assertEqual(self.balance(), before)

    def test_unsupported_and_corrected_sources_and_settled_accounts_explain_support_boundary(self):
        with workspace_context(self.workspace.pk):
            payout = self.account.operations.get(kind="WITHDRAW")
        self.assertContains(self.history(payout), "no supported correction workflow")
        with self.later(1):
            receipt = self.pay("25000")
            self.correct(receipt)
            self.assertContains(self.history(receipt), "already been corrected")
            receipt = self.pay("25000")
            self.settle()
            response = self.history(receipt)
            self.assertContains(response, "Corrections currently require an active account")
            self.assertNotContains(response, ">Review correction</a>")

    def test_guidance_is_workspace_scoped_and_blocker_display_is_bounded(self):
        with self.later(1):
            receipt = self.pay("25000")
            for n in range(12):
                self.deposit(description=f"Later custody {n}")
            with workspace_context(self.workspace.pk):
                self.account.refresh_from_db()
                info = corrections.correction_guidance(self.account, receipt)
                self.assertEqual(info["blocker_count"], 12)
                self.assertEqual(len(info["blockers"]), 10)
            foreign, _, _ = fixture(uuid.uuid4().hex[:8])
            with workspace_context(foreign.pk), self.assertRaisesMessage(ValueError, "matching Workspace"):
                corrections.correction_guidance(self.account, receipt)
