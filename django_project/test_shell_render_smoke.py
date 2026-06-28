from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.template import engines
from django.test import RequestFactory, SimpleTestCase


def _request(path="/", *, url_name="home", namespace=""):
    request = RequestFactory().get(path)
    request.user = AnonymousUser()
    request.resolver_match = SimpleNamespace(url_name=url_name, namespace=namespace)
    return request


def _render(source, context=None, request=None):
    template = engines["django"].from_string(source)
    return template.render(context or {}, request=request or _request())


class SaaSShellRenderSmokeTests(SimpleTestCase):
    def test_public_shell_renders_content_marker(self):
        html = _render(
            """
            {% extends "base_public.html" %}
            {% block title %}Public Smoke{% endblock %}
            {% block content %}<main id="public-smoke">Public shell</main>{% endblock %}
            """,
            request=_request("/", url_name="home"),
        )

        self.assertIn("Public Smoke", html)
        self.assertIn('id="public-smoke"', html)
        self.assertIn("Rokkad", html)

    def test_auth_shell_renders_content_marker(self):
        html = _render(
            """
            {% extends "base_auth.html" %}
            {% block title %}Auth Smoke{% endblock %}
            {% block content %}<section id="auth-smoke">Auth shell</section>{% endblock %}
            """,
            request=_request("/accounts/login/", url_name="account_login"),
        )

        self.assertIn("Auth Smoke", html)
        self.assertIn('id="auth-smoke"', html)
        self.assertIn("Sign In", html)

    def test_global_shell_renders_management_content_marker(self):
        html = _render(
            """
            {% extends "base_global.html" %}
            {% block title %}Global Smoke{% endblock %}
            {% block mgmt_content %}<section id="global-smoke">Global shell</section>{% endblock %}
            """,
            request=_request("/workspace/", url_name="workspace_selector"),
            context={"workspace": None, "user_workspace": None},
        )

        self.assertIn("Global Smoke", html)
        self.assertIn('id="global-smoke"', html)
        self.assertIn("Account &amp; Workspace Management", html)

    def test_workspace_settings_shell_renders_management_content_marker(self):
        html = _render(
            """
            {% extends "base_workspace_settings.html" %}
            {% block title %}Settings Smoke{% endblock %}
            {% block mgmt_content %}<section id="settings-smoke">Settings shell</section>{% endblock %}
            """,
            request=_request(
                "/orgs/workspace/1/preferences/",
                url_name="workspace_preferences",
            ),
            context={"workspace": None, "user_workspace": None},
        )

        self.assertIn("Settings Smoke", html)
        self.assertIn('id="settings-smoke"', html)
        self.assertIn("Account &amp; Workspace Management", html)

    def test_tenant_shell_renders_workspace_content_marker(self):
        html = _render(
            """
            {% extends "base_tenant.html" %}
            {% block title %}Tenant Smoke{% endblock %}
            {% block workspace_content %}<section id="tenant-smoke">Tenant shell</section>{% endblock %}
            """,
            request=_request("/dea/", url_name="dea_home"),
            context={
                "in_tenant": False,
                "show_sidebar": False,
                "workspace": None,
                "user_workspace": None,
                "user_permissions": set(),
            },
        )

        self.assertIn("Tenant Smoke", html)
        self.assertIn('id="tenant-smoke"', html)
        self.assertIn("sidebarOffcanvas", html)
