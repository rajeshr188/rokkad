from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import resolve, reverse
from invitations.app_settings import app_settings

from apps.orgs import urls as org_urls


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_ROOT = PROJECT_ROOT / "templates"
DOCS_UI_ROOT = PROJECT_ROOT / "docs" / "ui"


class InvitationTeamFlowIntentTests(SimpleTestCase):
    def test_phase4_invitation_team_cleanup_plan_exists(self):
        plan = DOCS_UI_ROOT / "invitation_team_flow_cleanup_plan.md"

        self.assertTrue(plan.exists())
        content = plan.read_text(encoding="utf-8-sig")
        for expected in (
            "Incoming Invitations",
            "Workspace Invitations",
            "Team Members",
            "No current URL or route name breaks",
            "Phase 4.2",
        ):
            self.assertIn(expected, content)

    def test_current_invitation_and_team_routes_remain_compatible(self):
        route_cases = {
            "team_invitations": reverse("team_invitations"),
            "team_accept_invitation": reverse(
                "team_accept_invitation", kwargs={"key": "abc123"}
            ),
            "team_invite": reverse("team_invite", kwargs={"workspace_id": 42}),
            "team_invite_success": reverse("team_invite_success"),
            "team_invitations_list": reverse("team_invitations_list"),
            "team_delete_invitation": reverse(
                "team_delete_invitation", kwargs={"invitation_id": 9}
            ),
            "team_members_list": reverse("team_members_list"),
            "team_change_role": reverse(
                "team_change_role",
                kwargs={"workspace_id": 42, "membership_id": 7},
            ),
            "team_remove_member": reverse(
                "team_remove_member",
                kwargs={"workspace_id": 42, "membership_id": 7},
            ),
            "workspace_leave": reverse("workspace_leave", kwargs={"workspace_id": 42}),
            "my_memberships": reverse("my_memberships"),
        }

        self.assertEqual(route_cases["team_invitations"], "/orgs/team/invitations/")
        self.assertEqual(
            route_cases["team_accept_invitation"],
            "/orgs/team/invitations/accept/abc123/",
        )
        self.assertEqual(
            route_cases["team_invite"],
            "/orgs/workspace/42/team/invite/",
        )
        self.assertEqual(route_cases["team_invite_success"], "/orgs/team/invite/success/")
        self.assertEqual(route_cases["team_invitations_list"], "/orgs/team/invitations/list/")
        self.assertEqual(
            route_cases["team_delete_invitation"],
            "/orgs/team/invitations/9/delete/",
        )
        self.assertEqual(route_cases["team_members_list"], "/orgs/team/members/")
        self.assertEqual(
            route_cases["team_change_role"],
            "/orgs/workspace/42/team/member/7/role/",
        )
        self.assertEqual(
            route_cases["team_remove_member"],
            "/orgs/workspace/42/team/member/7/remove/",
        )
        self.assertEqual(route_cases["workspace_leave"], "/orgs/workspace/42/leave/")
        self.assertEqual(route_cases["my_memberships"], "/orgs/memberships/")

        for route_name, path in route_cases.items():
            with self.subTest(route_name=route_name):
                self.assertEqual(resolve(path).url_name, route_name)

    def test_org_urlpatterns_are_grouped_by_invitation_and_team_intent(self):
        self.assertEqual(
            [pattern.name for pattern in org_urls.ACCOUNT_INVITATION_URLPATTERNS],
            ["team_invitations", "team_accept_invitation"],
        )
        self.assertEqual(
            [pattern.name for pattern in org_urls.WORKSPACE_INVITATION_URLPATTERNS],
            ["team_invite", "team_delete_invitation", "team_invitations_list", "team_invite_success"],
        )
        self.assertEqual(
            [pattern.name for pattern in org_urls.TEAM_MEMBER_URLPATTERNS],
            ["team_remove_member", "team_change_role", "team_members_list", "workspace_leave", "my_memberships"],
        )

    def test_org_urlpatterns_preserve_compatibility_order(self):
        grouped_patterns = (
            org_urls.WORKSPACE_MANAGER_URLPATTERNS
            + org_urls.ACCOUNT_INVITATION_URLPATTERNS
            + org_urls.WORKSPACE_INVITATION_URLPATTERNS
            + org_urls.TEAM_MEMBER_URLPATTERNS
            + org_urls.ACCOUNT_PROFILE_URLPATTERNS
        )

        self.assertEqual(org_urls.urlpatterns, grouped_patterns)
        self.assertEqual(
            [pattern.name for pattern in org_urls.urlpatterns],
            [
                "workspace_selector",
                "workspace_dashboard",
                "workspace_select",
                "workspace_create",
                "workspace_list",
                "workspace_detail",
                "workspace_update",
                "workspace_delete",
                "workspace_preferences",
                "team_invitations",
                "team_accept_invitation",
                "team_invite",
                "team_delete_invitation",
                "team_invitations_list",
                "team_invite_success",
                "team_remove_member",
                "team_change_role",
                "team_members_list",
                "workspace_leave",
                "my_memberships",
                "profile",
                "account_settings",
            ],
        )

    def test_invitation_template_shells_match_current_product_intent(self):
        global_incoming = (
            TEMPLATES_ROOT / "company" / "workspace_invitations.html"
        ).read_text(encoding="utf-8-sig")
        sent_invitations = (
            TEMPLATES_ROOT / "company" / "company_invitations_list.html"
        ).read_text(encoding="utf-8-sig")
        invite_form = (TEMPLATES_ROOT / "company" / "invitation_form.html").read_text(
            encoding="utf-8-sig"
        )
        invite_success = (
            TEMPLATES_ROOT / "company" / "invite_success.html"
        ).read_text(encoding="utf-8-sig")
        team_members = (TEMPLATES_ROOT / "company" / "membership_list.html").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("{% extends 'base_global.html' %}", global_incoming)
        for content in (sent_invitations, invite_form, invite_success, team_members):
            self.assertIn("{% extends 'base_workspace_settings.html' %}", content)

    def test_invitation_and_team_copy_distinguishes_received_from_sent(self):
        global_incoming = (
            TEMPLATES_ROOT / "company" / "workspace_invitations.html"
        ).read_text(encoding="utf-8-sig")
        sent_invitations = (
            TEMPLATES_ROOT / "company" / "company_invitations_list.html"
        ).read_text(encoding="utf-8-sig")
        invite_form = (TEMPLATES_ROOT / "company" / "invitation_form.html").read_text(
            encoding="utf-8-sig"
        )
        invite_success = (
            TEMPLATES_ROOT / "company" / "invite_success.html"
        ).read_text(encoding="utf-8-sig")

        self.assertIn("Invitations for You", global_incoming)
        self.assertIn("sent to your email", global_incoming)
        self.assertIn("Sent Workspace Invitations", sent_invitations)
        self.assertIn("Track invitations sent for", sent_invitations)
        self.assertIn("Invite Team Member", invite_form)
        self.assertIn("Send Workspace Invitation", invite_form)
        self.assertIn("Workspace Invitation Sent", invite_success)

    def test_invitation_and_team_templates_do_not_contain_known_mojibake(self):
        template_paths = (
            "company/workspace_invitations.html",
            "company/company_invitations_list.html",
            "company/invitation_form.html",
            "company/invite_success.html",
            "company/membership_list.html",
        )

        for template_path in template_paths:
            with self.subTest(template_path=template_path):
                content = (TEMPLATES_ROOT / template_path).read_text(
                    encoding="utf-8-sig"
                )
                self.assertNotIn("Â", content)
                self.assertNotIn("â", content)
                self.assertNotIn("Ã", content)
                self.assertNotIn("→", content)
                self.assertNotIn("·", content)

    def test_workspace_scoped_redirect_cleanup_contract_is_documented_in_views(self):
        views_content = (PROJECT_ROOT / "apps" / "orgs" / "views.py").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn(
            "f\"{reverse('team_invite_success')}?workspace_id={company.id}\"",
            views_content,
        )
        self.assertIn("def _get_workspace_from_query(request):", views_content)
        self.assertIn('workspace_id = request.GET.get("workspace_id")', views_content)
        self.assertIn("raise Http404(\"Invalid workspace ID\")", views_content)
        self.assertIn(
            "f\"{reverse('team_invitations_list')}?workspace_id={invitation_workspace_id}\"",
            views_content,
        )

    def test_invite_success_uses_workspace_settings_shell_after_cleanup(self):
        success_template = (TEMPLATES_ROOT / "company" / "invite_success.html").read_text(
            encoding="utf-8-sig"
        )
        plan = (DOCS_UI_ROOT / "invitation_team_flow_cleanup_plan.md").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("{% extends 'base_workspace_settings.html' %}", success_template)
        self.assertIn("sent_invitations_url", success_template)
        self.assertIn("Invite Another", success_template)
        self.assertIn("company/invite_success.html", plan)
        self.assertIn("Status: complete", plan)

    def test_direct_accept_route_uses_orgs_adapter_with_django_fallback(self):
        views_content = (PROJECT_ROOT / "apps" / "orgs" / "views.py").read_text(
            encoding="utf-8-sig"
        )
        urls_content = (PROJECT_ROOT / "apps" / "orgs" / "urls.py").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("from invitations.views import AcceptInvite", views_content)
        self.assertIn("views.team_accept_invitation", urls_content)
        self.assertIn("def team_accept_invitation(request, key):", views_content)
        self.assertIn("return AcceptInvite.as_view()(request, key=key)", views_content)
        self.assertIn("control_plane.accept_invitation(", views_content)
        self.assertEqual(settings.INVITATIONS_INVITATION_MODEL, "orgs.CompanyInvitation")
        self.assertTrue(app_settings.CONFIRM_INVITE_ON_GET)
        self.assertFalse(app_settings.ACCEPT_INVITE_AFTER_SIGNUP)
        self.assertEqual(app_settings.SIGNUP_REDIRECT, "account_signup")

    def test_custom_incoming_invitation_accept_flow_sets_workspace_context(self):
        views_content = (PROJECT_ROOT / "apps" / "orgs" / "views.py").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("control_plane.accept_invitation(", views_content)
        self.assertIn("user.profile.workspace = invitation.company", views_content)
        self.assertIn(
            '"workspace_dashboard", workspace_id=invitation.company.id',
            views_content,
        )
        self.assertIn("control_plane.decline_invitation(", views_content)

    def test_direct_accept_signal_bridges_membership_but_not_product_flow(self):
        signals_content = (PROJECT_ROOT / "apps" / "orgs" / "signals.py").read_text(
            encoding="utf-8-sig"
        )

        self.assertIn("@receiver(invite_accepted)", signals_content)
        self.assertIn("Membership.objects.get_or_create", signals_content)
        self.assertIn("PendingInvitation.objects.get_or_create", signals_content)
        self.assertNotIn("profile.workspace", signals_content)
        self.assertNotIn("AuditLog", signals_content)
