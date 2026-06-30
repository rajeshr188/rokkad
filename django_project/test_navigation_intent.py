from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = PROJECT_ROOT / "templates"
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read_template(relative_path):
    return (TEMPLATES_ROOT / relative_path).read_text(encoding="utf-8-sig")


class SaaSNavigationIntentTests(SimpleTestCase):
    def test_phase3_navigation_plan_exists(self):
        plan = DOCS_UI_ROOT / "navigation_workspace_switcher_plan.md"

        self.assertTrue(plan.exists())
        content = plan.read_text(encoding="utf-8-sig")
        self.assertIn("Workspace Switcher Contract", content)
        self.assertIn("Sidebar Contract", content)
        self.assertIn("Phase 3.2", content)

    def test_management_shell_visual_polish_checklist_exists(self):
        checklist = DOCS_UI_ROOT / "management_shell_visual_polish_checklist.md"

        self.assertTrue(checklist.exists())
        content = checklist.read_text(encoding="utf-8-sig")
        self.assertIn("Compatibility Constraints", content)
        self.assertIn("Visual Checklist", content)
        self.assertIn("Acceptance Criteria", content)
        self.assertIn("Phase 3.10", content)

    def test_phase3_final_review_exists(self):
        review = DOCS_UI_ROOT / "phase3_navigation_management_shell_review.md"

        self.assertTrue(review.exists())
        content = review.read_text(encoding="utf-8-sig")
        self.assertIn("Compatibility Review", content)
        self.assertIn("Verification Commands", content)
        self.assertIn("Commit Preparation Notes", content)
        self.assertIn("Phase 4 invitation/team flow cleanup", content)

    def test_workspace_switcher_partial_stays_control_plane_safe(self):
        content = _read_template("components/navigation/workspace_switcher.html")

        self.assertIn("workspace_select", content)
        self.assertIn("workspace_selector", content)
        self.assertIn("workspace_create", content)

        tenant_only_route_names = {
            "girvi:girvi_dashboard",
            "party:party_list",
            "product_product_home",
            "dea_business_events_dashboard",
            "dea_reports_hub",
            "rate_list",
            "data_import:import_data",
        }
        violations = [
            route_name for route_name in tenant_only_route_names if route_name in content
        ]
        self.assertEqual(violations, [])

    def test_main_nav_uses_reusable_workspace_switcher_partial(self):
        content = _read_template("components/navigation/main_nav.html")

        self.assertIn(
            "{% include 'components/navigation/workspace_switcher.html' with workspace_switcher_variant=\"navbar\" %}",
            content,
        )
        self.assertNotIn("{% for membership in request.user.memberships.all %}", content)

    def test_tenant_sidebar_remains_live_source_of_truth(self):
        workspace_layout = _read_template("layouts/workspace.html")
        sidebar = _read_template("components/navigation/sidebar.html")
        navigation_config = (PROJECT_ROOT / "django_project" / "navigation.py").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "{% include 'components/navigation/sidebar.html' %}",
            workspace_layout,
        )
        self.assertIn("Current status:", navigation_config)
        self.assertIn("Not used for live sidebar rendering", navigation_config)
        self.assertIn("dea_business_events_dashboard", sidebar)
        self.assertIn("workspace_slug_dashboard", sidebar)
        self.assertIn("workspace_slug_parties", sidebar)
        self.assertIn("workspace_slug_loans", sidebar)
        self.assertIn("workspace_slug_inventory", sidebar)

    def test_management_and_tenant_shells_have_separate_navigation_surfaces(self):
        management_layout = _read_template("layouts/management.html")
        workspace_layout = _read_template("layouts/workspace.html")

        self.assertIn("mgmt-sidebar", management_layout)
        self.assertIn("workspace_settings_sidebar.html", management_layout)
        self.assertIn("workspaceSidebar", workspace_layout)
        self.assertIn("sidebarOffcanvas", workspace_layout)
        self.assertNotIn("mgmt-sidebar", workspace_layout)
