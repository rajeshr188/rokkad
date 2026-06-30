from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class Phase8RegressionConsolidationIntentTests(SimpleTestCase):
    def test_phase81_plan_exists_and_defines_regression_first_scope(self):
        plan_path = DOCS_UI_ROOT / "phase8_regression_consolidation_plan.md"

        self.assertTrue(plan_path.exists())
        content = plan_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Phase 8 Regression Consolidation Plan",
            "strengthening tests around the routes, templates, authorization boundaries, and render contracts",
            "should not introduce new canonical URLs",
            "remove legacy URLs",
            "redesign screens",
            "roll out `/w/<workspace_slug>/...`",
            "the project should have enough regression coverage",
            "Commit the Phase 8 set",
        ):
            self.assertIn(expected, content)

    def test_phase81_plan_records_existing_guard_inventory(self):
        content = (DOCS_UI_ROOT / "phase8_regression_consolidation_plan.md").read_text(
            encoding="utf-8-sig"
        )

        guard_files = (
            "django_project/test_route_intent.py",
            "django_project/test_template_layout_intent.py",
            "django_project/test_shell_render_smoke.py",
            "django_project/test_management_shell_visual_smoke.py",
            "django_project/test_invitation_team_flow_intent.py",
            "django_project/test_authorization_surface_intent.py",
            "django_project/test_onboarding_phase6_intent.py",
            "django_project/test_phase7_public_auth_intent.py",
            "django_project/test_phase7_public_auth_render_smoke.py",
            "django_project/test_phase7_ui_polish_intent.py",
        )

        for guard_file in guard_files:
            with self.subTest(guard_file=guard_file):
                self.assertTrue((PROJECT_ROOT / guard_file).exists())
                self.assertIn(guard_file, content)

    def test_phase81_plan_keeps_regression_buckets_and_deferred_aliases_visible(self):
        content = (DOCS_UI_ROOT / "phase8_regression_consolidation_plan.md").read_text(
            encoding="utf-8-sig"
        )

        for expected in (
            "Route Boundary Regression",
            "Template/Shell Regression",
            "Auth/Public Flow Regression",
            "Workspace Flow Regression",
            "Invitation/Team Regression",
            "Authorization Regression",
            "Render/HTMX Regression",
            "`/pricing/`",
            "`/login/`, `/signup/`, `/password/reset/`",
            "`/invitations/accept/<key>`",
            "full `/w/<workspace_slug>/...` route-map rollout",
            "deeper high-fidelity product redesign",
        ):
            self.assertIn(expected, content)

    def test_phase81_plan_is_reflected_in_master_audit_status_and_memory(self):
        audit = _read("docs/ui/saas_information_architecture_audit.md")
        status = _read("docs/STATUS.md")
        memory = _read("docs/AGENT_MEMORY.md")

        for content in (audit, status, memory):
            with self.subTest():
                self.assertIn("Phase 8.1", content)
                self.assertIn("phase8_regression_consolidation_plan.md", content)
                self.assertIn("Phase 8.2", content)

    def test_phase88_review_closes_regression_phase_without_runtime_scope(self):
        review_path = DOCS_UI_ROOT / "phase8_regression_consolidation_review.md"

        self.assertTrue(review_path.exists())
        content = review_path.read_text(encoding="utf-8-sig")

        for expected in (
            "Phase 8 Regression Consolidation Review",
            "intentionally did not add new routes",
            "remove compatibility URLs",
            "redesign screens",
            "roll out the full `/w/<workspace_slug>/...` target map",
            "Deferred Scope",
            "`/pricing/`",
            "`/login/`, `/signup/`, `/password/reset/`",
            "`/invitations/accept/<key>`",
            "Full `/w/<workspace_slug>/...` tenant route-map rollout",
            "Commit the Phase 8 set",
        ):
            self.assertIn(expected, content)
