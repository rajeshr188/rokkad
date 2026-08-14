from django.contrib.staticfiles import finders
from django.test import SimpleTestCase
from django.urls import reverse

from django_project.test_shell_render_smoke import (
    _authenticated_request,
    _render,
    _workspace,
)


class ManagementShellVisualSmokeTests(SimpleTestCase):
    def test_management_stylesheet_is_staticfiles_discoverable(self):
        self.assertIsNotNone(finders.find("css/management.css"))

    def _render_management_shell(self, *, url_name="workspace_selector", namespace=""):
        workspace = _workspace()
        return _render(
            """
            {% extends "base_global.html" %}
            {% block title %}Management Visual Smoke{% endblock %}
            {% block page_header %}
            <div class="d-flex align-items-center justify-content-between mb-3">
                <div>
                    <h1 class="h3 mb-1">Workspace Management</h1>
                    <p class="text-muted mb-0">Visual smoke fixture.</p>
                </div>
                <a class="btn btn-primary" href="#">Primary action</a>
            </div>
            {% endblock %}
            {% block mgmt_content %}
            <section id="management-visual-smoke" class="row g-3">
                <div class="col-12 col-xl-7">
                    <div class="bg-white border rounded-2 p-3">
                        <h2 class="h5">Workspace setup</h2>
                        <p class="text-muted mb-0">Normal management content.</p>
                    </div>
                </div>
                <div class="col-12 col-xl-5">
                    <div class="bg-white border rounded-2 p-3">
                        <h2 class="h5">Account state</h2>
                        <p class="text-muted mb-0">Invitation and billing links should fit.</p>
                    </div>
                </div>
            </section>
            {% endblock %}
            """,
            request=_authenticated_request(
                "/workspace/",
                url_name=url_name,
                namespace=namespace,
            ),
            context={
                "workspace": workspace,
                "user_workspace": workspace,
                "user_role": "Owner",
                "invitation_count": 3,
            },
            use_request_processors=False,
        )

    def test_management_shell_uses_full_width_app_wrapper(self):
        html = self._render_management_shell()

        self.assertIn('href="/static/css/management.css"', html)
        self.assertIn('<main class="container-fluid p-0 mt-0 ', html)
        self.assertIn('<div class="mgmt-accent-bar">', html)
        self.assertIn('<div class="mgmt-shell">', html)
        self.assertNotIn('<main class="container-lg mt-4 ', html)

    def test_desktop_and_mobile_management_nav_share_visual_classes(self):
        html = self._render_management_shell()

        self.assertGreaterEqual(html.count("mgmt-nav-link"), 20)
        self.assertGreaterEqual(html.count("mgmt-section-title"), 6)
        self.assertIn("mgmt-sidebar d-none d-lg-flex", html)
        self.assertIn("offcanvas offcanvas-start mgmt-offcanvas", html)
        self.assertNotIn("nav-link py-2", html)
        self.assertNotIn("style=\"background:#f8f7ff", html)
        self.assertNotIn("style=\"color:#7c3aed", html)

    def test_active_state_is_available_in_desktop_and_mobile_nav(self):
        html = self._render_management_shell(url_name="workspace_selector")

        self.assertGreaterEqual(html.count(f'href="{reverse("app_workspaces")}"'), 2)
        self.assertGreaterEqual(html.count("mgmt-nav-link active"), 2)

    def test_management_visual_smoke_remains_control_plane_safe(self):
        html = self._render_management_shell()

        forbidden_tenant_routes = (
            "girvi:girvi_dashboard",
            "party:party_list",
            "dea_business_events_dashboard",
            "dea_reports_hub",
            "product_product_home",
        )
        for route_name in forbidden_tenant_routes:
            with self.subTest(route_name=route_name):
                self.assertNotIn(route_name, html)

        self.assertIn("My Workspaces", html)
        self.assertIn("New Workspace", html)
        self.assertIn("Team Members", html)
        self.assertIn("My Invitations", html)
