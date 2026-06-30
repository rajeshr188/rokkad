from django.conf import settings
from django.template import TemplateDoesNotExist
from django.test import TestCase, override_settings
from django.urls import reverse


TEST_STORAGES = {
    **settings.STORAGES,
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}


@override_settings(STORAGES=TEST_STORAGES)
class Phase7PublicAuthRenderSmokeTests(TestCase):
    def test_public_home_page_renders_phase77_surface(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn("css/public.css", html)
        self.assertIn("public-shell", html)
        self.assertIn("public-hero", html)
        self.assertIn("Run loans, inventory, commodity, and accounting", html)
        self.assertIn("public-product-preview", html)
        self.assertIn("/accounts/signup/", html)
        self.assertNotIn("https://via.placeholder.com", html)
        self.assertNotIn("hero-section", html)
        self.assertNotIn("testimonial-card", html)
        self.assertNotIn("Ã¢", html)

    def test_current_renderable_public_pages_use_public_shell(self):
        route_cases = {
            "/about/": "About page",
            "/privacy-policy/": "Privacy Policy",
            "/terms-and-conditions/": "Terms and Conditions",
        }

        for path, expected_fragment in route_cases.items():
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn("css/public.css", html)
                self.assertIn("public-shell", html)
                self.assertIn(expected_fragment, html)

    def test_missing_public_templates_remain_documented_until_implemented(self):
        missing_route_cases = {
            "/tenant/": "pages/tenant.html",
            "/cancellation-and-refund/": "pages/cancellation_and_refund.html",
            "/help/": "pages/help.html",
            "/faq/": "pages/faq.html",
        }
        public_auth_plan = open(
            "docs/ui/phase7_public_auth_polish_plan.md",
            encoding="utf-8-sig",
        ).read()
        phase8_plan = open(
            "docs/ui/phase8_regression_consolidation_plan.md",
            encoding="utf-8-sig",
        ).read()

        for path, template_name in missing_route_cases.items():
            with self.subTest(path=path):
                self.assertIn(template_name, public_auth_plan)
                self.assertIn("missing public templates", phase8_plan)
                with override_settings(ROOT_URLCONF="django_project.urls"):
                    with self.assertRaises(TemplateDoesNotExist):
                        self.client.get(path)

    @override_settings(
        SOCIALACCOUNT_PROVIDERS={
            "google": {
                "CLIENT_ID": "test-google-client-id",
                "SCOPE": ["profile", "email"],
            }
        }
    )
    def test_auth_pages_render_without_configured_google_social_app(self):
        route_cases = {
            "/accounts/login/": ("Log in", "auth-panel", "auth-card"),
            "/accounts/signup/": ("Create account", "auth-panel", "auth-card"),
            "/accounts/password/reset/": ("Forgot password?", "auth-panel", "auth-card"),
        }

        for path, expected_fragments in route_cases.items():
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn("css/public.css", html)
                self.assertIn("auth-shell", html)
                for fragment in expected_fragments:
                    self.assertIn(fragment, html)
                self.assertNotIn("Continue with Google", html)
                self.assertNotIn("g_id_onload", html)

    def test_current_auth_and_invitation_compatibility_paths_stay_available(self):
        self.assertEqual(reverse("account_login"), "/accounts/login/")
        self.assertEqual(reverse("account_signup"), "/accounts/signup/")
        self.assertEqual(reverse("account_reset_password"), "/accounts/password/reset/")
        self.assertEqual(
            reverse("invitations:accept-invite", kwargs={"key": "abc123"}),
            "/invitations/accept-invite/abc123",
        )

    def test_invalid_current_invitation_accept_path_fails_closed(self):
        response = self.client.get(
            reverse("invitations:accept-invite", kwargs={"key": "abc123"})
        )

        self.assertEqual(response.status_code, 410)
