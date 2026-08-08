from datetime import date
from decimal import Decimal
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.contenttypes.models import ContentType
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from moneyed import Money

from apps.tenant_apps.dea.models.payment import PaymentVoucher
from apps.tenant_apps.girvi.forms import GivenLoanRepaymentForm, RequestClosureLoanForm
from apps.tenant_apps.girvi.transition_registry import get_transition_form_ui
from apps.tenant_apps.girvi.models import LoanStatus
from apps.tenant_apps.girvi.service_modules.payment import (
    record_loan_disbursal,
    record_loan_release,
)
from apps.tenant_apps.girvi.views.custody_views import loan_custody_summary
from apps.tenant_apps.girvi.views.loan import loan_transition_view
from apps.tenant_apps.girvi.views.loanpayment import loan_payment_create_view
from apps.tenant_apps.girvi.views.prints import print_loan


class PR1FormAndModelGuardTests(SimpleTestCase):
    def test_given_loan_repayment_form_rejects_interest_gt_total(self):
        form = GivenLoanRepaymentForm(
            data={
                "total_amount": "100.00",
                "payment_date": "2026-03-23T10:30",
                "payment_method": "CASH",
                "interest_amount": "101.00",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("interest_amount", form.errors)

    def test_given_loan_repayment_form_rejects_overpayment_when_loan_supplied(self):
        loan = SimpleNamespace(
            pk=None,
            get_loan_amount=Decimal("1000.00"),
            outstanding_interest=Decimal("100.00"),
            get_total_principal_payments=lambda: Decimal("0.00"),
            get_total_interest_payments=lambda: Decimal("0.00"),
            get_total_payments=lambda: Decimal("0.00"),
        )
        form = GivenLoanRepaymentForm(
            data={
                "total_amount": "1100.01",
                "payment_date": "2026-03-23T10:30",
                "payment_method": "CASH",
                "interest_amount": "100.00",
            },
            loan=loan,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("total_amount", form.errors)

    def test_given_loan_repayment_form_rejects_interest_over_allocation(self):
        loan = SimpleNamespace(
            pk=None,
            get_loan_amount=Decimal("1000.00"),
            outstanding_interest=Decimal("100.00"),
            get_total_principal_payments=lambda: Decimal("0.00"),
            get_total_interest_payments=lambda: Decimal("0.00"),
            get_total_payments=lambda: Decimal("0.00"),
        )
        form = GivenLoanRepaymentForm(
            data={
                "total_amount": "500.00",
                "payment_date": "2026-03-23T10:30",
                "payment_method": "CASH",
                "interest_amount": "101.00",
            },
            loan=loan,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("interest_amount", form.errors)

    def test_paymentvoucher_get_voucher_type_requires_source(self):
        voucher = PaymentVoucher(direction="RECEIPT")
        with self.assertRaises(ValueError):
            voucher.get_voucher_type()

    def test_paymentvoucher_allows_disbursal_receipt_semantics(self):
        voucher = PaymentVoucher(
            payment_type="DISBURSAL",
            direction="RECEIPT",
            source_content_type_id=1,
            source_object_id=1,
            total_amount=Money(100, "INR"),
            amount_in_base_currency=Money(100, "INR"),
        )

        voucher.clean()

    def test_paymentvoucher_classifies_givenloan_release_when_flagged(self):
        voucher = PaymentVoucher(
            direction="RECEIPT",
            create_release=True,
            source_object_id=1,
            total_amount=Money(100, "INR"),
            amount_in_base_currency=Money(100, "INR"),
        )
        voucher.source_content_type_id = 1
        voucher._state.fields_cache["source_content_type"] = ContentType(
            app_label="girvi", model="givenloan"
        )

        self.assertEqual(voucher.get_voucher_type(), "GIVENLOAN_RELEASE")


class PR1RepaymentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.loanpayment.get_object_or_404")
    def test_repayment_get_context_includes_settlement_preview(self, mock_get_object_or_404):
        loan = SimpleNamespace(
            pk=1,
            loan_id="GL-001",
            borrower="Asha",
            get_loan_amount=Decimal("1000.00"),
            outstanding_interest=Decimal("100.00"),
            get_total_principal_payments=lambda: Decimal("200.00"),
            get_total_interest_payments=lambda: Decimal("20.00"),
            get_total_payments=lambda: Decimal("220.00"),
        )
        mock_get_object_or_404.return_value = loan

        request = self.factory.get("/girvi/loanpayment/1/create/")
        request.user = self.user
        request.htmx = False

        response = loan_payment_create_view.__wrapped__(request, pk=1)

        self.assertEqual(response.context_data["settlement"].total_outstanding, Decimal("900.00"))
        self.assertEqual(
            response.context_data["repayment_preview"].suggested_interest_amount,
            Decimal("100.00"),
        )
        self.assertEqual(
            response.context_data["form"].initial["interest_amount"],
            Decimal("100.00"),
        )
        self.assertEqual(
            [option["label"] for option in response.context_data["payment_options"]],
            ["Exact settlement", "Interest only", "Principal only"],
        )

    @patch("apps.tenant_apps.girvi.views.loanpayment.reverse", return_value="/girvi/loan/1/")
    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.warning")
    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.success")
    @patch("apps.tenant_apps.girvi.views.loanpayment.GivenLoanRepaymentService.execute")
    @patch("apps.tenant_apps.girvi.views.loanpayment.get_object_or_404")
    def test_repayment_create_posts_and_redirects(
        self,
        mock_get_object_or_404,
        mock_execute,
        mock_success,
        mock_warning,
        _mock_reverse,
    ):
        payment = MagicMock()
        payment.payment_id = "RCP-123"

        loan = MagicMock()
        loan.pk = 1
        loan.create_payment.return_value = payment
        loan.get_loan_amount = Decimal("1000.00")
        loan.outstanding_interest = Decimal("100.00")
        loan.get_total_principal_payments.return_value = Decimal("0.00")
        loan.get_total_interest_payments.return_value = Decimal("0.00")
        mock_get_object_or_404.return_value = loan
        mock_execute.return_value = SimpleNamespace(
            warnings=[],
            errors=[],
            success_message="Payment RCP-123 recorded and posted to accounting.",
        )

        request = self.factory.post(
            "/girvi/loanpayment/1/create/",
            data={
                "total_amount": "1000.00",
                "payment_date": "2026-03-23T10:30",
                "payment_method": "CASH",
                "reference_number": "REF-1",
                "interest_amount": "100.00",
                "description": "test",
                "is_final_payment": "on",
            },
        )
        request.user = self.user
        request.htmx = False

        response = loan_payment_create_view.__wrapped__(request, pk=1)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/girvi/loan/1/")
        mock_execute.assert_called_once()
        mock_success.assert_called_once()
        mock_warning.assert_not_called()

    @patch("apps.tenant_apps.girvi.views.loanpayment.reverse", return_value="/girvi/loan/1/")
    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.warning")
    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.success")
    @patch("apps.tenant_apps.girvi.views.loanpayment.GivenLoanRepaymentService.execute")
    @patch("apps.tenant_apps.girvi.views.loanpayment.get_object_or_404")
    def test_repayment_ignores_create_release_payload_key(
        self,
        mock_get_object_or_404,
        mock_execute,
        mock_success,
        mock_warning,
        _mock_reverse,
    ):
        payment = MagicMock()
        payment.payment_id = "RCP-124"

        loan = MagicMock()
        loan.pk = 1
        loan.create_payment.return_value = payment
        loan.get_loan_amount = Decimal("1000.00")
        loan.outstanding_interest = Decimal("100.00")
        loan.get_total_principal_payments.return_value = Decimal("0.00")
        loan.get_total_interest_payments.return_value = Decimal("0.00")
        mock_get_object_or_404.return_value = loan
        mock_execute.return_value = SimpleNamespace(
            warnings=[],
            errors=[],
            success_message="Payment RCP-124 recorded and posted to accounting.",
        )

        request = self.factory.post(
            "/girvi/loanpayment/1/create/",
            data={
                "total_amount": "1000.00",
                "payment_date": "2026-03-23T10:30",
                "payment_method": "CASH",
                "reference_number": "REF-1",
                "interest_amount": "100.00",
                "description": "test",
                "is_final_payment": "on",
                "create_release": "on",
            },
        )
        request.user = self.user
        request.htmx = False

        response = loan_payment_create_view.__wrapped__(request, pk=1)

        self.assertIsInstance(response, HttpResponseRedirect)
        command = mock_execute.call_args.args[0]
        self.assertNotIn("create_release", command.cleaned_data)
        mock_success.assert_called_once()
        mock_warning.assert_not_called()

    @patch("apps.tenant_apps.girvi.views.loanpayment.reverse", return_value="/girvi/loan/1/")
    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.success")
    @patch("apps.tenant_apps.girvi.views.loanpayment.GivenLoanRepaymentService.execute")
    @patch("apps.tenant_apps.girvi.views.loanpayment.get_object_or_404")
    def test_repeated_post_forwards_the_same_browser_idempotency_key(
        self,
        mock_get_object_or_404,
        mock_execute,
        _mock_success,
        _mock_reverse,
    ):
        loan = MagicMock(pk=1)
        loan.get_loan_amount = Decimal("1000.00")
        loan.outstanding_interest = Decimal("100.00")
        loan.get_total_principal_payments.return_value = Decimal("0.00")
        loan.get_total_interest_payments.return_value = Decimal("0.00")
        mock_get_object_or_404.return_value = loan
        mock_execute.return_value = SimpleNamespace(
            warnings=[],
            errors=[],
            success_message="Payment already recorded and posted to accounting.",
        )
        post_data = {
            "total_amount": "100.00",
            "payment_date": "2026-03-23T10:30",
            "payment_method": "CASH",
            "reference_number": "",
            "idempotency_key": "browser-submit-1",
            "interest_amount": "20.00",
            "description": "test",
        }

        for _attempt in range(2):
            request = self.factory.post(
                "/girvi/loanpayment/1/create/",
                data=post_data,
            )
            request.user = self.user
            request.htmx = False
            loan_payment_create_view.__wrapped__(request, pk=1)

        self.assertEqual(mock_execute.call_count, 2)
        submitted_keys = [
            call.args[0].cleaned_data["idempotency_key"]
            for call in mock_execute.call_args_list
        ]
        self.assertEqual(submitted_keys, ["browser-submit-1", "browser-submit-1"])


class PR3TakenLoanRepaymentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.success")
    @patch("apps.tenant_apps.girvi.views.loanpayment.TakenLoanRepaymentService.execute")
    @patch("apps.tenant_apps.girvi.views.loanpayment.get_object_or_404")
    def test_takenloan_repayment_create_posts_and_redirects(
        self,
        mock_get_object_or_404,
        mock_execute,
        mock_success,
    ):
        payment = MagicMock()
        payment.payment_id = "PAY-123"
        payment.get_voucher_type.return_value = "TAKENLOAN_PAYMENT"

        loan = MagicMock()
        loan.create_payment.return_value = payment
        loan.get_absolute_url.return_value = "/girvi/custody/taken-loans/2/collateral/"
        loan.pk = 2
        loan.get_loan_amount = Decimal("800.00")
        loan.outstanding_interest = Decimal("80.00")
        loan.get_total_principal_payments.return_value = Decimal("0.00")
        loan.get_total_interest_payments.return_value = Decimal("0.00")
        mock_get_object_or_404.return_value = loan
        mock_execute.return_value = SimpleNamespace(
            warnings=[],
            errors=[],
            success_message="Payment PAY-123 recorded and posted to accounting.",
        )

        request = self.factory.post(
            "/girvi/takenloan/2/payment/create/",
            data={
                "total_amount": "800.00",
                "payment_date": "2026-03-23T10:30",
                "payment_method": "BANK",
                "reference_number": "BANK-1",
                "interest_amount": "80.00",
                "description": "taken loan repayment",
                "is_final_payment": "on",
            },
        )
        request.user = self.user
        request.htmx = False

        from apps.tenant_apps.girvi.views.loanpayment import taken_loan_payment_create_view

        response = taken_loan_payment_create_view.__wrapped__(request, pk=2)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/girvi/custody/taken-loans/2/collateral/")
        mock_execute.assert_called_once()
        mock_success.assert_called_once()


class PR2DisbursalServiceTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.service_modules.payment.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.service_modules.payment.ContentType")
    def test_disbursal_service_returns_existing_without_posting(
        self,
        mock_content_type,
        mock_payment_voucher,
    ):
        existing = MagicMock(payment_id="RCP-EXIST")
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = existing

        with patch(
            "apps.tenant_apps.girvi.service_modules.payment.create_and_post_voucher_for_doc"
        ) as mock_post:
            FakeGivenLoan = type("FakeGivenLoan", (), {})
            FakeTakenLoan = type("FakeTakenLoan", (), {})
            loan = FakeGivenLoan()
            loan.pk = 10
            loan.loan_id = "GL-10"
            loan.loan_date = "2026-03-23"
            loan.get_loan_amount_with_currency = "1000 INR"
            loan.borrower = SimpleNamespace(customer_type="R")
            mock_post.return_value = (existing, False)
            with patch(
                "apps.tenant_apps.girvi.service_modules.payment.GivenLoan", new=FakeGivenLoan
            ), patch(
                "apps.tenant_apps.girvi.service_modules.payment.TakenLoan", new=FakeTakenLoan
            ), patch(
                "apps.tenant_apps.girvi.service_modules.payment.resolve_customer_account"
            ) as mock_resolve_account:
                result, created = record_loan_disbursal(loan, user=SimpleNamespace(id=1))

        self.assertEqual(result, existing)
        self.assertFalse(created)
        mock_resolve_account.assert_called_once_with(
            loan.borrower,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
        )
        mock_post.assert_called_once()

    @patch("apps.tenant_apps.girvi.service_modules.payment.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.service_modules.payment.ContentType")
    @patch("apps.tenant_apps.girvi.service_modules.payment.create_and_post_voucher_for_doc")
    def test_disbursal_service_creates_and_posts_givenloan_voucher(
        self,
        mock_post,
        mock_content_type,
        mock_payment_voucher,
    ):
        FakeGivenLoan = type("FakeGivenLoan", (), {})
        FakeTakenLoan = type("FakeTakenLoan", (), {})
        loan = FakeGivenLoan()
        loan.pk = 11
        loan.loan_id = "GL-11"
        loan.loan_date = "2026-03-23"
        loan.get_loan_amount_with_currency = "1000 INR"
        loan.borrower = SimpleNamespace(customer_type="R")

        created_payment = MagicMock()
        created_payment.get_voucher_type.return_value = "GIVENLOAN_PAYMENT"
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = None
        mock_payment_voucher.objects.create.return_value = created_payment
        mock_post.return_value = (created_payment, True)

        with patch(
            "apps.tenant_apps.girvi.service_modules.payment.GivenLoan", new=FakeGivenLoan
        ), patch(
            "apps.tenant_apps.girvi.service_modules.payment.TakenLoan", new=FakeTakenLoan
        ), patch(
            "apps.tenant_apps.girvi.service_modules.payment.resolve_customer_account"
        ) as mock_resolve_account:
            result, created = record_loan_disbursal(loan, user=SimpleNamespace(id=1))

        self.assertEqual(result, created_payment)
        self.assertTrue(created)
        mock_resolve_account.assert_called_once_with(
            loan.borrower,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
        )
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["direction"], "PAYMENT")
        self.assertEqual(call_kwargs["payment_type"], "DISBURSAL")

    @patch("apps.tenant_apps.girvi.service_modules.payment.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.service_modules.payment.ContentType")
    @patch("apps.tenant_apps.girvi.service_modules.payment.create_and_post_voucher_for_doc")
    def test_givenloan_disbursal_posts_net_payout_with_explicit_components(
        self,
        mock_post,
        mock_content_type,
        mock_payment_voucher,
    ):
        FakeGivenLoan = type("FakeGivenLoan", (), {})
        FakeTakenLoan = type("FakeTakenLoan", (), {})
        loan = FakeGivenLoan()
        loan.pk = 13
        loan.loan_id = "GL-13"
        loan.loan_date = "2026-03-23"
        loan.get_loan_amount_with_currency = "1000"
        loan.disbursal_upfront_interest_deduction = Decimal("100.00")
        loan.disbursal_document_charge = Decimal("25.00")
        loan.borrower = SimpleNamespace(customer_type="R")

        created_payment = MagicMock()
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = None
        mock_post.return_value = (created_payment, True)

        with patch(
            "apps.tenant_apps.girvi.service_modules.payment.GivenLoan", new=FakeGivenLoan
        ), patch(
            "apps.tenant_apps.girvi.service_modules.payment.TakenLoan", new=FakeTakenLoan
        ), patch(
            "apps.tenant_apps.girvi.service_modules.payment.resolve_customer_account"
        ):
            record_loan_disbursal(loan, user=SimpleNamespace(id=1))

        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["total_amount"].amount, Decimal("875.00"))
        self.assertEqual(call_kwargs["principal_amount"].amount, Decimal("1000.00"))
        self.assertEqual(call_kwargs["interest_amount"].amount, Decimal("100.00"))
        self.assertEqual(call_kwargs["fee_amount"].amount, Decimal("25.00"))

    @patch("apps.tenant_apps.girvi.service_modules.payment.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.service_modules.payment.ContentType")
    @patch("apps.tenant_apps.girvi.service_modules.payment.create_and_post_voucher_for_doc")
    def test_disbursal_service_creates_takenloan_disbursal_receipt(
        self,
        mock_post,
        mock_content_type,
        mock_payment_voucher,
    ):
        FakeGivenLoan = type("FakeGivenLoan", (), {})
        FakeTakenLoan = type("FakeTakenLoan", (), {})
        loan = FakeTakenLoan()
        loan.pk = 12
        loan.loan_id = "TL-12"
        loan.loan_date = "2026-03-23"
        loan.get_loan_amount_with_currency = "1500 INR"
        loan.lender = SimpleNamespace(customer_type="W")

        created_payment = MagicMock()
        created_payment.get_voucher_type.return_value = "TAKENLOAN_RECEIPT"
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = None
        mock_payment_voucher.objects.create.return_value = created_payment
        mock_post.return_value = (created_payment, True)

        with patch(
            "apps.tenant_apps.girvi.service_modules.payment.GivenLoan", new=FakeGivenLoan
        ), patch(
            "apps.tenant_apps.girvi.service_modules.payment.TakenLoan", new=FakeTakenLoan
        ), patch(
            "apps.tenant_apps.girvi.service_modules.payment.resolve_customer_account"
        ) as mock_resolve_account:
            result, created = record_loan_disbursal(loan, user=SimpleNamespace(id=1))

        self.assertEqual(result, created_payment)
        self.assertTrue(created)
        mock_resolve_account.assert_called_once_with(
            loan.lender,
            role_key="LENDER",
            purpose="LENDER_LOAN_PAYABLE",
        )
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args.kwargs
        self.assertEqual(call_kwargs["direction"], "RECEIPT")
        self.assertEqual(call_kwargs["payment_type"], "DISBURSAL")


class PR2TransitionHookTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True, username="tester")
        self.tenant = SimpleNamespace(schema_name="tenant1", owner=self.user)

    def test_request_closure_form_renders_plain_cancel_link(self):
        loan = SimpleNamespace(
            pk=1,
            status="ActiveCurrent",
            loan_id="GL-001",
            borrower=SimpleNamespace(name="Tester"),
            loan_date=date(2026, 4, 4),
            get_loan_amount=1000,
            get_absolute_url=lambda: "/girvi/loan/1/",
        )

        content = render_to_string(
            "girvi/loan/_transition_form_inner.html",
            {
                "form": RequestClosureLoanForm(user=self.user),
                "loan": loan,
                "transition_name": "request_closure",
                "transition_ui": get_transition_form_ui("request_closure"),
            },
        )

        self.assertIn('href="/girvi/loan/1/"', content)
        self.assertNotIn('hx-get="/girvi/loan/1/"', content)

    @patch("apps.tenant_apps.girvi.views.loan.redirect", side_effect=lambda url: HttpResponseRedirect(url))
    @patch("apps.tenant_apps.girvi.views.loan.messages.success")
    @patch("apps.tenant_apps.girvi.views.loan.get_object_or_404")
    @patch("apps.tenant_apps.girvi.views.loan.LoanTransitionService")
    def test_loan_transition_disburse_delegates_to_transition_service(
        self,
        mock_service_cls,
        mock_get_object_or_404,
        _mock_success,
        _mock_redirect,
    ):
        loan = MagicMock()
        loan.pk = 1
        loan.status = LoanStatus.APPROVED
        loan.get_absolute_url.return_value = "/girvi/loan/1/"
        mock_get_object_or_404.return_value = loan

        service = mock_service_cls.return_value
        service.execute.return_value = SimpleNamespace(
            success=True,
            level="success",
            message="ok",
        )

        request = self.factory.post(
            "/girvi/loan/1/transition/",
            data={"transition": "disburse_loan", "disbursed_by": "Tester"},
        )
        request.user = self.user
        request.tenant = self.tenant

        response = loan_transition_view(request, pk=1)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/girvi/loan/1/")
        mock_service_cls.assert_called_once_with(loan, self.user, self.tenant)
        service.execute.assert_called_once_with("disburse_loan", disbursed_by="Tester")


class CustodySummaryViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True, username="tester")

    @patch("apps.tenant_apps.girvi.views.custody_views.render")
    @patch("apps.tenant_apps.girvi.views.custody_views.get_object_or_404")
    def test_loan_custody_summary_uses_htmx_partial_template(
        self,
        mock_get_object_or_404,
        mock_render,
    ):
        loan = SimpleNamespace(
            loan_id="GL-001",
            can_release=lambda: (True, ""),
            loanitems=SimpleNamespace(
                all=lambda: [],
                count=lambda: 0,
                filter=lambda **kwargs: [],
            ),
        )
        mock_get_object_or_404.return_value = loan
        mock_render.return_value = HttpResponseRedirect("/ok/")

        request = self.factory.get("/girvi/loans/1/custody/")
        request.user = self.user
        request.tenant = SimpleNamespace(schema_name="tenant1", owner=self.user)
        request.htmx = True

        response = loan_custody_summary(request, loan_id=1)

        self.assertEqual(response.url, "/ok/")
        self.assertEqual(
            mock_render.call_args.args[1],
            "girvi/loan_custody_summary.html#custody-summary-content",
        )


class PrintLoanViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True, username="tester")

    @patch("apps.tenant_apps.girvi.views.prints.get_custom_jcl", return_value=b"%PDF-1.4 test")
    @patch("apps.tenant_apps.girvi.views.prints.LoanTemplate")
    @patch("apps.tenant_apps.girvi.views.prints.get_object_or_404")
    @patch("apps.tenant_apps.girvi.views.prints.GivenLoan")
    def test_print_loan_prefetches_customer_contact_relations_with_current_related_names(
        self,
        mock_givenloan,
        mock_get_object_or_404,
        mock_template,
        _mock_get_custom_jcl,
    ):
        mock_queryset = MagicMock(name="givenloan_queryset")
        mock_givenloan.objects.select_related.return_value = mock_queryset

        loan = SimpleNamespace(pk=1, loan_id="GL-001")
        mock_get_object_or_404.return_value = loan
        mock_template.objects.get_default.return_value = SimpleNamespace(pk=99)

        request = self.factory.get("/girvi/girvi/loan/detail/1/pdf")
        request.user = self.user

        response = print_loan.__wrapped__(request, pk=1)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        mock_queryset.prefetch_related.assert_called_once_with(
            "loanitems",
            "borrower__address",
            "borrower__contactno",
        )


class PR4ReleaseServiceTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.service_modules.payment.GivenLoanPostingService")
    def test_release_service_returns_existing_without_posting(
        self,
        mock_posting_service_cls,
    ):
        existing = MagicMock(payment_id="REL-EXIST")
        user = SimpleNamespace(id=1)
        release = SimpleNamespace(pk=31, release_id="REL-31")
        mock_posting_service_cls.return_value.post_release.return_value = (
            existing,
            False,
        )

        result, created = record_loan_release(release, created_by=user)

        self.assertEqual(result, existing)
        self.assertFalse(created)
        mock_posting_service_cls.return_value.post_release.assert_called_once_with(
            release,
            user,
        )

    @patch("apps.tenant_apps.girvi.service_modules.payment.GivenLoanPostingService")
    def test_release_service_creates_and_posts_for_positive_outstanding(
        self,
        mock_posting_service_cls,
    ):
        created_payment = MagicMock()
        user = SimpleNamespace(id=1)
        release = SimpleNamespace(pk=32, release_id="REL-32")
        mock_posting_service_cls.return_value.post_release.return_value = (
            created_payment,
            True,
        )

        result, created = record_loan_release(release, created_by=user)

        self.assertEqual(result, created_payment)
        self.assertTrue(created)
        mock_posting_service_cls.return_value.post_release.assert_called_once_with(
            release,
            user,
        )

    @patch("apps.tenant_apps.girvi.service_modules.payment.GivenLoanPostingService")
    def test_release_service_skips_when_no_outstanding(
        self,
        mock_posting_service_cls,
    ):
        user = SimpleNamespace(id=1)
        release = SimpleNamespace(pk=33, release_id="REL-33")
        mock_posting_service_cls.return_value.post_release.return_value = (None, False)

        result, created = record_loan_release(release, created_by=user)

        self.assertIsNone(result)
        self.assertFalse(created)
        mock_posting_service_cls.return_value.post_release.assert_called_once_with(
            release,
            user,
        )
