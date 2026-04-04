from contextlib import nullcontext
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import RequestFactory, SimpleTestCase
from django.utils import timezone

from apps.tenant_apps.girvi.views.loan import (
    get_interestrate,
    loan_create,
    loan_create_preview,
    loan_update,
)
from apps.tenant_apps.girvi.forms import build_initial_loan_item_formset
from apps.tenant_apps.girvi.models.loan_refactored import LoanLifecycleState
from apps.tenant_apps.girvi.services import (
    LoanCreateCommand,
    LoanCreationService,
    LoanItemCreateInput,
)


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

    def test_prefixed_itemtype_change_updates_matching_interest_field(self):
        request = self.factory.get(
            "/girvi/loan/get-interestrate/",
            data={"items-0-itemtype": "Silver"},
        )
        request.user = SimpleNamespace(
            is_authenticated=True,
            profile=SimpleNamespace(workspace=SimpleNamespace()),
        )

        with patch(
            "apps.tenant_apps.girvi.views.loan.CompanyPreferences",
            return_value=SimpleNamespace(
                interest_rate_gold=1.5,
                interest_rate_silver=2.25,
                interest_rate_other=3.0,
            ),
        ):
            response = get_interestrate(request)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="items-0-interestrate"')
        self.assertContains(response, 'value="2.25"')

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
        ) as given_loan_cls, patch(
            "apps.tenant_apps.girvi.service_modules.creation.ContentType.objects.get_for_model",
            return_value="givenloan-ct",
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanChangeLog.objects.create"
        ) as log_create:
            result = LoanCreationService.execute(command)

        self.assertTrue(result.success)
        self.assertEqual(given_loan_cls.call_args.kwargs["status"], LoanLifecycleState.DRAFT)
        log_create.assert_called_once()
        self.assertEqual(log_create.call_args.kwargs["source"], "Initial")
        self.assertEqual(log_create.call_args.kwargs["target"], "Draft")
    def test_initial_item_formset_uses_prefixed_interest_target(self):
        formset_class = build_initial_loan_item_formset()
        formset = formset_class(prefix="items")
        attrs = formset.forms[0].fields["itemtype"].widget.attrs

        self.assertEqual(attrs["hx-target"], "#div_id_items-0-interestrate")
        self.assertIn("girvi/loan/get-interestrate/", attrs["hx-get"])

    def test_initial_item_formset_allows_blank_extra_rows(self):
        data = {
            "items-TOTAL_FORMS": "3",
            "items-INITIAL_FORMS": "0",
            "items-MIN_NUM_FORMS": "0",
            "items-MAX_NUM_FORMS": "1000",
            "items-0-itemdesc": "Gold ring",
            "items-0-itemtype": "Gold",
            "items-0-quantity": "1",
            "items-0-weight": "10.500",
            "items-0-purity": "91.60",
            "items-0-loanamount": "0",
            "items-0-interestrate": "1.50",
            "items-1-itemdesc": "",
            "items-1-itemtype": "Gold",
            "items-1-quantity": "",
            "items-1-weight": "",
            "items-1-purity": "",
            "items-1-loanamount": "",
            "items-1-interestrate": "",
            "items-2-itemdesc": "",
            "items-2-itemtype": "Gold",
            "items-2-quantity": "",
            "items-2-weight": "",
            "items-2-purity": "",
            "items-2-loanamount": "",
            "items-2-interestrate": "",
        }
        formset_class = build_initial_loan_item_formset()

        with patch("apps.tenant_apps.girvi.forms.Rate.objects.filter") as rate_filter:
            rate_filter.return_value.exists.return_value = False
            formset = formset_class(data, prefix="items")
            is_valid = formset.is_valid()

        self.assertTrue(is_valid)
        self.assertEqual(formset.errors, [{}, {}, {}])

    def test_execute_creates_initial_items_when_provided(self):
        command = LoanCreateCommand(
            borrower=SimpleNamespace(pk=1),
            series=SimpleNamespace(is_active=True, name="A"),
            loan_date=timezone.now(),
            tenure=3,
            interest_type="Simple",
            created_by=SimpleNamespace(),
            loan_id="A0007",
            initial_items=[
                LoanItemCreateInput(
                    itemdesc="Gold ring",
                    itemtype="Gold",
                    quantity=1,
                    weight=Decimal("10.500"),
                    purity=Decimal("91.60"),
                    loanamount=Decimal("25000.00"),
                    interestrate=Decimal("1.50"),
                )
            ],
        )
        fake_loan = SimpleNamespace(id=77, pk=77, loan_id="A0007", save=MagicMock())
        fake_item = SimpleNamespace(full_clean=MagicMock(), save=MagicMock())

        with patch(
            "apps.tenant_apps.girvi.service_modules.creation.transaction.atomic",
            side_effect=lambda: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.GivenLoan",
            return_value=fake_loan,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanItem",
            return_value=fake_item,
        ) as loan_item_cls, patch(
            "apps.tenant_apps.girvi.service_modules.creation.ContentType.objects.get_for_model",
            return_value="givenloan-ct",
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanChangeLog.objects.create"
        ):
            result = LoanCreationService.execute(command)

        self.assertTrue(result.success)
        self.assertEqual(loan_item_cls.call_count, 1)
        self.assertEqual(loan_item_cls.call_args.kwargs["loan"], fake_loan)
        fake_item.full_clean.assert_called_once()
        fake_item.save.assert_called_once()

    def test_execute_fails_when_initial_item_validation_fails(self):
        command = LoanCreateCommand(
            borrower=SimpleNamespace(pk=1),
            series=SimpleNamespace(is_active=True, name="A"),
            loan_date=timezone.now(),
            tenure=3,
            interest_type="Simple",
            created_by=SimpleNamespace(),
            loan_id="A0008",
            initial_items=[
                LoanItemCreateInput(
                    itemdesc="Heavy chain",
                    itemtype="Gold",
                    quantity=1,
                    weight=Decimal("10.000"),
                    purity=Decimal("91.60"),
                    loanamount=Decimal("999999.00"),
                    interestrate=Decimal("1.50"),
                )
            ],
        )
        fake_loan = SimpleNamespace(id=78, pk=78, loan_id="A0008", save=MagicMock())
        fake_item = SimpleNamespace(
            full_clean=MagicMock(side_effect=ValidationError("Invalid item")),
            save=MagicMock(),
        )

        with patch(
            "apps.tenant_apps.girvi.service_modules.creation.transaction.atomic",
            side_effect=lambda: nullcontext(),
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.GivenLoan",
            return_value=fake_loan,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanItem",
            return_value=fake_item,
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.ContentType.objects.get_for_model",
            return_value="givenloan-ct",
        ), patch(
            "apps.tenant_apps.girvi.service_modules.creation.LoanChangeLog.objects.create"
        ):
            result = LoanCreationService.execute(command)

        self.assertFalse(result.success)
        self.assertIn("invalid item", result.message.lower())
        fake_item.save.assert_not_called()

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
        fake_item_formset = MagicMock()
        fake_item_formset.is_valid.return_value = True
        fake_item_formset.cleaned_data = [
            {
                "itemdesc": "Gold ring",
                "itemtype": "Gold",
                "quantity": 1,
                "weight": Decimal("10.500"),
                "purity": Decimal("91.60"),
                "loanamount": Decimal("25000.00"),
                "interestrate": Decimal("1.50"),
            }
        ]

        fake_result = SimpleNamespace(
            success=True,
            message="Created Loan: A0001",
            loan=SimpleNamespace(id=42, loan_id="A0001"),
        )

        with patch("apps.tenant_apps.girvi.views.loan.LoanForm", return_value=fake_form), patch(
            "apps.tenant_apps.girvi.views.loan.build_initial_loan_item_formset",
            return_value=lambda *args, **kwargs: fake_item_formset,
        ), patch(
            "apps.tenant_apps.girvi.views.loan.LoanCreationService.execute",
            return_value=fake_result,
        ) as execute_mock, patch("apps.tenant_apps.girvi.views.loan.messages.success"), patch(
            "apps.tenant_apps.girvi.views.loan.messages.warning"
        ):
            response = loan_create(request)

        execute_mock.assert_called_once()
        command = execute_mock.call_args.args[0]
        self.assertEqual(len(command.initial_items), 1)
        self.assertEqual(command.initial_items[0].itemdesc, "Gold ring")
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
