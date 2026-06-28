from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.conf import settings
from django.template import Context
from django.template import engines
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse


def _request(path="/", *, url_name="home", namespace=""):
    request = RequestFactory().get(path)
    request.user = AnonymousUser()
    request.resolver_match = SimpleNamespace(url_name=url_name, namespace=namespace)
    return request


class _Memberships:
    def __init__(self, memberships):
        self._memberships = memberships

    def all(self):
        return self._memberships


class _AuthenticatedUser:
    is_authenticated = True
    username = "owner"
    first_name = "Owner"

    def __init__(self, workspace=None, memberships=None):
        self.profile = SimpleNamespace(id=1, workspace=workspace)
        self.memberships = _Memberships(memberships or [])

    def get_full_name(self):
        return self.first_name


def _workspace(id=1, name="Acme Jewellers", schema_name="acme"):
    return SimpleNamespace(id=id, name=name, schema_name=schema_name, owner_id=1)


def _membership(workspace):
    return SimpleNamespace(company=workspace)


def _authenticated_request(path="/workspace/", *, url_name="workspace_selector", namespace=""):
    workspace = _workspace()
    request = _request(path, url_name=url_name, namespace=namespace)
    request.user = _AuthenticatedUser(
        workspace=workspace,
        memberships=[_membership(workspace), _membership(_workspace(2, "Beta Bullion", "beta"))],
    )
    return request


def _render(source, context=None, request=None, *, use_request_processors=True):
    request = request or _request()
    context = context or {}
    storages = {
        **settings.STORAGES,
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }
    with override_settings(STORAGES=storages):
        if use_request_processors:
            template = engines["django"].from_string(source)
            return template.render(context, request=request)

        template = engines["django"].engine.from_string(source)
        context = {"request": request, "user": request.user, **context}
        return template.render(Context(context))


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

    def test_authenticated_global_shell_renders_workspace_switcher(self):
        html = _render(
            """
            {% extends "base_global.html" %}
            {% block title %}Global Auth Smoke{% endblock %}
            {% block mgmt_content %}<section id="global-auth-smoke">Global shell</section>{% endblock %}
            """,
            request=_authenticated_request("/workspace/", url_name="workspace_selector"),
            context={"workspace": None, "user_workspace": None},
            use_request_processors=False,
        )

        self.assertIn("workspace-switcher-navbar", html)
        self.assertIn("Acme Jewellers", html)
        self.assertIn("All Workspaces", html)

    def test_authenticated_management_shell_renders_expected_nav_routes(self):
        workspace = _workspace()
        html = _render(
            """
            {% extends "base_global.html" %}
            {% block title %}Management Navigation Smoke{% endblock %}
            {% block mgmt_content %}<section id="management-nav-smoke">Management shell</section>{% endblock %}
            """,
            request=_authenticated_request("/workspace/", url_name="workspace_selector"),
            context={
                "workspace": workspace,
                "user_workspace": workspace,
                "user_role": "Owner",
                "invitation_count": 2,
            },
            use_request_processors=False,
        )

        expected_hrefs = [
            reverse("workspace_selector"),
            reverse("workspace_create"),
            reverse("workspace_detail", kwargs={"workspace_id": workspace.id}),
            reverse("workspace_preferences", kwargs={"workspace_id": workspace.id}),
            reverse("team_members_list"),
            reverse("team_invite", kwargs={"workspace_id": workspace.id}),
            reverse("team_invitations_list"),
            reverse("team_invitations"),
            reverse("account_settings"),
            reverse("profile"),
        ]

        for href in expected_hrefs:
            self.assertIn(f'href="{href}"', html)

        billing_href = (
            f'{reverse("workspace_select", kwargs={"workspace_id": workspace.id})}'
            f'?next={reverse("subscriptions:dashboard")}'
        )
        self.assertIn(f'href="{billing_href}"', html)

        for label in (
            "My Workspaces",
            "New Workspace",
            "Settings",
            "Preferences",
            "Team Members",
            "Invite Member",
            "Sent Invitations",
            "My Invitations",
            "Billing",
            "Account Settings",
            "Profile",
        ):
            self.assertIn(label, html)

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

    def test_authenticated_tenant_shell_renders_workspace_switcher(self):
        workspace = _workspace()
        html = _render(
            """
            {% extends "base_tenant.html" %}
            {% block title %}Tenant Auth Smoke{% endblock %}
            {% block workspace_content %}<section id="tenant-auth-smoke">Tenant shell</section>{% endblock %}
            """,
            request=_authenticated_request("/dea/", url_name="dea_home"),
            context={
                "in_tenant": True,
                "show_sidebar": False,
                "workspace": workspace,
                "user_workspace": workspace,
                "user_role": "Owner",
                "user_permissions": set(),
            },
            use_request_processors=False,
        )

        self.assertIn("workspace-switcher-navbar", html)
        self.assertIn("Acme Jewellers", html)
        self.assertIn("Switch workspace", html)
