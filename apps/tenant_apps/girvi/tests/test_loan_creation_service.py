from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.girvi.views.loan import (
    loan_create,
    loan_create_preview,
    loan_update,
)
from apps.tenant_apps.girvi.services import LoanCreateCommand, LoanCreationService


class LoanCreationServiceTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_execute_rejects_inactive_series(self):
        command = LoanCreateCommand(
            borrower=SimpleNamespace(pk=1),
            series=SimpleNamespace(is_active=False, name="A"),
            loan_date="2026-04-02T10:00",
            tenure=3,
            interest_type="Simple",
            created_by=SimpleNamespace(),
            loan_id="A0001",
        )

        result = LoanCreationService.execute(command)

        self.assertFalse(result.success)
        self.assertIn("inactive", result.message.lower())

    def test_preview_returns_expected_loan_id_without_created_by(self):
        command = LoanCreateCommand(
            borrower=SimpleNamespace(pk=1),
            series=SimpleNamespace(is_active=True, name="A", pk=7),
            loan_date=timezone.now(),
            tenure=3,
            interest_type="Simple",
            created_by=None,
            loan_id="",
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanIDGenerator.generate",
            return_value="A0002",
        ):
            preview = LoanCreationService.preview(command)

        self.assertTrue(preview.is_valid)
        self.assertEqual(preview.expected_loan_id, "A0002")
        self.assertEqual(preview.errors, [])

    def test_preview_includes_borrower_account_summary(self):
        borrower = SimpleNamespace(
            pk=1,
            account=SimpleNamespace(
                credit_limit="₹50,000.00",
                get_current_balance=MagicMock(return_value="₹12,500.00"),
                get_available_credit=MagicMock(return_value="₹37,500.00"),
            ),
        )
        command = LoanCreateCommand(
            borrower=borrower,
            series=SimpleNamespace(is_active=True, name="A", pk=7),
            loan_date=timezone.now(),
            tenure=3,
            interest_type="Simple",
            created_by=None,
            loan_id="",
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanIDGenerator.generate",
            return_value="A0004",
        ):
            preview = LoanCreationService.preview(command)

        self.assertEqual(preview.borrower_credit_limit, "₹50,000.00")
        self.assertEqual(preview.borrower_current_balance, "₹12,500.00")
        self.assertEqual(preview.borrower_available_credit, "₹37,500.00")

    def test_preview_rejects_future_dates(self):
        command = LoanCreateCommand(
            borrower=SimpleNamespace(pk=1),
            series=SimpleNamespace(is_active=True, name="A", pk=7),
            loan_date=timezone.now() + timedelta(days=1),
            tenure=3,
            interest_type="Simple",
            created_by=None,
            loan_id="",
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanIDGenerator.generate",
            return_value="A0003",
        ):
            preview = LoanCreationService.preview(command)

        self.assertFalse(preview.is_valid)
        self.assertIn("future", " ".join(preview.errors).lower())

    def test_execute_records_creation_audit_log(self):
        command = LoanCreateCommand(
            borrower=SimpleNamespace(pk=1),
            series=SimpleNamespace(is_active=True, name="A"),
            loan_date=timezone.now(),
            tenure=3,
            interest_type="Simple",
            created_by=SimpleNamespace(),
            loan_id="A0001",
        )
        fake_loan = SimpleNamespace(id=99, pk=99, loan_id="A0001", save=MagicMock())

        with patch(
            "apps.tenant_apps.girvi.service_modules.creation.transaction.atomic",
            side_effect=lambda: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.GivenLoan",
            return_value=fake_loan,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.ContentType.objects.get_for_model",
            return_value="givenloan-ct",
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanChangeLog.objects.create"
        ) as log_create:
            result = LoanCreationService.execute(command)

        self.assertTrue(result.success)
        log_create.assert_called_once()
        self.assertEqual(log_create.call_args.kwargs["source"], "Initial")
        self.assertEqual(log_create.call_args.kwargs["target"], "Created")

    def test_loan_create_post_uses_creation_service(self):
        request = self.factory.post("/girvi/loan/create/", data={"loan_id": "A0001"})
        request.user = SimpleNamespace(is_authenticated=True)

        fake_form = MagicMock()
        fake_form.is_valid.return_value = True
        fake_form.cleaned_data = {
            "borrower": SimpleNamespace(pk=1),
            "series": SimpleNamespace(is_active=True, name="A"),
            "loan_date": "2026-04-02T10:00",
            "tenure": 3,
            "interest_type": "Simple",
            "loan_id": "A0001",
        }

        fake_result = SimpleNamespace(
            success=True,
            message="Created Loan: A0001",
            loan=SimpleNamespace(id=42, loan_id="A0001"),
        )

        with patch("apps.tenant_apps.girvi.views.loan.LoanForm", return_value=fake_form), patch(
            "apps.tenant_apps.girvi.views.loan.LoanCreationService.execute",
            return_value=fake_result,
        ) as execute_mock, patch("apps.tenant_apps.girvi.views.loan.messages.success"), patch(
            "apps.tenant_apps.girvi.views.loan.messages.warning"
        ):
            response = loan_create(request)

        execute_mock.assert_called_once()
        self.assertIn("/loan/detail/42/", response["HX-Redirect"])

    def test_loan_update_post_does_not_use_creation_service(self):
        request = self.factory.post("/girvi/loan/update/42/", data={"loan_id": "A0001"})
        request.user = SimpleNamespace(is_authenticated=True)

        existing_loan = SimpleNamespace(
            id=42,
            loan_id="A0001",
            created_by=SimpleNamespace(),
            save=MagicMock(),
        )
        fake_form = MagicMock()
        fake_form.is_valid.return_value = True
        fake_form.save.return_value = existing_loan

        with patch("apps.tenant_apps.girvi.views.loan.get_object_or_404", return_value=existing_loan), patch(
            "apps.tenant_apps.girvi.views.loan.LoanForm", return_value=fake_form
        ), patch(
            "apps.tenant_apps.girvi.views.loan.transaction.atomic", side_effect=lambda: nullcontext()
        ), patch(
            "apps.tenant_apps.girvi.views.loan.LoanCreationService.execute"
        ) as execute_mock, patch("apps.tenant_apps.girvi.views.loan.messages.success"):
            response = loan_update(request, 42)

        execute_mock.assert_not_called()
        self.assertIn("/loan/detail/42/", response["HX-Redirect"])

    def test_live_preview_endpoint_renders_preview_partial(self):
        request = self.factory.get(
            "/girvi/loan/create/preview/",
            data={"borrower": "1", "series": "7", "loan_id": "A0005"},
        )
        request.user = SimpleNamespace(is_authenticated=True)

        fake_preview = SimpleNamespace(
            is_valid=True,
            expected_loan_id="A0005",
            borrower="Test Borrower",
            series="Series A",
            loan_date=timezone.now(),
            tenure=3,
            interest_type="Simple",
            warnings=[],
            errors=[],
        )

        with patch(
            "apps.tenant_apps.girvi.views.loan._build_create_preview_from_data",
            return_value=fake_preview,
        ):
            response = loan_create_preview(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Loan Creation Preview")
        self.assertContains(response, "A0005")
