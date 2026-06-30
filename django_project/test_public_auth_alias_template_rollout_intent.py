from pathlib import Path

from django.test import SimpleTestCase
from django.urls import NoReverseMatch, reverse


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"
TEMPLATES_ROOT = PROJECT_ROOT / "templates"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class PublicAuthAliasTemplateRolloutIntentTests(SimpleTestCase):
    def test_phase91_plan_exists_and_keeps_runtime_baseline_explicit(self):
        plan_path = DOCS_UI_ROOT / "public_auth_alias_template_rollout_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Public/Auth Alias and Template Rollout Plan",
            "Phase 9.1: Plan And Guard Baseline",
            "Status: complete",
            "Keep runtime behavior unchanged",
            "Phase 9.2: Pricing And Missing Public Templates",
            "Phase 9.3: Short Auth Aliases",
            "Phase 9.4: Public Invitation Accept Alias",
            "Future Phase: `/w/<workspace_slug>/...` Route Map",
            "Commit this public/auth alias-template phase",
        ):
            self.assertIn(expected, content)

    def test_phase91_deferred_routes_remain_absent_before_runtime_rollout(self):
        absent_route_names = (
            "workspace_slug_dashboard",
        )

        for route_name in absent_route_names:
            with self.subTest(route_name=route_name):
                with self.assertRaises(NoReverseMatch):
                    reverse(route_name)

    def test_phase92_pricing_route_and_public_templates_are_live(self):
        self.assertEqual(reverse("pricing"), "/pricing/")

        live_templates = (
            "pages/tenant.html",
            "pages/cancellation_and_refund.html",
            "pages/contact.html",
            "pages/help.html",
            "pages/faq.html",
            "pages/pricing.html",
        )

        for template in live_templates:
            with self.subTest(template=template):
                self.assertTrue((TEMPLATES_ROOT / template).exists())

    def test_phase93_short_auth_aliases_are_live_compatibility_redirects(self):
        self.assertEqual(reverse("login"), "/login/")
        self.assertEqual(reverse("signup"), "/signup/")
        self.assertEqual(reverse("password_reset"), "/password/reset/")

    def test_phase94_public_invitation_accept_alias_is_live(self):
        self.assertEqual(
            reverse("public_invitation_accept", kwargs={"key": "abc123"}),
            "/invitations/accept/abc123/",
        )

    def test_phase91_current_auth_and_invitation_routes_remain_compatibility_surface(self):
        self.assertEqual(reverse("account_login"), "/accounts/login/")
        self.assertEqual(reverse("account_signup"), "/accounts/signup/")
        self.assertEqual(reverse("account_reset_password"), "/accounts/password/reset/")
        self.assertEqual(
            reverse("invitations:accept-invite", kwargs={"key": "abc123"}),
            "/invitations/accept-invite/abc123",
        )
        self.assertEqual(
            reverse("team_accept_invitation", kwargs={"key": "abc123"}),
            "/orgs/team/invitations/accept/abc123/",
        )

    def test_phase92_rollout_plan_records_public_template_completion(self):
        plan = _read("docs/ui/public_auth_alias_template_rollout_plan.md")

        self.assertIn("Phase 9.2: Pricing And Missing Public Templates", plan)
        self.assertIn("Status: complete", plan)
        self.assertIn("Phase 9.3: Short Auth Aliases", plan)

    def test_phase91_public_auth_rollout_is_reflected_in_project_docs(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")

        for content in (status, memory, audit):
            with self.subTest():
                self.assertIn("Phase 9.1", content)
                self.assertIn("public_auth_alias_template_rollout_plan.md", content)
                self.assertIn("Phase 9.2", content)

    def test_phase95_review_closes_public_auth_alias_template_phase(self):
        review_path = DOCS_UI_ROOT / "public_auth_alias_template_rollout_review.md"

        self.assertTrue(review_path.exists())
        content = review_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Public/Auth Alias and Template Rollout Review",
            "Added `/pricing/`",
            "Added short auth redirect aliases",
            "Added `/invitations/accept/<key>`",
            "Existing allauth `/accounts/...` paths remain",
            "Existing django-invitations `/invitations/accept-invite/<key>` remains available",
            "Full `/w/<workspace_slug>/...` route-map rollout",
            "Commit this public/auth alias-template phase",
        ):
            self.assertIn(expected, content)
