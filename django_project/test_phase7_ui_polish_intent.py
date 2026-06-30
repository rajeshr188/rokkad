from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"
TEMPLATES_ROOT = PROJECT_ROOT / "templates"
STATIC_ROOT = PROJECT_ROOT / "static"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class Phase7UIPolishIntentTests(SimpleTestCase):
    def test_phase7_plan_exists_and_defines_safe_first_slice(self):
        plan_path = DOCS_UI_ROOT / "phase7_modern_fintech_ui_polish_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Phase 7 Modern Fintech UI Polish Plan",
            "management/workspace setup surfaces",
            "No route changes in Phase 7.1",
            "No permission or middleware behavior changes in Phase 7.1",
            "Workspace setup remains advisory and non-blocking",
            "Bootstrap/HTMX remains the UI foundation",
            "Phase 7.10 Checkpoint",
            "first-pass UI infrastructure and surface cleanup",
            "management/setup visual vocabulary",
        ):
            self.assertIn(expected, content)

    def test_phase7_plan_keeps_product_area_visual_targets_separate(self):
        content = (DOCS_UI_ROOT / "phase7_modern_fintech_ui_polish_plan.md").read_text(
            encoding="utf-8-sig"
        )

        for expected in (
            "Public pages should feel like a polished SaaS fintech funnel",
            "Authenticated global pages should feel like a workspace manager",
            "Tenant ERP pages should feel dense, stable, and operational",
            "Workspace settings should feel administrative",
            "Public/schema concepts must not leak into tenant ERP screens",
            "Tenant business data must not leak into global/public management screens",
        ):
            self.assertIn(expected, content)

    def test_management_shell_remains_static_stylesheet_owned_before_polish(self):
        management_layout = _read("templates/layouts/management.html")
        management_css = _read("static/css/management.css")

        self.assertIn("{% static 'css/management.css' %}", management_layout)
        self.assertNotIn("<style>", management_layout)
        self.assertIn(".mgmt-accent-bar", management_css)
        self.assertIn(".mgmt-shell", management_css)
        self.assertIn(".mgmt-nav-link", management_css)
        self.assertIn(".mgmt-content", management_css)
        self.assertIn(".mgmt-setup-hero", management_css)
        self.assertIn(".mgmt-setup-grid", management_css)
        self.assertIn(".mgmt-setup-task", management_css)
        self.assertIn(".mgmt-status-badge", management_css)

    def test_workspace_setup_page_stays_in_settings_shell_and_advisory(self):
        setup_template = _read("templates/company/workspace_setup.html")

        self.assertIn("{% extends 'base_workspace_settings.html' %}", setup_template)
        self.assertIn("Workspace setup", setup_template)
        self.assertIn("Track the core setup tasks", setup_template)
        self.assertIn("workspace_settings_setup_state", setup_template)
        self.assertIn("Mark setup complete", setup_template)
        self.assertIn("Dismiss dashboard card", setup_template)
        self.assertIn("Reopen setup", setup_template)
        self.assertNotIn("disabled", setup_template.lower())
        self.assertNotIn("blocked", setup_template.lower())

    def test_workspace_setup_page_uses_phase72_visual_vocabulary(self):
        setup_template = _read("templates/company/workspace_setup.html")
        task_partial = _read("templates/components/setup/setup_checklist_task.html")

        for expected in (
            "mgmt-state-alert",
            "mgmt-setup-hero",
            "mgmt-setup-summary",
            "mgmt-progress-track",
            "mgmt-progress-bar",
            "mgmt-setup-actions",
            "mgmt-setup-grid",
            "components/setup/setup_checklist_task.html",
        ):
            self.assertIn(expected, setup_template)

        for expected in (
            "mgmt-setup-task",
            "mgmt-setup-task-header",
            "mgmt-status-badge done",
            "mgmt-status-badge check",
            "mgmt-status-badge todo",
            "mgmt-setup-task-action",
        ):
            self.assertIn(expected, task_partial)

        self.assertNotIn("card border-0 shadow-sm mb-4", setup_template)
        self.assertNotIn("badge bg-success-subtle", task_partial)
        self.assertNotIn("badge bg-warning-subtle", task_partial)

    def test_workspace_dashboard_setup_card_keeps_canonical_state_targets(self):
        dashboard_template = _read("templates/company/workspace_dashboard.html")

        self.assertIn("{% static 'css/management.css' %}", dashboard_template)
        self.assertIn("setup_state.should_show_dashboard_card", dashboard_template)
        self.assertIn("workspace_settings_setup", dashboard_template)
        self.assertIn("workspace_settings_setup_state", dashboard_template)
        self.assertIn("View setup", dashboard_template)
        self.assertIn("Dismiss", dashboard_template)
        self.assertIn("Complete the core setup tasks", dashboard_template)

    def test_workspace_dashboard_setup_card_uses_phase73_visual_vocabulary(self):
        dashboard_template = _read("templates/company/workspace_dashboard.html")
        task_partial = _read("templates/components/setup/setup_checklist_task.html")

        for expected in (
            "mgmt-setup-hero",
            "mgmt-setup-summary",
            "mgmt-progress-track",
            "mgmt-progress-bar",
            "mgmt-setup-actions",
            "mgmt-setup-grid",
            "components/setup/setup_checklist_task.html",
        ):
            self.assertIn(expected, dashboard_template)

        for expected in (
            "mgmt-setup-task",
            "mgmt-setup-task-header",
            "mgmt-status-badge done",
            "mgmt-status-badge check",
            "mgmt-status-badge todo",
            "mgmt-setup-task-action",
        ):
            self.assertIn(expected, task_partial)

        self.assertNotIn("badge bg-success-subtle", task_partial)
        self.assertNotIn("badge bg-warning-subtle", task_partial)

    def test_phase74_setup_task_markup_is_shared_by_setup_surfaces(self):
        setup_template = _read("templates/company/workspace_setup.html")
        dashboard_template = _read("templates/company/workspace_dashboard.html")
        task_partial = _read("templates/components/setup/setup_checklist_task.html")

        self.assertIn(
            '{% include "components/setup/setup_checklist_task.html" with item=item workspace_id=company.id task_id_prefix="setup-task" heading_level="h2" %}',
            setup_template,
        )
        self.assertIn(
            '{% include "components/setup/setup_checklist_task.html" with item=item workspace_id=workspace.id task_id_prefix="dashboard-setup-task" heading_level="h3" %}',
            dashboard_template,
        )
        self.assertIn('heading_level == "h3"', task_partial)
        self.assertIn("workspace_settings_preferences", task_partial)
        self.assertIn("workspace_settings_invite", task_partial)
        self.assertIn("dea_business_events_dashboard", task_partial)

    def test_phase7_first_slice_does_not_add_new_static_entrypoints(self):
        css_files = {
            path.relative_to(STATIC_ROOT).as_posix()
            for path in (STATIC_ROOT / "css").glob("*.css")
        }

        self.assertIn("css/management.css", css_files)
        self.assertIn("css/workspace.css", css_files)
        self.assertNotIn("css/phase7.css", css_files)
        self.assertNotIn("css/workspace-setup.css", css_files)

    def test_setup_surfaces_do_not_point_back_to_legacy_setup_routes(self):
        setup_template = _read("templates/company/workspace_setup.html")
        dashboard_template = _read("templates/company/workspace_dashboard.html")
        sidebar_template = _read("templates/components/navigation/workspace_settings_sidebar.html")

        for content in (setup_template, dashboard_template, sidebar_template):
            with self.subTest():
                self.assertIn("workspace_settings_setup", content)

        self.assertNotIn("{% url 'workspace_setup'", setup_template)
        self.assertNotIn("{% url 'workspace_setup'", dashboard_template)

    def test_workspace_selector_uses_phase75_workspace_manager_vocabulary(self):
        workspace_home = _read("templates/company/workspace_home.html")
        management_css = _read("static/css/management.css")

        for expected in (
            "mgmt-workspace-hero",
            "mgmt-workspace-summary",
            "mgmt-summary-tile",
            "mgmt-workspace-grid",
            "mgmt-workspace-card",
            "mgmt-workspace-avatar",
            "mgmt-workspace-actions",
            "mgmt-side-card",
            "mgmt-empty-state",
        ):
            self.assertIn(expected, workspace_home)
            self.assertIn(f".{expected}", management_css)

        self.assertIn("app_workspace_create", workspace_home)
        self.assertIn("app_invitations", workspace_home)
        self.assertIn("workspace_select", workspace_home)
        self.assertIn("workspace_settings_home", workspace_home)
        self.assertNotIn("createWorkspaceModal", workspace_home)
        self.assertNotIn("class=\"card h-100 workspace-card", workspace_home)
        self.assertNotIn("Welcome Back!", workspace_home)

    def test_phase79_tenant_shell_and_dashboard_use_density_vocabulary(self):
        tenant_alias = _read("templates/base_tenant.html")
        workspace_layout = _read("templates/layouts/workspace.html")
        sidebar = _read("templates/components/navigation/sidebar.html")
        dashboard = _read("templates/company/workspace_dashboard.html")
        workspace_css = _read("static/css/workspace.css")

        self.assertIn("{% static 'css/workspace.css' %}", tenant_alias)
        self.assertIn("workspace-context-bar", workspace_layout)
        self.assertIn("workspace-sidebar-toggle", workspace_layout)
        self.assertIn("workspace-nav-link", sidebar)
        self.assertIn("workspace-identity", sidebar)
        self.assertIn("tenant-page-header", dashboard)
        self.assertIn("tenant-stat-grid", dashboard)
        self.assertIn("tenant-quick-grid", dashboard)
        self.assertNotIn("<style>", workspace_layout)
        self.assertNotIn("<style>", sidebar)
        self.assertNotIn("<style>", dashboard)
        self.assertNotIn("dashboard-stat-card", dashboard)
        self.assertNotIn('class="quick-action', dashboard)

        for expected in (
            ".workspace-sidebar",
            ".workspace-nav-link",
            ".tenant-page-header",
            ".tenant-stat-card",
            ".tenant-quick-action",
        ):
            self.assertIn(expected, workspace_css)

    def test_phase710_review_records_first_pass_closeout_and_deferred_scope(self):
        review_path = DOCS_UI_ROOT / "phase7_modern_fintech_ui_polish_review.md"
        audit = _read("docs/ui/saas_information_architecture_audit.md")

        self.assertTrue(review_path.exists())
        review = review_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Phase 7 Modern Fintech UI Polish Review",
            "first-pass UI infrastructure and surface cleanup",
            "not be read as the final high-fidelity product design",
            "deeper product-design pass remains deferred",
            "Full high-fidelity fintech visual redesign remains deferred",
            "The full target `/w/<workspace_slug>/...` route map",
            "`/pricing/`, `/login/`, `/signup/`, `/password/reset/`, and `/invitations/accept/<key>`",
            "Browser screenshot review was not completed",
            "Commit the Phase 7 set",
            "start Phase 8 regression consolidation",
        ):
            self.assertIn(expected, review)

        self.assertIn("Phase 7.10 closes the first-pass UI polish track", audit)
        self.assertIn("not the final high-fidelity fintech redesign", audit)
        self.assertIn("start Phase 8 regression consolidation", audit)
