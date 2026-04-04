from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from moneyed import Money

from apps.tenant_apps.dea.models.payment import PaymentVoucher
from apps.tenant_apps.girvi.forms import GivenLoanRepaymentForm, RequestClosureLoanForm
from apps.tenant_apps.girvi.transition_registry import get_transition_form_ui
from apps.tenant_apps.girvi.models.loan_refactored import LoanStatus
from apps.tenant_apps.girvi.payment_service import (
    record_loan_disbursal,
    record_loan_release,
)
from apps.tenant_apps.girvi.views.loan import loan_transition_view
from apps.tenant_apps.girvi.views.loanpayment import loan_payment_create_view


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


class PR1RepaymentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.loanpayment.reverse", return_value="/girvi/loan/1/")
    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.success")
    @patch("apps.tenant_apps.girvi.views.loanpayment.create_and_post_voucher_for_doc")
    @patch("apps.tenant_apps.girvi.views.loanpayment.get_object_or_404")
    def test_repayment_create_posts_and_redirects(
        self,
        mock_get_object_or_404,
        mock_create_and_post,
        mock_success,
        _mock_reverse,
    ):
        payment = MagicMock()
        payment.payment_id = "RCP-123"
        payment.get_voucher_type.return_value = "GIVENLOAN_RECEIPT"

        loan = MagicMock()
        loan.pk = 1
        loan.create_payment.return_value = payment
        mock_get_object_or_404.return_value = loan

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
        self.assertEqual(response.url, "/girvi/loan/1/")
        mock_create_and_post.assert_called_once()
        payment.save.assert_called_once_with(update_fields=["posted"])
        mock_success.assert_called_once()


class PR3TakenLoanRepaymentViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True)

    @patch("apps.tenant_apps.girvi.views.loanpayment.messages.success")
    @patch("apps.tenant_apps.girvi.views.loanpayment.create_and_post_voucher_for_doc")
    @patch("apps.tenant_apps.girvi.views.loanpayment.get_object_or_404")
    def test_takenloan_repayment_create_posts_and_redirects(
        self,
        mock_get_object_or_404,
        mock_create_and_post,
        mock_success,
    ):
        payment = MagicMock()
        payment.payment_id = "PAY-123"
        payment.get_voucher_type.return_value = "TAKENLOAN_PAYMENT"

        loan = MagicMock()
        loan.create_payment.return_value = payment
        loan.get_absolute_url.return_value = "/girvi/custody/taken-loans/2/collateral/"
        mock_get_object_or_404.return_value = loan

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
        mock_create_and_post.assert_called_once()
        payment.save.assert_called_once_with(update_fields=["posted"])
        mock_success.assert_called_once()


class PR2DisbursalServiceTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.payment_service.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.payment_service.ContentType")
    def test_disbursal_service_returns_existing_without_posting(
        self,
        mock_content_type,
        mock_payment_voucher,
    ):
        existing = MagicMock(payment_id="RCP-EXIST")
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = existing

        with patch(
            "apps.tenant_apps.girvi.payment_service.create_and_post_voucher_for_doc"
        ) as mock_post:
            FakeGivenLoan = type("FakeGivenLoan", (), {})
            FakeTakenLoan = type("FakeTakenLoan", (), {})
            loan = FakeGivenLoan()
            loan.pk = 10
            with patch(
                "apps.tenant_apps.girvi.payment_service.GivenLoan", new=FakeGivenLoan
            ), patch(
                "apps.tenant_apps.girvi.payment_service.TakenLoan", new=FakeTakenLoan
            ):
                result, created = record_loan_disbursal(loan, user=SimpleNamespace(id=1))

        self.assertEqual(result, existing)
        self.assertFalse(created)
        mock_post.assert_not_called()

    @patch("apps.tenant_apps.girvi.payment_service.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.payment_service.ContentType")
    @patch("apps.tenant_apps.girvi.payment_service.create_and_post_voucher_for_doc")
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

        created_payment = MagicMock()
        created_payment.get_voucher_type.return_value = "GIVENLOAN_PAYMENT"
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = None
        mock_payment_voucher.objects.create.return_value = created_payment

        with patch(
            "apps.tenant_apps.girvi.payment_service.GivenLoan", new=FakeGivenLoan
        ), patch(
            "apps.tenant_apps.girvi.payment_service.TakenLoan", new=FakeTakenLoan
        ):
            result, created = record_loan_disbursal(loan, user=SimpleNamespace(id=1))

        self.assertEqual(result, created_payment)
        self.assertTrue(created)
        mock_payment_voucher.objects.create.assert_called_once()
        mock_post.assert_called_once()
        created_payment.save.assert_called_once_with(update_fields=["posted"])

    @patch("apps.tenant_apps.girvi.payment_service.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.payment_service.ContentType")
    @patch("apps.tenant_apps.girvi.payment_service.create_and_post_voucher_for_doc")
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

        created_payment = MagicMock()
        created_payment.get_voucher_type.return_value = "TAKENLOAN_RECEIPT"
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = None
        mock_payment_voucher.objects.create.return_value = created_payment

        with patch(
            "apps.tenant_apps.girvi.payment_service.GivenLoan", new=FakeGivenLoan
        ), patch(
            "apps.tenant_apps.girvi.payment_service.TakenLoan", new=FakeTakenLoan
        ):
            result, created = record_loan_disbursal(loan, user=SimpleNamespace(id=1))

        self.assertEqual(result, created_payment)
        self.assertTrue(created)
        create_kwargs = mock_payment_voucher.objects.create.call_args.kwargs
        self.assertEqual(create_kwargs["direction"], "RECEIPT")
        self.assertEqual(create_kwargs["payment_type"], "DISBURSAL")
        mock_post.assert_called_once()


class PR2TransitionHookTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True, username="tester")
        self.tenant = SimpleNamespace()

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
    def test_loan_transition_view_canonicalizes_disburse_to_v2_for_approved_loan(
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
            data={"transition": "disburse", "disbursed_by": "Tester"},
        )
        request.user = self.user
        request.tenant = self.tenant

        response = loan_transition_view(request, pk=1)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/girvi/loan/1/")
        mock_service_cls.assert_called_once_with(loan, self.user, self.tenant)
        service.execute.assert_called_once_with(
            "disburse_loan",
            disbursed_by="Tester",
        )

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
            data={"transition": "disburse", "disbursed_by": "Tester"},
        )
        request.user = self.user
        request.tenant = self.tenant

        response = loan_transition_view(request, pk=1)

        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertEqual(response.url, "/girvi/loan/1/")
        mock_service_cls.assert_called_once_with(loan, self.user, self.tenant)
        service.execute.assert_called_once_with("disburse_loan", disbursed_by="Tester")


class PR4ReleaseServiceTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.payment_service.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.payment_service.ContentType")
    def test_release_service_returns_existing_without_posting(
        self,
        mock_content_type,
        mock_payment_voucher,
    ):
        existing = MagicMock(payment_id="REL-EXIST")
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = existing

        with patch(
            "apps.tenant_apps.girvi.payment_service.create_and_post_voucher_for_doc"
        ) as mock_post:
            FakeGivenLoan = type("FakeGivenLoan", (), {})
            loan = FakeGivenLoan()
            loan.pk = 20
            loan.outstanding_principal = Money(250, "INR")
            loan.interest_due = lambda: 0

            release = SimpleNamespace(
                pk=31,
                release_id="REL-31",
                release_date="2026-03-24",
                loan=loan,
            )

            with patch("apps.tenant_apps.girvi.payment_service.GivenLoan", new=FakeGivenLoan):
                result, created = record_loan_release(
                    release,
                    created_by=SimpleNamespace(id=1),
                )

        self.assertEqual(result, existing)
        self.assertFalse(created)
        mock_post.assert_not_called()

    @patch("apps.tenant_apps.girvi.payment_service.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.payment_service.ContentType")
    @patch("apps.tenant_apps.girvi.payment_service.create_and_post_voucher_for_doc")
    def test_release_service_creates_and_posts_for_positive_outstanding(
        self,
        mock_post,
        mock_content_type,
        mock_payment_voucher,
    ):
        FakeGivenLoan = type("FakeGivenLoan", (), {})
        loan = FakeGivenLoan()
        loan.pk = 21
        loan.loan_id = "GL-21"
        loan.outstanding_principal = Money(500, "INR")
        loan.interest_due = lambda: 25

        created_payment = MagicMock()
        mock_content_type.objects.get_for_model.return_value = object()
        mock_payment_voucher.objects.filter.return_value.first.return_value = None
        mock_payment_voucher.objects.create.return_value = created_payment

        release = SimpleNamespace(
            pk=32,
            release_id="REL-32",
            release_date="2026-03-24",
            loan=loan,
        )

        with patch("apps.tenant_apps.girvi.payment_service.GivenLoan", new=FakeGivenLoan):
            result, created = record_loan_release(
                release,
                created_by=SimpleNamespace(id=1),
            )

        self.assertEqual(result, created_payment)
        self.assertTrue(created)
        mock_payment_voucher.objects.create.assert_called_once()
        create_kwargs = mock_payment_voucher.objects.create.call_args.kwargs
        self.assertEqual(create_kwargs["direction"], "RECEIPT")
        self.assertEqual(create_kwargs["payment_type"], "RECEIPT")
        self.assertEqual(create_kwargs["reference_number"], "RELEASE-32")
        mock_post.assert_called_once()
        created_payment.save.assert_called_once_with(update_fields=["posted"])

    @patch("apps.tenant_apps.girvi.payment_service.PaymentVoucher")
    @patch("apps.tenant_apps.girvi.payment_service.ContentType")
    @patch("apps.tenant_apps.girvi.payment_service.create_and_post_voucher_for_doc")
    def test_release_service_skips_when_no_outstanding(
        self,
        mock_post,
        mock_content_type,
        mock_payment_voucher,
    ):
        FakeGivenLoan = type("FakeGivenLoan", (), {})
        loan = FakeGivenLoan()
        loan.pk = 22
        loan.loan_id = "GL-22"
        loan.outstanding_principal = Money(0, "INR")
        loan.interest_due = lambda: 0

        release = SimpleNamespace(
            pk=33,
            release_id="REL-33",
            release_date="2026-03-24",
            loan=loan,
        )

        with patch("apps.tenant_apps.girvi.payment_service.GivenLoan", new=FakeGivenLoan):
            result, created = record_loan_release(
                release,
                created_by=SimpleNamespace(id=1),
            )

        self.assertIsNone(result)
        self.assertFalse(created)
        mock_payment_voucher.objects.create.assert_not_called()
        mock_content_type.objects.get_for_model.assert_not_called()
        mock_post.assert_not_called()
