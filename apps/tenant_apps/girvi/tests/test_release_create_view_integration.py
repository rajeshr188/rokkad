from contextlib import nullcontext
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.release import release_create


class ReleaseCreateViewIntegrationTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def _user(self):
        return SimpleNamespace(
            is_authenticated=True,
            username="demo-user",
            profile=SimpleNamespace(workspace="tenant-1"),
        )

    def _loan(self):
        return SimpleNamespace(pk=42, loan_id="GL-42", status="Disbursed")

    def _bind_workspace(self, request):
        request.tenant = SimpleNamespace(
            schema_name="tenant-1",
            owner=request.user,
            theme="default",
            logo="",
        )
        return request

    def _checklist_ready(self):
        return {
            "can_release": True,
            "blockers": [],
            "outstanding_amount": "0.00",
            "total_with_lenders": 0,
        }

    def _checklist_blocked(self, blocker="Loan has outstanding dues"):
        return {
            "can_release": False,
            "blockers": [blocker],
            "outstanding_amount": "500.00",
            "total_with_lenders": 0,
        }

    def test_release_create_get_renders_preview_feedback(self):
        loan = self._loan()
        loan.borrower = "Demo Borrower"
        request = self.factory.get(f"/girvi/release/create/{loan.pk}/")
        request.user = self._user()
        request.htmx = True
        request._messages = MagicMock()
        self._bind_workspace(request)

        fake_form = MagicMock()
        fake_form.is_bound = False
        fake_form.loan_preview = loan

        fake_preview = SimpleNamespace(
            is_valid=True,
            current_status="Disbursed",
            outstanding_amount="₹10,000.00",
            warnings=["Loan has no outstanding balance. Release accounting may be skipped."],
            errors=[],
        )

        with patch("apps.tenant_apps.girvi.views.release.get_object_or_404", return_value=loan), patch(
            "apps.tenant_apps.girvi.views.release.ReleaseForm", return_value=fake_form
        ), patch(
            "apps.tenant_apps.girvi.views.release.build_release_readiness_checklist",
            return_value=self._checklist_ready(),
        ), patch(
            "apps.tenant_apps.girvi.views.release.ReleaseLifecycleService.preview",
            return_value=fake_preview,
        ):
            response = release_create(request, pk=loan.pk)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context_data["release_preview"], fake_preview)
        self.assertIn(
            "Loan has no outstanding balance. Release accounting may be skipped.",
            response.context_data["release_preview"].warnings,
        )

    def test_release_create_posts_via_service_and_invokes_flow_and_posting(self):
        loan = self._loan()
        request = self.factory.post("/girvi/release/create/", data={"loan": loan.pk})
        request.user = self._user()
        request.htmx = False
        request._messages = MagicMock()
        self._bind_workspace(request)

        fake_form = MagicMock()
        fake_form.is_valid.return_value = True
        fake_form.cleaned_data = {
            "loan": loan,
            "release_date": datetime(2026, 4, 1, 10, 30),
            "released_by": None,
        }

        class FakeRelease:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)

            def save(self):
                return None

        flow = MagicMock()
        flow.request_closure.can_proceed.return_value = True
        flow.complete_closure.can_proceed.return_value = True

        with patch("apps.tenant_apps.girvi.views.release.ReleaseForm", return_value=fake_form), patch(
            "apps.tenant_apps.girvi.views.release.build_release_readiness_checklist",
            return_value=self._checklist_ready(),
        ), patch(
            "apps.tenant_apps.girvi.services.transaction.atomic", side_effect=lambda: nullcontext()
        ), patch("apps.tenant_apps.girvi.services.apps.get_model", return_value=FakeRelease), patch(
            "apps.tenant_apps.girvi.service_modules.release_lifecycle.build_runtime_loan_flow", return_value=flow
        ), patch("apps.tenant_apps.girvi.service_modules.release_lifecycle.record_loan_release") as post_release:
            response = release_create(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/girvi/loan/detail/42/", response["Location"])
        self.assertIn("/girvi/loan/detail/42/", response["HX-Push-Url"])
        flow.request_closure.assert_called_once()
        flow.complete_closure.assert_called_once()
        created_release = post_release.call_args.args[0]
        self.assertEqual(created_release.loan, loan)
        post_release.assert_called_once()

    def test_release_create_get_redirects_to_checklist_when_blocked(self):
        loan = self._loan()
        loan.borrower = "Demo Borrower"
        request = self.factory.get(f"/girvi/release/create/{loan.pk}/")
        request.user = self._user()
        request.htmx = False
        request._messages = MagicMock()
        self._bind_workspace(request)

        with patch("apps.tenant_apps.girvi.views.release.get_object_or_404", return_value=loan), patch(
            "apps.tenant_apps.girvi.views.release.build_release_readiness_checklist",
            return_value=self._checklist_blocked(),
        ), patch("apps.tenant_apps.girvi.views.release.ReleaseForm") as form_cls:
            response = release_create(request, pk=loan.pk)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/girvi/custody/loans/42/release/check/", response["Location"])
        form_cls.assert_not_called()

    def test_release_create_post_blocks_when_checklist_not_ready(self):
        loan = self._loan()
        request = self.factory.post("/girvi/release/create/", data={"loan": loan.pk})
        request.user = self._user()
        request.htmx = False
        request._messages = MagicMock()
        self._bind_workspace(request)

        fake_form = MagicMock()
        fake_form.is_valid.return_value = True
        fake_form.cleaned_data = {
            "loan": loan,
            "release_date": datetime(2026, 4, 1, 10, 30),
            "released_by": None,
        }

        fake_preview = SimpleNamespace(
            is_valid=True,
            current_status="Disbursed",
            outstanding_amount="500.00",
            warnings=[],
            errors=[],
        )

        with patch("apps.tenant_apps.girvi.views.release.ReleaseForm", return_value=fake_form), patch(
            "apps.tenant_apps.girvi.views.release.ReleaseLifecycleService.preview",
            return_value=fake_preview,
        ), patch(
            "apps.tenant_apps.girvi.views.release.build_release_readiness_checklist",
            return_value=self._checklist_blocked("Loan has outstanding dues of 500.00"),
        ), patch(
            "apps.tenant_apps.girvi.views.release.ReleaseLifecycleService.execute"
        ) as execute_service:
            response = release_create(request)

        self.assertEqual(response.status_code, 200)
        execute_service.assert_not_called()
        fake_form.add_error.assert_called_with(None, "Loan has outstanding dues of 500.00")
