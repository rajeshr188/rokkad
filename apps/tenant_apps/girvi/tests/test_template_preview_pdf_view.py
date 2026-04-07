from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.test import RequestFactory, SimpleTestCase

from apps.tenant_apps.girvi.views.template import template_preview_pdf


class TemplatePreviewPdfViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.user = SimpleNamespace(id=1, is_authenticated=True, username="tester")

    @patch("apps.tenant_apps.girvi.views.template.messages.warning")
    @patch("apps.tenant_apps.girvi.views.template.get_object_or_404")
    @patch("apps.tenant_apps.girvi.views.template.GivenLoan")
    @patch("apps.tenant_apps.girvi.views.template._require_template_admin")
    def test_template_preview_pdf_redirects_when_no_sample_loan_exists(
        self,
        mock_require_admin,
        mock_givenloan,
        mock_get_object_or_404,
        mock_warning,
    ):
        mock_require_admin.return_value = object()
        template_obj = SimpleNamespace(
            pk=7,
            name="Demo Template",
            get_absolute_url=lambda: "/girvi/templates/7/",
        )
        mock_get_object_or_404.return_value = template_obj

        mock_queryset = MagicMock(name="givenloan_queryset")
        mock_givenloan.objects.select_related.return_value = mock_queryset
        mock_queryset.prefetch_related.return_value = mock_queryset
        mock_queryset.order_by.return_value.first.return_value = None

        request = self.factory.get("/girvi/templates/7/preview-pdf/")
        request.user = self.user

        response = template_preview_pdf.__wrapped__(request, pk=7)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, "/girvi/templates/7/")
        mock_warning.assert_called_once()

    @patch("apps.tenant_apps.girvi.views.template.get_object_or_404")
    @patch("apps.tenant_apps.girvi.views.template.LoanPrintService.render_loan_ticket")
    @patch("apps.tenant_apps.girvi.views.template.GivenLoan")
    @patch("apps.tenant_apps.girvi.views.template._require_template_admin")
    def test_template_preview_pdf_returns_inline_pdf_for_sample_loan(
        self,
        mock_require_admin,
        mock_givenloan,
        mock_render_loan_ticket,
        mock_get_object_or_404,
    ):
        mock_require_admin.return_value = object()
        template_obj = SimpleNamespace(
            pk=7,
            name="Demo Template",
            get_absolute_url=lambda: "/girvi/templates/7/",
        )
        loan = SimpleNamespace(pk=11, loan_id="GL-PREVIEW-001")
        mock_get_object_or_404.return_value = template_obj

        mock_queryset = MagicMock(name="givenloan_queryset")
        mock_givenloan.objects.select_related.return_value = mock_queryset
        mock_queryset.prefetch_related.return_value = mock_queryset
        mock_queryset.order_by.return_value.first.return_value = loan

        mock_render_loan_ticket.return_value = (template_obj, b"%PDF-1.4 preview")

        request = self.factory.get("/girvi/templates/7/preview-pdf/")
        request.user = self.user

        response = template_preview_pdf.__wrapped__(request, pk=7)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("GL-PREVIEW-001", response["Content-Disposition"])
