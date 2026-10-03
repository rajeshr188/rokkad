"""Guidance is source-backed and read-only, never a substitute for command guards."""
import re
import uuid
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase, override_settings

from apps.tenancy.context import workspace_context
from apps.tenant_apps.loans.models import KhataOperation
from apps.tenant_apps.loans.selectors.khata_summary import summary_accounts, account_summary
from apps.tenant_apps.loans.selectors.khata_workflow import workflow_state, activation_approvals, opening_illustration
from apps.tenant_apps.loans.services import khata_accounts, khata_servicing
from apps.tenant_apps.loans.web import khata_workflows, khata_views, khata_draft
from apps.tenant_apps.loans.web.khata_forms import ActionForm, TermsForm
from .test_khata_corrections import CorrectionFixture
from .test_khata_foundation import draft_args, fixture
from .test_khata_opening import STORAGES


@override_settings(STORAGES=STORAGES)
class KhataGuidanceTests(CorrectionFixture, TestCase):
    def setUp(self):
        super().setUp()
        self.account.refresh_from_db()

    def request(self, data=None, actor=None, method="get"):
        request = getattr(RequestFactory(), method)("/", data or {})
        request.user, request.workspace = actor or self.actor, self.workspace
        return request

    def state(self, account=None):
        account = summary_accounts(workspace=self.workspace, balances_only=True).get(pk=(account or self.account).pk)
        return workflow_state(account, summary=account_summary(account), actor=self.actor)

    def test_empty_draft_guides_receiving_and_does_not_offer_impossible_opening(self):
        draft = khata_accounts.create_draft(**draft_args(self.workspace, self.actor, self.borrower, self.series))
        with workspace_context(self.workspace.pk):
            state = self.state(draft)
            self.assertEqual(state["suggested"], ["deposit"])
            self.assertFalse(state["ready"]["approve"])
            self.assertFalse(state["ready"]["photo"])
            self.assertTrue(state["ready"]["cancel"])
            self.assertFalse(state["ready"]["handover"])
            response = khata_views.detail(self.request({"section": "actions"}), draft.pk)
            self.assertContains(response, "Opening proposal saved" if not state["pending"] else "Proposal awaiting approval")
            self.assertNotContains(response, f'/khata/{draft.pk}/actions/approve/')

    def test_pending_changes_approval_and_activation_are_distinct_and_used_choice_disappears(self):
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.state()["ready"]["activate-change"])
        self.proposal("15000000")
        with workspace_context(self.workspace.pk):
            self.assertTrue(self.state()["ready"]["approve-change"])
            self.assertEqual(self.state()["current"].agreed_limit, Decimal("10000000"))
        approval = self.approve_change()
        with workspace_context(self.workspace.pk):
            state = self.state()
            self.assertEqual(state["status"], "Approved change awaiting activation")
            self.assertEqual(activation_approvals(self.account, self.actor).get().pk, approval.pk)
            self.assertEqual(state["suggested"], ["activate-change"])
        self.activate(approval)
        with workspace_context(self.workspace.pk):
            self.assertFalse(activation_approvals(self.account, self.actor))
            self.assertEqual(self.state()["status"], "Current agreement active")
            self.assertEqual(self.state()["current"].agreed_limit, Decimal("15000000"))
            self.assertFalse(ActionForm(account=self.account, action="activate-change", actor=self.actor).fields["approval"].queryset)
            self.assertTrue(ActionForm(account=self.account, action="activate-change", actor=self.actor, replaying=True).fields["approval"].queryset.filter(pk=approval.pk).exists())

    def test_intervening_source_new_proposal_and_day_boundary_exclude_stale_approvals(self):
        self.proposal("15000000"); approval = self.approve_change()
        self.deposit(description="New evidence")
        with workspace_context(self.workspace.pk):
            self.assertFalse(activation_approvals(self.account, self.actor))
            self.assertTrue(self.state()["ready"]["approve-change"])
        approval = self.approve_change()
        with self.later(0, 1), workspace_context(self.workspace.pk):
            self.assertFalse(activation_approvals(self.account, self.actor))
            self.assertEqual(self.state()["suggested"], ["proposal"])
        self.proposal("16000000")
        with workspace_context(self.workspace.pk):
            self.assertFalse(activation_approvals(self.account, self.actor))

    def test_strict_choice_reuses_live_evidence_validation(self):
        self.proposal("15000000"); self.approve_change()
        # Inactive lending series invalidates an increase without adding an operation.
        from apps.tenant_apps.loans.services import khata_series
        preview = khata_series.preview(workspace=self.workspace, actor=self.actor, series_id=self.series.pk)
        khata_series.change_status(workspace=self.workspace, actor=self.actor, series_id=self.series.pk,
            to_status="PAUSED", reason="Pause lending", request_key=uuid.uuid4(), review_hash=preview["review_hash"])
        with workspace_context(self.workspace.pk):
            self.assertFalse(activation_approvals(self.account, self.actor))

    def test_finalization_and_receipt_follow_actual_periods_and_due_clearance(self):
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.state()["ready"]["finalize"])
            self.assertFalse(self.state()["ready"]["interest"])
        with self.later(1), workspace_context(self.workspace.pk):
            state = self.state()
            self.assertTrue(state["ready"]["finalize"])
            self.assertTrue(state["ready"]["interest"])
            self.assertEqual(state["next_due"], date(2026, 11, 10))
            self.pay("100000")
            self.assertFalse(self.state()["ready"]["finalize"])
            self.assertFalse(self.state()["ready"]["interest"])
            self.assertEqual(self.state()["next_due"], date(2026, 12, 10))

    def test_return_reservation_and_actual_completion_control_handover(self):
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.state()["ready"]["handover"])
        incoming = self.replacement(); source = self.exchange([self.first], [incoming])
        with workspace_context(self.workspace.pk):
            self.assertTrue(self.state()["ready"]["handover"])
        self.handover(self.first, source)
        with workspace_context(self.workspace.pk):
            self.assertFalse(self.state()["ready"]["handover"])

    def test_cashier_cannot_gain_noncash_activation_from_guidance(self):
        self.proposal("15000000"); self.approve_change()
        cashier = self.staff("loan_repay")
        with workspace_context(self.workspace.pk):
            request = self.request({"section": "actions"}, actor=cashier)
            response = khata_views.detail(request, self.account.pk)
            self.assertNotContains(response, f'/khata/{self.account.pk}/actions/activate-change/')
            self.assertFalse(self.state()["ready"]["finalize"])

    def test_monthly_unit_annual_bill_rounding_short_month_and_zero_illustrations(self):
        args = dict(agreed_limit=Decimal("10000000"), monthly_rate=Decimal("1"), day=date(2026, 10, 10))
        monthly = opening_illustration(**args, frequency="MONTHLY")
        annual = opening_illustration(**args, frequency="ANNUAL")
        self.assertEqual(monthly["first_bill"], Decimal("100000"))
        self.assertEqual(annual["first_bill"], Decimal("1200000"))
        self.assertEqual(annual["monthly_charge"], monthly["monthly_charge"])
        self.assertEqual(annual["due_on"], date(2027, 10, 10))
        self.assertEqual(opening_illustration(agreed_limit=Decimal("1"), monthly_rate=Decimal("0.5"), frequency="MONTHLY", day=date(2026, 1, 31))["monthly_charge"], Decimal("0.01"))
        self.assertEqual(opening_illustration(**(args | {"day": date(2024, 2, 29)}), frequency="ANNUAL")["due_on"], date(2025, 2, 28))
        self.assertEqual(opening_illustration(**(args | {"monthly_rate": Decimal(0)}), frequency="ANNUAL")["first_bill"], 0)

    def test_estimate_is_validated_private_read_only_and_permission_scoped(self):
        data = dict(agreed_limit="10000000", monthly_rate="1", frequency="ANNUAL")
        with workspace_context(self.workspace.pk):
            count = KhataOperation.objects.count()
            response = khata_draft.estimate(self.request(data))
            self.assertContains(response, "12,00,000")
            self.assertContains(response, "not just the withdrawal")
            self.assertIn("no-store", response["Cache-Control"])
            for bad in ({"agreed_limit": "0"}, {"monthly_rate": "NaN"}, {"monthly_rate": "0.0000001"}, {"frequency": "WEEKLY"}):
                self.assertEqual(khata_draft.estimate(self.request(data | bad)).status_code, 400)
            self.assertEqual(KhataOperation.objects.count(), count)
            with self.assertRaises(PermissionDenied):
                khata_draft.estimate(self.request(data, actor=self.staff()))

    def test_native_borrower_choices_are_bounded_active_and_workspace_scoped(self):
        foreign, actor, borrower = fixture(uuid.uuid4().hex[:8])
        with workspace_context(self.workspace.pk):
            native = TermsForm(workspace=self.workspace, borrower_search=self.borrower.party_code)
            self.assertEqual(list(native.fields["borrower"].queryset), [self.borrower])
            self.assertNotIn(borrower, native.fields["borrower"].queryset)
            self.assertLessEqual(native.fields["borrower"].queryset.count(), 25)
            rich = TermsForm(workspace=self.workspace)
            self.assertIn(f"/w/{self.workspace.slug}/", rich.fields["borrower"].widget.data_url)
            response = khata_workflows.operate(self.request(), action="new")
            self.assertContains(response, 'id="borrower-outstanding"')
            self.assertContains(response, 'id="khata-opening-estimate"')
        with self.assertRaisesMessage(ValueError, "matching Workspace"):
            activation_approvals(self.account)

    def test_new_review_includes_illustration_without_creating_account(self):
        data = dict(request_key=uuid.uuid4(), series=self.series.pk, borrower=self.borrower.pk,
            agreed_limit="10000000", monthly_rate="1", ltv_percent="75", frequency="ANNUAL",
            lender_name="Fictional lender", lender_address="Fictional address")
        with workspace_context(self.workspace.pk):
            before = self.account.__class__.objects.count()
            response = khata_workflows.operate(self.request(data, method="post"), action="new")
            self.assertContains(response, "Indicative opening interest")
            self.assertContains(response, "12,00,000")
            self.assertEqual(self.account.__class__.objects.count(), before)
            self.assertTrue(re.search('name="review_token"', response.content.decode()))
