from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.printing import (
    GirviDocumentResult,
    GirviDocumentService,
    LoanPrintService,
)


class LoanPrintServiceOrchestrationTests(SimpleTestCase):
    def _template(self):
        frames = [
            SimpleNamespace(frame_name="loan_id"),
            SimpleNamespace(frame_name="loan_date"),
            SimpleNamespace(frame_name="customer_info"),
            SimpleNamespace(frame_name="loan_desc"),
            SimpleNamespace(frame_name="amount"),
            SimpleNamespace(frame_name="amount_words"),
            SimpleNamespace(frame_name="loan_qr"),
        ]
        return SimpleNamespace(
            pk=5,
            name="Demo Template",
            is_active=True,
            print_option="O",
            base_template=None,
            dup_template=None,
            terms_template=None,
            form_d3_template=None,
            page_width=14.8,
            page_height=21.0,
            templateframe_set=SimpleNamespace(all=lambda: frames),
        )

    def test_build_print_result_uses_injected_template_resolver_and_renderer(self):
        loan = SimpleNamespace(loan_id="GL-001")
        template = self._template()
        template_resolver = Mock(return_value=template)
        renderer = Mock(return_value=b"%PDF-1.4 test")

        result = LoanPrintService.build_print_result(
            loan,
            template_resolver=template_resolver,
            renderer=renderer,
        )

        self.assertTrue(result.ok)
        self.assertIs(result.template, template)
        self.assertEqual(result.pdf, b"%PDF-1.4 test")
        template_resolver.assert_called_once_with()
        renderer.assert_called_once_with(loan=loan, template_id=template.pk)

    def test_build_print_result_returns_error_message_when_renderer_fails(self):
        loan = SimpleNamespace(loan_id="GL-002")
        template = self._template()

        result = LoanPrintService.build_print_result(
            loan,
            template=template,
            renderer=Mock(return_value=None),
        )

        self.assertFalse(result.ok)
        self.assertIs(result.template, template)
        self.assertIsNone(result.pdf)
        self.assertTrue(result.error_message)
        self.assertIsInstance(result.readiness, dict)


class GirviDocumentServiceTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.service_modules.printing.LoanPrintService.build_print_result")
    def test_render_loan_ticket_adapts_print_result(self, mock_build_print_result):
        mock_build_print_result.return_value = SimpleNamespace(
            pdf=b"%PDF-1.4 loan",
            error_message="",
        )
        loan = SimpleNamespace(loan_id="GL-123")

        result = GirviDocumentService.render_loan_ticket(loan)

        self.assertTrue(result.ok)
        self.assertEqual(result.document_type, "loan_ticket")
        self.assertEqual(result.file_name, "loan_ticket_GL-123.pdf")

    @patch("apps.tenant_apps.girvi.service_modules.printing.generate_form_h")
    def test_render_release_form_h_uses_document_generator(self, mock_generate_form_h):
        mock_generate_form_h.return_value = b"%PDF-1.4 form-h"
        release = SimpleNamespace(pk=42)

        result = GirviDocumentService.render_release_form_h(release)

        self.assertTrue(result.ok)
        self.assertEqual(result.document_type, "release_form_h")
        self.assertEqual(result.file_name, "form_h_42.pdf")

    @patch("apps.tenant_apps.girvi.service_modules.printing.generate_payment_receipt_pdf")
    def test_render_payment_receipt_uses_document_generator(self, mock_generate_receipt):
        mock_generate_receipt.return_value = b"%PDF-1.4 receipt"
        payment = SimpleNamespace(pk=7, payment_id="PAY-007")

        result = GirviDocumentService.render_payment_receipt(payment)

        self.assertTrue(result.ok)
        self.assertEqual(result.document_type, "payment_receipt")
        self.assertEqual(result.file_name, "payment_receipt_PAY-007.pdf")

    def test_build_pdf_response_sets_content_headers(self):
        result = GirviDocumentResult(
            document_type="payment_receipt",
            file_name="payment_receipt_PAY-008.pdf",
            pdf=b"%PDF-1.4 data",
        )

        response = GirviDocumentService.build_pdf_response(result)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn('filename="payment_receipt_PAY-008.pdf"', response["Content-Disposition"])
