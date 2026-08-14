from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class WorkspaceSlugDeferredTargetsIntentTests(SimpleTestCase):
    def test_phase111_deferred_target_plan_exists(self):
        plan_path = DOCS_UI_ROOT / "workspace_slug_deferred_targets_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Workspace Slug Deferred Targets Plan",
            "Phase 11.1: Target Decision",
            "Status: complete",
            "Do not resurrect removed `sales` or `purchase` runtime apps",
            "Do not redirect workspace security/audit routes to account-level security",
            "Phase 11.2: Safe Redirect Aliases",
            "Phase 11.3: Interim Redirect Aliases",
            "Phase 11.4: New Workspace Settings Screens",
        ):
            self.assertIn(expected, content)

    def test_phase111_tenant_section_targets_are_chosen(self):
        plan = _read("docs/ui/workspace_slug_deferred_targets_plan.md")

        expected_pairs = {
            "/w/<workspace_slug>/operations/": "dea_business_events_dashboard",
            "/w/<workspace_slug>/sales/": "dea_business_events_dashboard",
            "/w/<workspace_slug>/purchase/": "dea_business_events_dashboard",
            "/w/<workspace_slug>/commodity/": "dea_commodity_list",
            "/w/<workspace_slug>/reports/": "dea_reports_hub",
        }

        for route, target in expected_pairs.items():
            with self.subTest(route=route):
                self.assertIn(route, plan)
                self.assertIn(target, plan)

    def test_phase111_workspace_settings_targets_are_chosen(self):
        plan = _read("docs/ui/workspace_slug_deferred_targets_plan.md")

        expected_pairs = {
            "/w/<workspace_slug>/settings/profile/": "workspace_update",
            "/w/<workspace_slug>/settings/roles/": "workspace_settings_team",
            "/w/<workspace_slug>/settings/billing/": "subscriptions:dashboard",
            "/w/<workspace_slug>/settings/modules/": "new workspace modules screen",
            "/w/<workspace_slug>/settings/numbering/": "girvi:girvi_series_list",
            "/w/<workspace_slug>/settings/accounting/": "dea_chart_of_accounts",
            "/w/<workspace_slug>/settings/security/": "new workspace security/audit screen",
        }

        for route, target in expected_pairs.items():
            with self.subTest(route=route):
                self.assertIn(route, plan)
                self.assertIn(target, plan)

    def test_phase111_target_decision_is_reflected_in_project_docs(self):
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")
        audit = _read("docs/ui/saas_information_architecture_audit.md")
        review = _read("docs/ui/workspace_slug_route_map_review.md")

        for content in (status, memory, audit, review):
            with self.subTest():
                self.assertIn("Phase 11.1", content)
                self.assertIn("workspace_slug_deferred_targets_plan.md", content)
                self.assertIn("Phase 11.2", content)

    def test_phase11_final_review_closes_slug_route_map_before_portal(self):
        review_path = DOCS_UI_ROOT / "workspace_slug_phase11_review.md"

        self.assertTrue(review_path.exists())
        content = review_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Workspace Slug Phase 11 Review",
            "Phase 11 completes route availability",
            "full canonical replacements for the legacy tenant app roots",
            "/w/<workspace_slug>/settings/modules/",
            "/w/<workspace_slug>/settings/security/",
            "Contact remains intentionally absent",
            "customer/member portal",
            "/portal/loans/",
            "Company.schema_name",
            "AuditLog",
            "tenant_route_canonicalization_phase13_plan.md",
        ):
            self.assertIn(expected, content)
