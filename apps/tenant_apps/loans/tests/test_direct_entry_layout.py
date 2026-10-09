"""Opt-in presentation, shared financial commands and reversible layout choice."""
from types import SimpleNamespace
from django.test import RequestFactory
from django.urls import reverse

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.web.entry_presentation import entry_presentation
from . import test_origination_review as review_fixtures


class DirectEntryLayoutTests(review_fixtures.OriginationReviewTests):
    @classmethod
    def get_test_schema_name(cls):
        return "direct-entry-layout-trial"

    def setUp(self):
        super().setUp()
        self.path = reverse("workspace_loans:pawn_loan_create", args=[self.tenant.slug])
        self.client.get(self.path + "?entry=direct&layout=simplified")

    def capture(self, name, response):
        import os
        from pathlib import Path
        if directory := os.environ.get("DIRECT_LAYOUT_QA_CAPTURE"):
            folder = Path(directory)
            folder.mkdir(parents=True, exist_ok=True)
            (folder/(name+'.html')).write_bytes(response.content)

    def test_fresh_browser_keeps_current_and_choice_does_not_change_other_browser(self):
        fresh = self.make_workspace_client()
        fresh.force_login(self.owner)
        current = fresh.get(self.path + "?entry=direct")
        self.capture("current", current)
        self.assertEqual(current.context["direct_layout"], "current")
        self.assertNotContains(current, "data-direct-item-fields")
        self.assertContains(current, "Override monthly interest")
        simplified = self.client.get(self.path + "?entry=direct")
        self.assertEqual(simplified.context["direct_layout"], "simplified")
        self.assertContains(simplified, "data-direct-item-fields")
        self.capture("simplified", simplified)
        self.assertEqual(fresh.get(self.path + "?entry=direct").context["direct_layout"], "current")

    def test_layout_switch_keeps_purpose_values_token_and_counters_without_saving(self):
        data = self._payload(self.license, self.series)
        data.update(entry_mode="direct", entry_selection="auto", action="layout_change", direct_layout="current")
        counts = (m.PawnLoan.objects.count(), m.PawnLoanEvent.objects.count())
        result = self.client.post(self.path, data)
        self.assertEqual(result.context["entry_purpose"], "direct")
        self.assertEqual(result.context["entry_selection"], "auto")
        self.assertEqual(result.context["direct_layout"], "current")
        self.assertEqual(result.context["submission_token"], data["submission_token"])
        self.assertEqual(result.context["formset"][0]["allocated_principal"].value(), "10000.00")
        self.assertEqual(result.context["form"]["tenure_months"].value(), "3")
        self.assertEqual(counts, (m.PawnLoan.objects.count(), m.PawnLoanEvent.objects.count()))
        self.assertEqual(self.series.number_sequences.get(document_kind="PAWN_LOAN").next_number, 1)
        self.assertEqual(self.client.get(self.path + "?entry=direct").context["direct_layout"], "current")
        data.pop("collateral-0-photograph")
        data["direct_layout"] = "simplified"
        result = self.client.post(self.path, data)
        self.capture("switch", result)
        self.assertContains(result, "data-direct-item-fields")
        self.assertEqual(counts, (m.PawnLoan.objects.count(), m.PawnLoanEvent.objects.count()))

    def test_layout_session_is_scoped_to_workspace_and_user_and_rejects_unknown_choice(self):
        session = {}
        def request(workspace_id, user_id, choice=None):
            data = dict(action="layout_change", entry_mode="direct", entry_selection="auto")
            if choice is not None:
                data["direct_layout"] = choice
            req = RequestFactory().post("/unused", data)
            req.session = session
            req.loans_workspace = SimpleNamespace(pk=workspace_id)
            req.user = SimpleNamespace(pk=user_id)
            return entry_presentation(req)[1]["direct_layout"]
        self.assertEqual(request(10, 20, "simplified"), "simplified")
        self.assertEqual(request(11, 20), "current")
        self.assertEqual(request(10, 21), "current")
        self.assertEqual(request(10, 20), "simplified")
        self.assertEqual(request(10, 20, "unsafe"), "current")

    def test_policy_controls_appraisal_and_missing_tenure_is_disclosed(self):
        for method, name in (("CALCULATED_METAL_VALUE", "calculated"),
                             ("LATEST_APPRAISAL", "appraisal"),
                             ("LOWER_OF_CALCULATED_AND_APPRAISAL", "lower")):
            m.PawnLoanEconomicPolicy.objects.filter(workspace=self.tenant).update(valuation_method=method)
            response = self.client.get(self.path + "?entry=direct")
            self.capture(name, response)
            self.assertEqual(response.context["direct_valuation_method"], method)
            self.assertContains(response, 'data-policy-required="false"' if name == "calculated" else 'data-policy-required="true"')
            self.assertContains(response, "No standing tenure has been resolved")
        m.PawnLoanEconomicPolicy.objects.filter(workspace=self.tenant).update(default_tenure_months=12)
        page = self.client.get(self.path + "?entry=direct")
        self.assertEqual(page.context["form"]["tenure_months"].value(), 12)
        self.assertFalse(page.context["direct_tenure_open"])
        self.assertContains(page, "Standing setup: 12 months")
        self.assertContains(page, 'id="expected-loan-number"', count=1)
        self.assertContains(page, 'id="id_tenure_months"', count=1)

    def test_hidden_exceptions_still_require_reason_and_ltv_still_blocks(self):
        data = self._payload(self.license, self.series)
        data.update(action="preview", entry_mode="direct", direct_layout="simplified",
                    **{"collateral-0-interest_rate_override": "3"})
        invalid = self.client.post(self.path, data)
        self.assertContains(invalid, "Explain why this item needs a different interest rate")
        self.assertContains(invalid, "data-direct-rate-exception open")
        self.assertEqual(m.PawnLoan.objects.count(), 0)
        data.pop("collateral-0-interest_rate_override")
        data.pop("collateral-0-photograph")
        data["collateral-0-allocated_principal"] = "50000"
        invalid = self.client.post(self.path, data)
        self.assertIsNone(invalid.context["economics_preview"])
        self.assertTrue(invalid.context["form"].errors or invalid.context["formset"].total_error_count())
        self.assertEqual(m.PawnLoan.objects.count(), 0)

    def test_paper_form_does_not_expose_direct_layout_controls(self):
        page = self.client.get(self.path + "?entry=paper")
        self.assertNotContains(page, 'id="direct-layout"')
        self.assertNotContains(page, "data-direct-item-fields")

    def test_simplified_staff_layout_does_not_grant_override_or_payout_authority(self):
        from django.contrib.auth import get_user_model
        from apps.orgs.models import Membership, Role
        staff = get_user_model().objects.create_user(username="layout-trial-staff")
        role, _ = Role.objects.get_or_create(name="Member")
        Membership.objects.create(user=staff, company=self.tenant, role=role)
        self.client.force_login(staff)
        page = self.client.get(self.path + "?entry=direct&layout=simplified")
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "data-direct-item-fields")
        self.assertNotContains(page, 'value="review"')
        self.assertNotContains(page, "Use a different item interest rate")
        self.assertTrue(page.context["formset"][0].fields["interest_rate_override"].disabled)
        self.assertEqual(self.client.get(reverse("workspace_loans:pawn_loan_review_disburse",
            args=[self.tenant.slug, 1])).status_code, 403)
