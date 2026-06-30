from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

from apps.onboarding import urls as onboarding_urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


def _route_names(patterns):
    return {pattern.name for pattern in patterns}


def _read(relative_path):
    return (PROJECT_ROOT / relative_path).read_text(encoding="utf-8-sig")


class OnboardingPhase6IntentTests(SimpleTestCase):
    def test_phase6_onboarding_plan_exists(self):
        plan = DOCS_UI_ROOT / "onboarding_phase6_plan.md"

        self.assertTrue(plan.exists())
        content = plan.read_text(encoding="utf-8-sig")
        for expected in (
            "Phase 6 Onboarding Plan",
            "workspace setup checklist",
            "Business profile",
            "Accounting setup",
            "Opening balances",
            "Invite team",
            "Create first transaction",
            "Do not remove existing `/onboarding/...` URLs",
        ):
            self.assertIn(expected, content)

    def test_existing_onboarding_routes_remain_compatibility_entrypoints(self):
        route_names = _route_names(onboarding_urls.urlpatterns)

        self.assertEqual(
            {
                "onboarding_start",
                "onboarding_profile",
                "onboarding_company",
                "onboarding_team",
                "onboarding_tour",
                "onboarding_complete",
                "onboarding_skip",
            },
            route_names,
        )

    def test_workspace_creation_control_plane_boundary_is_documented(self):
        plan = (DOCS_UI_ROOT / "onboarding_phase6_plan.md").read_text(
            encoding="utf-8-sig"
        )
        onboarding_views = _read("apps/onboarding/views.py")
        orgs_views = _read("apps/orgs/views.py")
        control_plane = _read("apps/orgs/services/control_plane.py")

        self.assertIn("Workspace creation previously existed in two places", plan)
        self.assertIn("def onboarding_company", onboarding_views)
        self.assertIn("_provision_company_schema(company)", onboarding_views)
        self.assertIn("_seed_company_schema_defaults(company)", onboarding_views)
        self.assertIn(
            "control_plane.create_onboarding_workspace_from_form",
            onboarding_views,
        )
        self.assertNotIn("Domain.objects.create", onboarding_views)
        self.assertNotIn("Membership.objects.create", onboarding_views)
        self.assertIn("def workspace_create", orgs_views)
        self.assertIn("control_plane.create_workspace_from_form", orgs_views)
        self.assertIn("def create_onboarding_workspace_from_form", control_plane)
        self.assertIn("provision_workspace(company)", control_plane)
        self.assertIn("seed_workspace_defaults(company)", control_plane)

    def test_phase6_plan_points_to_control_plane_services(self):
        plan = (DOCS_UI_ROOT / "onboarding_phase6_plan.md").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "Workspace creation should use the orgs control-plane workspace service",
            plan,
        )
        self.assertIn(
            "Team invitations should use the orgs invitation control-plane service",
            plan,
        )
        self.assertIn("Phase 6.2 Service", plan)
        self.assertIn("Phase 6.3 Dashboard Surface", plan)
        self.assertIn("Phase 6.4 Workspace Settings Setup Page", plan)
        self.assertIn("Phase 6.5 Completion Routing", plan)
        self.assertIn("Phase 6.6 Control-plane Workspace Creation", plan)
        self.assertIn("Phase 6.7 Control-plane Team Invitations", plan)
        self.assertIn("Phase 6.8 Setup Completion and Dismiss State", plan)
        self.assertIn("Phase 6.9: Review and commit Phase 6", plan)

    def test_phase62_workspace_setup_checklist_service_exists(self):
        service = _read("apps/onboarding/services/setup_checklist.py")

        for expected in (
            "WorkspaceSetupMetrics",
            "SetupChecklistItem",
            "WorkspaceSetupChecklist",
            "build_workspace_setup_checklist",
            "collect_workspace_setup_metrics",
            "business_profile",
            "accounting_setup",
            "opening_balances",
            "parties",
            "products",
            "opening_stock",
            "invite_team",
            "rates",
            "first_transaction",
        ):
            self.assertIn(expected, service)

        self.assertIn("without mutating application state", service)

    def test_phase65_completion_redirect_helper_exists(self):
        views = _read("apps/onboarding/views.py")

        self.assertIn("_redirect_to_workspace_setup_or_list", views)
        self.assertIn('"workspace_settings_setup"', views)
        self.assertIn('"workspace_list"', views)
        self.assertIn("allow_profile_fallback=True", views)

    def test_phase67_onboarding_team_invites_use_control_plane_service(self):
        views = _read("apps/onboarding/views.py")
        control_plane = _read("apps/orgs/services/control_plane.py")

        self.assertIn("def onboarding_team", views)
        self.assertIn(
            "control_plane.send_onboarding_team_invitations",
            views,
        )
        self.assertNotIn("CompanyInvitation.objects.create", views)
        self.assertNotIn("Role.objects.get", views)
        self.assertIn("def send_onboarding_team_invitations", control_plane)
        self.assertIn("role_policy.assert_can_invite_role", control_plane)
        self.assertIn("CompanyInvitation.create", control_plane)
        self.assertIn("invitation.send_invitation(request)", control_plane)

    def test_phase68_workspace_setup_state_contract_exists(self):
        models = _read("apps/onboarding/models.py")
        services = _read("apps/onboarding/services/setup_state.py")
        orgs_views = _read("apps/orgs/views.py")
        dashboard_template = _read("templates/company/workspace_dashboard.html")
        setup_template = _read("templates/company/workspace_setup.html")

        self.assertIn("class WorkspaceSetupState", models)
        self.assertIn("dismissed_at", models)
        self.assertIn("marked_complete_at", models)
        self.assertIn("build_workspace_setup_display_state", services)
        self.assertIn("should_show_dashboard_card", services)
        self.assertIn("dismiss_workspace_setup", services)
        self.assertIn("mark_workspace_setup_complete", services)
        self.assertIn("reopen_workspace_setup", services)
        self.assertIn("def workspace_setup_state", orgs_views)
        self.assertIn("workspace_settings_setup_state", dashboard_template)
        self.assertIn("setup_state.should_show_dashboard_card", dashboard_template)
        self.assertIn("Mark setup complete", setup_template)
        self.assertIn("Dismiss dashboard card", setup_template)
        self.assertIn("Reopen setup", setup_template)

    def test_phase85_workspace_setup_routes_keep_canonical_and_legacy_entrypoints(self):
        setup_template = _read("templates/company/workspace_setup.html")
        dashboard_template = _read("templates/company/workspace_dashboard.html")
        phase8_plan = _read("docs/ui/phase8_regression_consolidation_plan.md")

        self.assertEqual(
            reverse("workspace_settings_setup", kwargs={"workspace_id": 42}),
            "/workspace/42/settings/setup/",
        )
        self.assertEqual(
            reverse("workspace_settings_setup_state", kwargs={"workspace_id": 42}),
            "/workspace/42/settings/setup/state/",
        )
        self.assertEqual(
            reverse("workspace_setup", kwargs={"workspace_id": 42}),
            "/orgs/workspace/42/setup/",
        )
        self.assertEqual(
            reverse("workspace_setup_state", kwargs={"workspace_id": 42}),
            "/orgs/workspace/42/setup/state/",
        )

        for template in (setup_template, dashboard_template):
            with self.subTest():
                self.assertIn("workspace_settings_setup_state", template)
                self.assertNotIn("{% url 'workspace_setup_state'", template)

        self.assertIn("Phase 8.5", phase8_plan)
        self.assertIn("workspace switching, setup, and onboarding", phase8_plan)

    def test_phase85_workspace_switching_contract_remains_membership_safe(self):
        orgs_views = _read("apps/orgs/views.py")
        orgs_tests = _read("apps/orgs/tests.py")

        self.assertIn("def workspace_select(request, workspace_id):", orgs_views)
        self.assertIn("_assert_workspace_access(request, workspace", orgs_views)
        self.assertIn("user.profile.set_workspace(workspace)", orgs_views)
        self.assertIn("WORKSPACE_SWITCH", orgs_views)
        self.assertIn('next_url and next_url.startswith("/")', orgs_views)

        access_check_index = orgs_views.index("_assert_workspace_access(request, workspace")
        set_workspace_index = orgs_views.index("user.profile.set_workspace(workspace)")
        self.assertLess(access_check_index, set_workspace_index)

        for expected_test in (
            "test_workspace_select_redirects_when_access_denied",
            "test_workspace_select_sets_workspace_when_access_allowed",
        ):
            self.assertIn(expected_test, orgs_tests)

    def test_phase85_workspace_setup_runtime_regression_files_remain_present(self):
        expected_test_files = (
            "apps/onboarding/tests_setup_checklist.py",
            "apps/onboarding/tests_setup_state.py",
            "apps/onboarding/tests_completion_redirects.py",
            "apps/onboarding/tests_company_creation.py",
            "apps/onboarding/tests_team_invites.py",
        )

        for relative_path in expected_test_files:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((PROJECT_ROOT / relative_path).exists())

        setup_checklist_tests = _read("apps/onboarding/tests_setup_checklist.py")
        setup_state_tests = _read("apps/onboarding/tests_setup_state.py")
        completion_tests = _read("apps/onboarding/tests_completion_redirects.py")

        self.assertIn("test_empty_workspace_metrics_keep_checklist_non_blocking", setup_checklist_tests)
        self.assertIn("test_complete_metrics_mark_every_setup_item_complete", setup_checklist_tests)
        self.assertIn("test_display_state_shows_dashboard_card_for_incomplete_active_setup", setup_state_tests)
        self.assertIn("test_state_mutators_update_expected_timestamps", setup_state_tests)
        self.assertIn("test_onboarding_complete_redirects_to_workspace_setup", completion_tests)
        self.assertIn("test_onboarding_skip_redirects_to_workspace_setup_when_workspace_exists", completion_tests)
