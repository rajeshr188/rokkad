from django.conf import settings
from django.test import TestCase, override_settings


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
