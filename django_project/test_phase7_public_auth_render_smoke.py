from django.conf import settings
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
            "/pricing/": "Start with the controls small teams need",
            "/about/": "About page",
            "/tenant/": "Each business runs in its own workspace",
            "/privacy-policy/": "Privacy Policy",
            "/cancellation-and-refund/": "Cancellation and refund policy",
            "/terms-and-conditions/": "Terms and Conditions",
            "/help/": "Get oriented before daily operations begin",
            "/faq/": "Frequently asked questions",
        }

        for path, expected_fragment in route_cases.items():
            with self.subTest(path=path):
                with override_settings(ROOT_URLCONF="django_project.urls"):
                    response = self.client.get(path)

                self.assertEqual(response.status_code, 200)
                html = response.content.decode()
                self.assertIn("css/public.css", html)
                self.assertIn("public-shell", html)
                self.assertIn(expected_fragment, html)

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

    def test_phase93_short_auth_aliases_redirect_to_allauth_paths(self):
        route_cases = {
            "/login/?next=/app/": "/accounts/login/?next=/app/",
            "/signup/": "/accounts/signup/",
            "/password/reset/": "/accounts/password/reset/",
        }

        for path, expected_location in route_cases.items():
            with self.subTest(path=path):
                response = self.client.get(path)

                self.assertEqual(response.status_code, 302)
                self.assertEqual(response["Location"], expected_location)

    def test_current_auth_and_invitation_compatibility_paths_stay_available(self):
        self.assertEqual(reverse("login"), "/login/")
        self.assertEqual(reverse("signup"), "/signup/")
        self.assertEqual(reverse("password_reset"), "/password/reset/")
        self.assertEqual(reverse("account_login"), "/accounts/login/")
        self.assertEqual(reverse("account_signup"), "/accounts/signup/")
        self.assertEqual(reverse("account_reset_password"), "/accounts/password/reset/")
        self.assertEqual(
            reverse("public_invitation_accept", kwargs={"key": "abc123"}),
            "/invitations/accept/abc123/",
        )
        self.assertEqual(
            reverse("invitations:accept-invite", kwargs={"key": "abc123"}),
            "/invitations/accept-invite/abc123",
        )

    def test_invalid_current_invitation_accept_path_fails_closed(self):
        route_names = (
            "public_invitation_accept",
            "invitations:accept-invite",
        )

        for route_name in route_names:
            with self.subTest(route_name=route_name):
                response = self.client.get(
                    reverse(route_name, kwargs={"key": "abc123"})
                )

                self.assertEqual(response.status_code, 410)
