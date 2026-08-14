from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

from django_project.shared_urlpatterns import (
    AUTH_URLPATTERNS,
    PUBLIC_PLATFORM_URLPATTERNS,
)
from pages import urls as pages_urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"
TEMPLATES_ROOT = PROJECT_ROOT / "templates"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


def _extends_line(relative_path):
    for line in _read(relative_path).splitlines():
        stripped = line.strip()
        if stripped.startswith("{% extends "):
            return stripped
    return ""


def _route_names(patterns):
    return {pattern.name for pattern in patterns if getattr(pattern, "name", None)}


def _route_prefixes(patterns):
    return [str(pattern.pattern) for pattern in patterns]


class Phase7PublicAuthIntentTests(SimpleTestCase):
    def test_phase76_plan_exists_and_records_current_scope(self):
        plan_path = DOCS_UI_ROOT / "phase7_public_auth_polish_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Phase 7.6 Public/Auth Polish Plan",
            "inventory and guard-test slice",
            "No route changes",
            "Current Route Inventory",
            "Current Template Inventory",
            "Gaps To Keep Visible",
            "The target `/pricing/` route",
            "The target short auth aliases `/login/`, `/signup/`, and `/password/reset/`",
            "Phase 7.6 does not implement missing routes or missing templates",
            "Proceed with Phase 7.9",
        ):
            self.assertIn(expected, content)

    def test_public_and_auth_urlpattern_groups_stay_intent_named(self):
        self.assertEqual(_route_prefixes(PUBLIC_PLATFORM_URLPATTERNS), [""])
        self.assertEqual(
            _route_prefixes(AUTH_URLPATTERNS),
            [
                "login/",
                "signup/",
                "password/reset/",
                "invitations/accept/<str:key>/",
                "accounts/",
                "accounts/",
                "invitations/",
            ],
        )

    def test_current_public_route_inventory_matches_pages_urlconf(self):
        route_names = _route_names(pages_urls.urlpatterns)

        for expected in (
            "home",
            "pricing",
            "about",
            "tenant",
            "privacy_policy",
            "cancellation_and_refund",
            "terms_and_conditions",
            "contact",
            "help",
            "faq",
            "dashboard",
            "company_dashboard",
            "workspace_home",
            "workspace_invitations",
            "workspace_select",
            "download_template_pack",
        ):
            self.assertIn(expected, route_names)

        self.assertIn("pricing", route_names)

    def test_current_auth_routes_remain_allauth_compatibility_paths(self):
        self.assertEqual(reverse("login"), "/login/")
        self.assertEqual(reverse("signup"), "/signup/")
        self.assertEqual(reverse("password_reset"), "/password/reset/")
        self.assertEqual(reverse("account_login"), "/accounts/login/")
        self.assertEqual(reverse("account_signup"), "/accounts/signup/")
        self.assertEqual(reverse("account_reset_password"), "/accounts/password/reset/")

    def test_public_auth_shell_aliases_load_shared_stylesheet(self):
        public_alias = _read("templates/base_public.html")
        auth_alias = _read("templates/base_auth.html")

        for content, shell_class in (
            (public_alias, "public-shell"),
            (auth_alias, "auth-shell"),
        ):
            with self.subTest(shell_class=shell_class):
                self.assertIn('{% extends "layouts/base.html" %}', content)
                self.assertIn("{% load static %}", content)
                self.assertIn("{% block extra_css %}", content)
                self.assertIn("{% static 'css/public.css' %}", content)
                self.assertIn("container-fluid p-0 mt-0", content)
                self.assertIn(shell_class, content)

    def test_active_public_pages_keep_public_shell(self):
        for template in (
            "templates/pages/home.html",
            "templates/pages/about.html",
            "templates/pages/privacy_policy.html",
            "templates/pages/terms_and_conditions.html",
        ):
            with self.subTest(template=template):
                self.assertIn("base_public.html", _extends_line(template))

    def test_active_auth_forms_keep_auth_shell_and_form_contracts(self):
        auth_templates = (
            "templates/account/login.html",
            "templates/account/logout.html",
            "templates/account/signup.html",
            "templates/account/password_reset.html",
            "templates/account/password_reset_done.html",
            "templates/account/password_reset_from_key.html",
            "templates/account/password_reset_from_key_done.html",
            "templates/account/password_change.html",
            "templates/account/password_set.html",
        )

        for template in auth_templates:
            with self.subTest(template=template):
                self.assertIn("base_auth.html", _extends_line(template))

        login_template = _read("templates/account/login.html")
        signup_template = _read("templates/account/signup.html")
        password_reset_template = _read("templates/account/password_reset.html")

        self.assertIn("{% csrf_token %}", login_template)
        self.assertIn("{% csrf_token %}", signup_template)
        self.assertIn("{% csrf_token %}", password_reset_template)
        self.assertIn("GOOGLE_OAUTH_ENABLED", login_template)
        self.assertIn("GOOGLE_OAUTH_ENABLED", signup_template)
        self.assertIn("provider_login_url 'google'", login_template)
        self.assertIn("provider_login_url 'google'", signup_template)
        self.assertIn("account_reset_password", password_reset_template)
        self.assertIn("auth-panel", login_template)
        self.assertIn("auth-panel", signup_template)
        self.assertIn("auth-panel", password_reset_template)
        self.assertIn("auth-card", login_template)
        self.assertIn("auth-card", signup_template)
        self.assertIn("auth-card", password_reset_template)

    def test_authenticated_account_pages_stay_global_not_public_or_auth(self):
        for template in (
            "templates/account/userprofile_detail.html",
            "templates/account/userprofile_form.html",
            "templates/account/workspace_management.html",
        ):
            with self.subTest(template=template):
                line = _extends_line(template)
                self.assertIn("base_global.html", line)
                self.assertNotIn("base_public.html", line)
                self.assertNotIn("base_auth.html", line)

    def test_phase76_records_historical_missing_public_template_gaps(self):
        phase7_content = _read("docs/ui/phase7_public_auth_polish_plan.md")
        rollout_content = _read("docs/ui/public_auth_alias_template_rollout_plan.md")

        for expected in (
            "pages/tenant.html",
            "pages/cancellation_and_refund.html",
            "pages/contact.html",
            "pages/help.html",
            "pages/faq.html",
        ):
            self.assertIn(expected, phase7_content)
            self.assertIn(expected, rollout_content)
            self.assertTrue((TEMPLATES_ROOT / expected).exists())

        self.assertTrue((TEMPLATES_ROOT / "pages/pricing.html").exists())

    def test_phase77_public_auth_visual_vocabulary_is_static_owned(self):
        css = _read("static/css/public.css")
        home_template = _read("templates/pages/home.html")

        for expected in (
            ".public-hero",
            ".public-product-preview",
            ".public-card-grid",
            ".public-impact-band",
            ".auth-panel",
            ".auth-story",
            ".auth-card",
        ):
            self.assertIn(expected, css)

        for expected in (
            "public-hero",
            "public-product-preview",
            "public-card-grid",
            "public-impact-band",
            "account_signup",
            "account_login",
        ):
            self.assertIn(expected, home_template)

        self.assertNotIn("<style>", home_template)
        self.assertNotIn("https://via.placeholder.com", home_template)
        self.assertNotIn("linear-gradient", home_template)
        self.assertNotIn("â", home_template)

    def test_phase77_public_css_avoids_viewport_scaled_type(self):
        css = _read("static/css/public.css")

        self.assertNotIn("clamp(", css)
        self.assertNotIn("vw", css)
        self.assertNotIn("letter-spacing: -", css)
