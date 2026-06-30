from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.onboarding import views


class OnboardingCompanyCreationTests(SimpleTestCase):
    def test_onboarding_company_uses_orgs_control_plane_creation_service(self):
        request = RequestFactory().post("/onboarding/company/", data={"name": "Acme"})
        request.user = SimpleNamespace(
            is_authenticated=True,
            profile=SimpleNamespace(set_workspace=MagicMock()),
        )
        progress = SimpleNamespace(
            profile_completed=True,
            company_created=False,
            next_step_url="/onboarding/team/",
            mark_step_complete=MagicMock(),
        )
        company = SimpleNamespace(id=12, name="Acme")
        form = MagicMock()
        form.is_valid.return_value = True
        form.cleaned_data = {"industry": "jewellery", "company_size": "small"}

        with (
            patch("apps.onboarding.views.get_or_create_progress", return_value=progress),
            patch("apps.onboarding.views.CompanySetupForm", return_value=form),
            patch(
                "apps.onboarding.views.control_plane.create_onboarding_workspace_from_form",
                return_value=(company, "fresh"),
            ) as create_workspace,
            patch("apps.onboarding.views.OnboardingChoice.objects.create") as create_choice,
            patch("apps.onboarding.views.AuditLog.log") as audit_log,
            patch("apps.onboarding.views.messages.success") as success_message,
            patch("apps.onboarding.views.redirect", return_value="redirected") as redirect,
        ):
            response = views.onboarding_company(request)

        self.assertEqual(response, "redirected")
        create_workspace.assert_called_once_with(
            form=form,
            user=request.user,
            request=request,
            provision_workspace=views._provision_company_schema,
            seed_workspace_defaults=views._seed_company_schema_defaults,
        )
        request.user.profile.set_workspace.assert_called_once_with(company)
        progress.mark_step_complete.assert_called_once_with(2)
        self.assertEqual(create_choice.call_count, 2)
        audit_log.assert_called_once()
        self.assertEqual(
            audit_log.call_args.kwargs["data"]["provisioning_mode"],
            "fresh",
        )
        success_message.assert_called_once()
        redirect.assert_called_once_with("/onboarding/team/")
