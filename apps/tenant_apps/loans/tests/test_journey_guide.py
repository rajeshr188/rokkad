from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.tenant_apps.loans.web.journey import guide


class JourneyGuideAccessTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/w/example/loans/guide/")
        self.request.user = SimpleNamespace(is_authenticated=True)

    def test_anonymous_requires_login(self):
        self.request.user = AnonymousUser()
        self.assertEqual(guide(self.request).status_code, 302)

    @patch("apps.tenant_apps.loans.access.resolve_workspace_access")
    @patch("apps.tenant_apps.loans.access.resolve_request_workspace")
    def test_read_only_member_can_read_but_cannot_post(self, resolve_workspace, resolve_access):
        resolve_workspace.return_value = SimpleNamespace(pk=1)
        resolve_access.return_value = SimpleNamespace(membership=object(), platform_override=False,
                                                      can=lambda action: action == "data.view")
        with patch("apps.tenant_apps.loans.web.journey.render", return_value=HttpResponse("guide")):
            self.assertEqual(guide(self.request).status_code, 200)
            self.request.method = "POST"
            self.assertEqual(guide(self.request).status_code, 405)

    @patch("apps.tenant_apps.loans.access.resolve_workspace_access")
    @patch("apps.tenant_apps.loans.access.resolve_request_workspace")
    def test_no_workspace_membership_or_read_permission_denied(self, resolve_workspace, resolve_access):
        resolve_workspace.return_value = SimpleNamespace(pk=1)
        for member, allowed in ((None, True), (object(), False)):
            with self.subTest(member=bool(member), allowed=allowed):
                resolve_access.return_value = SimpleNamespace(membership=member, platform_override=False,
                                                              can=lambda action: allowed)
                with self.assertRaises(PermissionDenied):
                    guide(self.request)
        resolve_workspace.return_value = None
        with self.assertRaises(PermissionDenied):
            guide(self.request)


class DraftSplitDiscoveryTests(SimpleTestCase):
    def render(self, state, count, permission=True):
        return render_to_string("loans/pawn/_draft_split_discovery.html", {
            "loan": SimpleNamespace(pk=7, state=state, collateral_items=SimpleNamespace(count=count)),
            "can_split_draft": permission,
            "request": SimpleNamespace(workspace=SimpleNamespace(slug="example")),
        })

    def test_eligible_draft_exposes_working_split_link(self):
        body = self.render("DRAFT", 2)
        self.assertIn(reverse("workspace_loans:pawn_loan_split", args=["example", 7]), body)
        self.assertIn("Split into another draft", body)

    def test_single_row_explains_quantity_does_not_enable_split(self):
        body = self.render("DRAFT", 1)
        self.assertIn("Quantity within a single row", body)
        self.assertNotIn("/split/", body)
        self.assertIn("Correct draft", body)

    def test_finalized_or_unauthorized_records_never_offer_split(self):
        for state in ("APPROVED", "ACTIVE", "CLOSED", "CANCELLED"):
            with self.subTest(state=state):
                self.assertNotIn("data-draft-split-discovery", self.render(state, 2))
        self.assertNotIn("data-draft-split-discovery", self.render("DRAFT", 2, False))
