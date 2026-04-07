from types import SimpleNamespace
from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.printing import LoanPrintService


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
