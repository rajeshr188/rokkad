from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.onboarding import views


class OnboardingTeamInviteTests(SimpleTestCase):
    def test_onboarding_team_uses_orgs_control_plane_invitation_service(self):
        request = RequestFactory().post(
            "/onboarding/team/",
            data={"email_addresses": "a@example.com\nb@example.com"},
        )
        request.user = SimpleNamespace(is_authenticated=True)
        progress = SimpleNamespace(
            company_created=True,
            team_setup_completed=False,
            skipped_team=False,
            next_step_url="/onboarding/tour/",
            mark_step_complete=MagicMock(),
        )
        company = SimpleNamespace(id=12, name="Acme")
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {"email_addresses": ["a@example.com", "b@example.com"]}
        invitation_result = {
            "invitations": [SimpleNamespace(email="a@example.com")],
            "failed": [{"email": "b@example.com", "error": Exception("boom")}],
            "invited_count": 1,
            "failed_count": 1,
        }

        with (
            patch("apps.onboarding.views.get_or_create_progress", return_value=progress),
            patch("apps.onboarding.views.resolve_request_workspace", return_value=company),
            patch("apps.onboarding.views.TeamInviteForm", return_value=form),
            patch(
                "apps.onboarding.views.control_plane.send_onboarding_team_invitations",
                return_value=invitation_result,
            ) as send_invitations,
            patch("apps.onboarding.views.logger.error") as logger_error,
            patch("apps.onboarding.views.AuditLog.log") as audit_log,
            patch("apps.onboarding.views.messages.success") as success_message,
            patch("apps.onboarding.views.redirect", return_value="redirected") as redirect,
        ):
            response = views.onboarding_team(request)

        self.assertEqual(response, "redirected")
        send_invitations.assert_called_once_with(
            email_addresses=["a@example.com", "b@example.com"],
            actor=request.user,
            company=company,
            request=request,
        )
        logger_error.assert_called_once()
        success_message.assert_called_once_with(
            request,
            "Invitations sent to 1 team members!",
        )
        audit_log.assert_called_once()
        self.assertEqual(audit_log.call_args.kwargs["data"]["count"], 1)
        self.assertEqual(audit_log.call_args.kwargs["data"]["failed_count"], 1)
        progress.mark_step_complete.assert_called_once_with(3)
        redirect.assert_called_once_with("/onboarding/tour/")

    def test_onboarding_team_skip_preserves_existing_optional_step_behavior(self):
        request = RequestFactory().post("/onboarding/team/", data={"skip": "1"})
        request.user = SimpleNamespace(is_authenticated=True)
        progress = SimpleNamespace(
            company_created=True,
            team_setup_completed=False,
            skipped_team=False,
            next_step_url="/onboarding/tour/",
            skip_step=MagicMock(),
        )

        with (
            patch("apps.onboarding.views.get_or_create_progress", return_value=progress),
            patch("apps.onboarding.views.resolve_request_workspace"),
            patch("apps.onboarding.views.messages.info") as info_message,
            patch("apps.onboarding.views.redirect", return_value="redirected") as redirect,
        ):
            response = views.onboarding_team(request)

        self.assertEqual(response, "redirected")
        progress.skip_step.assert_called_once_with(3)
        info_message.assert_called_once_with(
            request,
            "You can invite team members later from settings.",
        )
        redirect.assert_called_once_with("/onboarding/tour/")
