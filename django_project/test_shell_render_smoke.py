from types import SimpleNamespace

from django.contrib.auth.models import AnonymousUser
from django.contrib.messages import constants as message_levels
from django.contrib.messages.storage.base import Message
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


class _CountRelation:
    def __init__(self, count):
        self._count = count

    def count(self):
        return self._count


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
    return SimpleNamespace(
        id=id,
        name=name,
        schema_name=schema_name,
        slug=schema_name,
        owner_id=1,
        lifecycle_state="ACTIVE",
        logo=None,
        memberships=_CountRelation(2),
    )


def _membership(workspace):
    return SimpleNamespace(company=workspace)


def _authenticated_request(path="/workspace/", *, url_name="workspace_selector", namespace=""):
    workspace = _workspace()
    request = _request(path, url_name=url_name, namespace=namespace)
    request.user = _AuthenticatedUser(
        workspace=workspace,
        memberships=[_membership(workspace), _membership(_workspace(2, "Beta Bullion", "beta"))],
    )
    if "/settings/" in path:
        request.workspace = workspace
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
    def test_full_page_signin_message_renders_once(self):
        notification = "Successfully signed in as punba."
        for layout in ("base_global.html", "base_auth.html", "base_tenant.html"):
            with self.subTest(layout=layout):
                html = _render(
                    '{% extends "' + layout + '" %}',
                    request=_request(),
                    context={
                        "workspace": None, "user_workspace": None,
                        "messages": [Message(message_levels.SUCCESS, notification)],
                    },
                )
                self.assertEqual(html.count(notification), 1)
                self.assertIn('id="toasts"', html)
                if layout == "base_global.html":
                    self.assertLess(html.index('class="mgmt-content"'), html.index(notification))
                    self.assertNotIn("Account &amp; Workspace Management", html)

    def test_background_toast_fragment_retains_message(self):
        notification = "Profile updated."
        html = _render(
            '{% include "toasts.html" %}',
            request=_request(),
            context={"messages": [Message(message_levels.SUCCESS, notification)]},
        )
        self.assertEqual(html.count(notification), 1)
        self.assertIn('hx-swap-oob="afterbegin"', html)

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
        self.assertNotIn("Account &amp; Workspace Management", html)

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
        from apps.orgs.permissions import get_permissions_for_role
        workspace = _workspace()
        request = _authenticated_request("/w/acme/settings/", url_name="workspace_slug_settings")
        html = _render(
            '{% extends "base_global.html" %}', request=request,
            context={"user_permissions": get_permissions_for_role("Owner"), "user_role": "Owner"},
            use_request_processors=False,
        )
        for name in (
            "workspace_slug_dashboard", "workspace_slug_loan_create", "workspace_slug_loan_list",
            "workspace_slug_parties", "workspace_slug_rates", "workspace_slug_notifications",
            "workspace_slug_settings", "workspace_slug_settings_team", "workspace_slug_settings_numbering",
            "workspace_slug_settings_preferences", "workspace_subscriptions:dashboard",
        ):
            href = reverse(name, kwargs={"workspace_slug": workspace.slug})
            self.assertIn(f'href="{href}"', html)
        self.assertIn(reverse("account_settings"), html)
        self.assertIn(reverse("app_invitations"), html)
        self.assertNotIn("Clear Workspace", html)
        self.assertNotIn("Account &amp; Workspace Management", html)

    def test_switcher_uses_page_workspace_not_saved_preference(self):
        request = _authenticated_request()
        request.workspace = _workspace(2, "Beta Bullion", "beta")
        html = _render(
            '{% include "components/navigation/workspace_switcher.html" with workspace_switcher_variant="navbar" %}',
            request=request, use_request_processors=False,
        )
        label = html.split('id="workspaceDropdown"', 1)[1].split('</button>', 1)[0]
        self.assertIn("Beta Bullion", label)
        self.assertNotIn("Acme Jewellers", label)
        request.workspace = None
        html = _render(
            '{% include "components/navigation/workspace_switcher.html" with workspace_switcher_variant="navbar" %}',
            request=request, use_request_processors=False,
        )
        label = html.split('id="workspaceDropdown"', 1)[1].split('</button>', 1)[0]
        self.assertIn("Workspaces", label)
        self.assertNotIn("Acme Jewellers", label)

    def test_authenticated_management_shell_shows_preferences_for_admin_role(self):
        workspace = _workspace()
        html = _render(
            """
            {% extends "base_global.html" %}
            {% block title %}Management Admin Smoke{% endblock %}
            {% block mgmt_content %}<section id="management-admin-smoke">Management shell</section>{% endblock %}
            """,
            request=_authenticated_request("/workspace/1/settings/", url_name="workspace_settings_home"),
            context={
                "workspace": workspace,
                "user_workspace": workspace,
                "user_role": "Admin",
                "user_permissions": {"workspace_settings"},
                "invitation_count": 0,
            },
            use_request_processors=False,
        )

        preferences_href = reverse(
            "workspace_slug_settings_preferences",
            kwargs={"workspace_slug": workspace.slug},
        )
        self.assertGreaterEqual(html.count(f'href="{preferences_href}"'), 2)
        self.assertIn("Preferences", html)

    def test_workspace_selector_renders_global_workspace_manager_surface(self):
        workspace = _workspace()
        other_workspace = _workspace(2, "Beta Bullion", "beta")
        html = _render(
            """
            {% include "company/workspace_home.html" %}
            """,
            request=_authenticated_request("/app/workspaces/", url_name="app_workspaces"),
            context={
                "workspace": workspace,
                "user_workspace": workspace,
                "user_role": "Owner",
                "workspaces": [
                    SimpleNamespace(
                        company=workspace,
                        role=SimpleNamespace(name="Owner"),
                        created="2026-06-30",
                    ),
                    SimpleNamespace(
                        company=other_workspace,
                        role=SimpleNamespace(name="Admin"),
                        created="2026-06-30",
                    ),
                ],
                "current_workspace": workspace,
                "workspace_count": 2,
                "invitation_count": 0,
                "sent_invitations_count": 1,
                "pending_invitations": [],
                "has_workspaces": True,
            },
            use_request_processors=False,
        )

        self.assertNotIn("Global workspace manager", html)
        self.assertIn("mgmt-workspace-hero", html)
        self.assertIn("mgmt-workspace-card current", html)
        self.assertIn("Acme Jewellers", html)
        self.assertIn("Beta Bullion", html)
        self.assertIn("Switch Workspace", html)
        self.assertIn(reverse("app_workspace_create"), html)
        self.assertIn(reverse("app_invitations"), html)
        self.assertIn(reverse("workspace_select", kwargs={"workspace_id": other_workspace.id}), html)
        self.assertIn(
            reverse(
                "workspace_slug_settings",
                kwargs={"workspace_slug": workspace.slug},
            ),
            html,
        )
        self.assertNotIn("createWorkspaceModal", html)
        self.assertNotIn("Welcome Back!", html)

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
        self.assertNotIn("Account &amp; Workspace Management", html)

    def test_customer_portal_shell_renders_portal_only_navigation(self):
        html = _render(
            """
            {% extends "base_customer_portal.html" %}
            {% block title %}Portal Smoke{% endblock %}
            {% block portal_content %}<section id="portal-smoke">Portal shell</section>{% endblock %}
            """,
            request=_authenticated_request("/portal/", url_name="customer_portal_dashboard"),
            context={
                "portal_party_name": "Asha Customer",
                "portal_workspace_name": "Acme Jewellers",
            },
            use_request_processors=False,
        )

        self.assertIn("Portal Smoke", html)
        self.assertIn('id="portal-smoke"', html)
        self.assertIn("portal-topbar", html)
        self.assertIn("portal-sidebar", html)
        self.assertIn("Asha Customer", html)
        self.assertIn("My loans", html)
        self.assertIn("My statements", html)
        self.assertIn('href="/portal/loans/"', html)
        self.assertIn('href="/portal/statements/"', html)
        self.assertNotIn("data-route-pending", html)
        self.assertNotIn("workspace-sidebar", html)
        self.assertNotIn("Account &amp; Workspace Management", html)

    def test_tenant_shell_renders_workspace_content_marker(self):
        html = _render(
            """
            {% extends "base_tenant.html" %}
            {% block title %}Tenant Smoke{% endblock %}
            {% block workspace_content %}<section id="tenant-smoke">Tenant shell</section>{% endblock %}
            """,
            request=_request("/loans/", url_name="pawn_loan_list"),
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
        request = _authenticated_request(
            f"/w/{workspace.slug}/loans/internal/", url_name="pawn_loan_list"
        )
        request.workspace = workspace
        html = _render(
            """
            {% extends "base_tenant.html" %}
            {% block title %}Tenant Auth Smoke{% endblock %}
            {% block workspace_content %}<section id="tenant-auth-smoke">Tenant shell</section>{% endblock %}
            """,
            request=request,
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
        self.assertNotIn("Switch workspace", html)

    def test_workspace_dashboard_renders_setup_checklist_card(self):
        workspace = _workspace()
        setup_checklist = SimpleNamespace(
            completed_count=1,
            total_count=2,
            completion_percentage=50,
            items=(
                SimpleNamespace(
                    key="business_profile",
                    title="Business profile",
                    description="Confirm workspace identity.",
                    status="complete",
                    action_label="Review profile",
                ),
                SimpleNamespace(
                    key="rates",
                    title="Rates",
                    description="Configure operational rates.",
                    status="incomplete",
                    action_label="Configure rates",
                ),
                SimpleNamespace(
                    key="parties",
                    title="Parties",
                    description="Add customers, suppliers, brokers, or employees.",
                    status="incomplete",
                    action_label="Add parties",
                ),
            ),
        )
        setup_state = SimpleNamespace(
            should_show_dashboard_card=True,
            is_complete=False,
            is_dismissed=False,
        )
        request = _authenticated_request(
            "/orgs/workspace/1/dashboard/", url_name="workspace_dashboard"
        )
        request.workspace = workspace
        html = _render(
            """
            {% include "company/workspace_dashboard.html" %}
            """,
            request=request,
            context={
                "in_tenant": True,
                "show_sidebar": False,
                "workspace": workspace,
                "user_workspace": workspace,
                "user_role": "Owner",
                "user_permissions": set(),
                "role": "Owner",
                "can_view": True,
                "setup_checklist": setup_checklist,
                "setup_state": setup_state,
                "team_count": 1,
                "pending_invitations": 0,
                "total_customers": 0,
                "loan_count": 0,
                "new_customers": [],
                "gold_rate": None,
                "silver_rate": None,
                "has_active_subscription": True,
                "sunken": SimpleNamespace(loan_count=0),
            },
            use_request_processors=False,
        )

        self.assertIn("Workspace setup", html)
        self.assertNotIn("DEA Dashboard", html)
        self.assertNotIn("workspace_slug_accounting", html)
        self.assertIn("1/2", html)
        self.assertIn("50%", html)
        self.assertIn("1/2 complete", html)
        self.assertIn("mgmt-setup-hero", html)
        self.assertIn("Rates", html)
        self.assertIn("Parties", html)
        self.assertIn("Dismiss", html)
        self.assertIn(
            reverse(
                "workspace_slug_settings_setup_state",
                kwargs={"workspace_slug": workspace.slug},
            ),
            html,
        )
        self.assertIn(
            reverse(
                "workspace_slug_rates",
                kwargs={"workspace_slug": workspace.slug},
            ),
            html,
        )
        self.assertIn(reverse("workspace_slug_parties", kwargs={"workspace_slug": workspace.slug}), html)

    def test_workspace_settings_setup_page_renders_checklist(self):
        workspace = _workspace()
        setup_checklist = SimpleNamespace(
            completed_count=1,
            total_count=2,
            completion_percentage=50,
            items=(
                SimpleNamespace(
                    key="business_profile",
                    title="Business profile",
                    description="Confirm workspace identity.",
                    status="complete",
                    action_label="Review profile",
                ),
                SimpleNamespace(
                    key="rates",
                    title="Rates",
                    description="Configure operational rates.",
                    status="incomplete",
                    action_label="Configure rates",
                ),
                SimpleNamespace(
                    key="parties",
                    title="Parties",
                    description="Add customers, suppliers, brokers, or employees.",
                    status="incomplete",
                    action_label="Add parties",
                ),
            ),
        )
        setup_state = SimpleNamespace(
            should_show_dashboard_card=True,
            is_complete=False,
            is_dismissed=False,
        )
        html = _render(
            """
            {% include "company/workspace_setup.html" %}
            """,
            request=_authenticated_request(
                "/workspace/1/settings/setup/",
                url_name="workspace_settings_setup",
            ),
            context={
                "workspace": workspace,
                "user_workspace": workspace,
                "user_role": "Owner",
                "company": workspace,
                "setup_checklist": setup_checklist,
                "setup_state": setup_state,
            },
            use_request_processors=False,
        )

        self.assertIn("Workspace setup", html)
        self.assertIn("1/2 complete", html)
        self.assertIn("Rates", html)
        self.assertIn("Parties", html)
        self.assertIn("Mark setup complete", html)
        self.assertIn("Dismiss dashboard card", html)
        self.assertIn(
            reverse(
                "workspace_slug_settings_setup_state",
                kwargs={"workspace_slug": workspace.slug},
            ),
            html,
        )
        self.assertIn(
            reverse(
                "workspace_slug_rates",
                kwargs={"workspace_slug": workspace.slug},
            ),
            html,
        )
        self.assertIn(reverse("workspace_slug_parties", kwargs={"workspace_slug": workspace.slug}), html)
