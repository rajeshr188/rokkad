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
        return SimpleNamespace(pk=42, loan_id="GL-42", status="DISBURSED")

    def test_release_create_get_renders_preview_feedback(self):
        loan = self._loan()
        loan.borrower = "Demo Borrower"
        request = self.factory.get(f"/girvi/release/create/{loan.pk}/")
        request.user = self._user()
        request.htmx = True
        request._messages = MagicMock()

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
            "apps.tenant_apps.girvi.views.release.ReleaseLifecycleService.preview",
            return_value=fake_preview,
        ):
            response = release_create(request, pk=loan.pk)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Release Preview")
        self.assertContains(response, "Loan has no outstanding balance. Release accounting may be skipped.")

    def test_release_create_posts_via_service_and_invokes_flow_and_posting(self):
        loan = self._loan()
        request = self.factory.post("/girvi/release/create/", data={"loan": loan.pk})
        request.user = self._user()
        request.htmx = False
        request._messages = MagicMock()

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
        flow.deliver.can_proceed.return_value = True

        with patch("apps.tenant_apps.girvi.views.release.ReleaseForm", return_value=fake_form), patch(
            "apps.tenant_apps.girvi.services.transaction.atomic", side_effect=lambda: nullcontext()
        ), patch("apps.tenant_apps.girvi.services.apps.get_model", return_value=FakeRelease), patch(
            "apps.tenant_apps.girvi.flows.LoanFlow", return_value=flow
        ), patch("apps.tenant_apps.girvi.payment_service.record_loan_release") as post_release:
            response = release_create(request)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/girvi/loan/detail/42/", response["Location"])
        self.assertIn("/girvi/loan/detail/42/", response["HX-Push-Url"])
        flow.deliver.assert_called_once()
        created_release = post_release.call_args.args[0]
        self.assertEqual(created_release.loan, loan)
        post_release.assert_called_once()
