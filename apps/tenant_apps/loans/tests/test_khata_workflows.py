import re
import uuid

from django.core import signing
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase, RequestFactory, override_settings
from django.utils import timezone

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataOperation, KhataAccount, KhataInterestPeriod
from apps.tenant_apps.loans.services import khata_accounts as accounts, khata_servicing as servicing
from apps.tenant_apps.loans.web import khata_workflows as views
from .test_khata_corrections import CorrectionFixture
from . import test_khata_foundation as foundation, test_khata_opening as opening_tests


@override_settings(STORAGES=opening_tests.STORAGES)
class KhataWorkflowTests(CorrectionFixture, TestCase):
    def request(self, data=None, actor=None, method="post"):
        req = getattr(RequestFactory(), method)("/", data or {})
        req.user = actor or self.actor
        req.workspace = self.workspace
        return req

    def action(self, name, data=None, actor=None, method="post"):
        with workspace_context(self.workspace.pk):
            return views.operate(self.request(data, actor, method), self.account.pk, name)

    def review(self, name, data=None):
        response = self.action(name, dict(request_key=uuid.uuid4(), **(data or {})))
        self.assertEqual(response.status_code, 200)
        matches = re.findall(r'name="review_token" value="([^"]+)"', response.content.decode())
        self.assertTrue(matches, response.content.decode())
        return matches[0]

    def test_get_and_review_do_not_post_confirmation_is_idempotent(self):
        with workspace_context(self.workspace.pk):
            count = KhataOperation.objects.count()
        self.assertEqual(self.action("withdraw", method="get").status_code, 200)
        token = self.review("withdraw", dict(value="20000", payment_reference="Actual cash payout"))
        with workspace_context(self.workspace.pk):
            self.assertEqual(KhataOperation.objects.count(), count)
        for _ in range(2):
            self.assertEqual(self.action("withdraw", dict(review_token=token)).status_code, 302)
        with workspace_context(self.workspace.pk):
            self.assertEqual(KhataOperation.objects.count(), count + 1)

    def test_review_cannot_be_tampered_or_shared_with_another_actor(self):
        token = self.review("withdraw", dict(value="20000", payment_reference="Cash payout"))
        response = self.action("withdraw", dict(review_token=token + "changed"))
        self.assertContains(response, "review expired or changed")
        cashier = self.staff("loan_disburse")
        response = self.action("withdraw", dict(review_token=token), actor=cashier)
        self.assertContains(response, "review expired or changed")
        response = self.action("settle", dict(review_token=token))
        self.assertContains(response, "review expired or changed")

    def test_stale_review_does_not_pay_out(self):
        token = self.review("withdraw", dict(value="20000", payment_reference="Cash payout"))
        self.deposit(description="New received evidence")
        response = self.action("withdraw", dict(review_token=token))
        self.assertContains(response, "changed after review")
        with workspace_context(self.workspace.pk):
            self.assertEqual(self.account.operations.filter(kind="WITHDRAW").count(), 1)

    def test_edit_review_retains_instructions_without_posting(self):
        token = self.review("withdraw", dict(value="23456.78", payment_reference="Signed payout"))
        response = self.action("withdraw", dict(review_token=token, edit="1"))
        self.assertContains(response, 'value="23456.78"')
        self.assertContains(response, 'value="Signed payout"')
        with workspace_context(self.workspace.pk):
            self.assertEqual(self.account.operations.filter(kind="WITHDRAW").count(), 1)

    def test_review_expires_at_business_day_boundary(self):
        token = self.review("settle", dict(payment_reference="Settlement"))
        with self.later(0, 1):
            self.assertContains(self.action("settle", dict(review_token=token)), "review expired or changed")

    def test_new_draft_and_proposal_use_scoped_borrower_and_fixed_monthly_rate(self):
        data = dict(request_key=uuid.uuid4(), series=self.series.pk, borrower=self.borrower.pk,
            agreed_limit="500000", monthly_rate="1.25", ltv_percent="75", frequency="ANNUAL",
            lender_name="Fictional lender", lender_address="Fictional address")
        with workspace_context(self.workspace.pk):
            response = views.operate(self.request(data))
            token = re.search(r'name="review_token" value="([^"]+)"', response.content.decode())[1]
            self.assertEqual(views.operate(self.request(dict(review_token=token))).status_code, 302)
            new = KhataAccount.objects.exclude(pk=self.account.pk).get()
            self.assertEqual(new.state, "DRAFT")
            self.assertEqual(new.agreement_revisions.get().frequency, "ANNUAL")
            self.assertEqual(str(new.agreement_revisions.get().monthly_rate), "1.250000")
        self.proposal(limit="15000000")
        token = self.review("approve-change", dict(principal_repayment="0", agreement_reference="Borrower signed", outgoing=[]))
        self.assertEqual(self.action("approve-change", dict(review_token=token)).status_code, 302)
        with workspace_context(self.workspace.pk):
            approval = self.account.operations.filter(kind="TERMS_OK").get()
        token = self.review("activate-change", dict(approval=approval.pk, payment_reference=""))
        self.assertEqual(self.action("activate-change", dict(review_token=token)).status_code, 302)

    def test_group_exchange_and_actual_handover_review_retries(self):
        replacement = self.replacement("100")
        token = self.review("exchange", dict(outgoing=[self.first.pk], incoming=[replacement.pk], reason="Equal replacement"))
        self.assertEqual(self.action("exchange", dict(review_token=token)).status_code, 302)
        with workspace_context(self.workspace.pk):
            source = self.account.operations.filter(kind="EXCHANGE").get()
        token = self.review("handover", dict(item=self.first.pk, parent=source.pk, recipient="Borrower", reference="Signed handover"))
        for _ in range(2):
            self.assertEqual(self.action("handover", dict(review_token=token)).status_code, 302)
        with workspace_context(self.workspace.pk):
            self.assertEqual(self.account.operations.filter(kind="HANDOVER").count(), 1)

    def test_settlement_has_full_amount_and_requires_confirmation(self):
        token = self.review("settle", dict(payment_reference="Actual cash receipt"))
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.account.operations.filter(kind="SETTLE").exists())
        self.assertEqual(self.action("settle", dict(review_token=token)).status_code, 302)
        self.assertEqual(self.action("settle", dict(review_token=token)).status_code, 302)
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            self.assertEqual(self.account.state, "SETTLED_RETURN_PENDING")

    def test_cash_and_administration_permissions_cannot_be_forged(self):
        viewer = self.staff()
        with self.assertRaises(PermissionDenied):
            self.action("withdraw", actor=viewer, method="get")
        with self.assertRaises(PermissionDenied):
            self.action("correct", actor=viewer, method="get")
        with workspace_context(self.workspace.pk), self.assertRaises(PermissionDenied):
            views.setup(self.request(actor=viewer, method="get"))

    def test_foreign_account_and_items_are_not_choices(self):
        workspace, actor, borrower = foundation.fixture(uuid.uuid4().hex[:8])
        series = accounts.create_series(workspace=workspace, actor=actor, code="OTHER", name="Other", prefix="OTHER")
        foreign = accounts.create_draft(**foundation.draft_args(workspace, actor, borrower, series))
        with workspace_context(self.workspace.pk), self.assertRaises(Http404):
            views.operate(self.request(method="get"), foreign.pk, "deposit")
        self.assertContains(self.action("handover", dict(request_key=uuid.uuid4(), item=99999999, parent=99999999,
            recipient="Borrower", reference="Signed")), "Select a valid choice")

    def test_finalization_stale_review_is_rejected_and_cash_is_not_created(self):
        with self.later(1):
            token = self.review("finalize")
            self.deposit(description="Intervening collateral")
            self.assertContains(self.action("finalize", dict(review_token=token)), "changed after review")
            token = self.review("finalize")
            self.assertEqual(self.action("finalize", dict(review_token=token)).status_code, 302)
            with workspace_context(self.workspace.pk):
                self.assertEqual(KhataInterestPeriod.objects.count(), 1)
                self.assertFalse(self.account.operations.filter(kind="INTEREST").exists())

    def test_interest_receipt_and_bounded_correction_from_forms(self):
        with self.later(1, 1):
            token = self.review("interest", dict(value="100000", payment_reference="Actual interest receipt"))
            self.assertEqual(self.action("interest", dict(review_token=token)).status_code, 302)
            with workspace_context(self.workspace.pk):
                source = self.account.operations.filter(kind="INTEREST").get()
            token = self.review("correct", dict(source=source.pk, cash_resolution="REFUNDED",
                reason="Incorrect receipt", resolution_reference="Full cash refund signed"))
            for _ in range(2):
                self.assertEqual(self.action("correct", dict(review_token=token)).status_code, 302)
            with workspace_context(self.workspace.pk):
                self.assertEqual(self.account.operations.filter(kind="CORRECT").count(), 1)

    def test_private_photo_integrity_and_workspace_scoping(self):
        photo = self.photo(self.first)
        with workspace_context(self.workspace.pk):
            response = views.photo(self.request(method="get"), self.account.pk, photo.pk)
            self.assertEqual(response["Content-Type"], "image/png")
            self.assertIn("private", response["Cache-Control"])
            with self.assertRaises(Http404):
                views.photo(self.request(method="get"), self.account.pk + 1000, photo.pk)
            photo.file.storage.delete(photo.file.name)
            self.assertEqual(views.photo(self.request(method="get"), self.account.pk, photo.pk).status_code, 409)

    def test_series_and_owner_warning_policy_forms(self):
        with workspace_context(self.workspace.pk):
            response = views.setup(self.request(dict(kind="series", code="FREE", name="Independent khata",
                prefix="FREE", width=5, maximum_number=99999, license="")))
            self.assertEqual(response.status_code, 302)
            response = views.setup(self.request(dict(kind="policy", request_key=uuid.uuid4(),
                exchange="BLOCK", overdue="WARN", reason="Owner approved strict exchanges")))
            self.assertEqual(response.status_code, 302)
            self.assertContains(views.setup(self.request(method="get")), "Independent khata")

    def test_deposit_form_rejects_impossible_weights_before_review(self):
        response = self.action("deposit", dict(request_key=uuid.uuid4(), description="Gold", metal="GOLD",
            quantity=1, gross_weight="1", net_weight="2", purity="99.9", storage_reference="Vault", received_from="Borrower"))
        self.assertContains(response, "Net weight cannot exceed gross weight")
        self.assertNotContains(response, 'name="review_token"')

    def test_opening_deposit_approval_and_first_withdrawal_through_forms(self):
        self.account = accounts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        self.assertEqual(self.action("deposit", dict(request_key=uuid.uuid4(), description="Fictional gold", metal="GOLD", quantity=1,
            gross_weight="100", net_weight="100", purity="100", storage_reference="Vault", received_from="Borrower",
            receipt_confirmed="on")).status_code, 302)
        token = self.review("approve")
        self.assertEqual(self.action("approve", dict(review_token=token)).status_code, 302)
        token = self.review("withdraw", dict(value="20000", payment_reference="First cash payout"))
        self.assertEqual(self.action("withdraw", dict(review_token=token)).status_code, 302)
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            self.assertEqual(self.account.state, "ACTIVE")

    def test_unopened_return_and_cancellation_through_forms(self):
        self.account = accounts.create_draft(**foundation.draft_args(self.workspace, self.actor, self.borrower, self.series))
        item = self.deposit()
        token = self.review("return-unopened", dict(item=item.pk, recipient="Borrower", reason="Draft not taken"))
        self.assertEqual(self.action("return-unopened", dict(review_token=token)).status_code, 302)
        token = self.review("cancel", dict(reason="Draft not taken"))
        self.assertEqual(self.action("cancel", dict(review_token=token)).status_code, 302)
        with workspace_context(self.workspace.pk):
            self.account.refresh_from_db()
            self.assertEqual(self.account.state, "CANCELLED")
