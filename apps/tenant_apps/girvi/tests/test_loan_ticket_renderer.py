from datetime import datetime
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.documents.loan_ticket import (
    build_loan_ticket_pdf,
    resolve_frame_value,
)


class LoanTicketRendererTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.documents.loan_ticket.LoanTemplate.objects.filter")
    def test_build_loan_ticket_pdf_supports_refactored_givenloan_api(
        self,
        mock_filter,
    ):
        frames = [
            SimpleNamespace(
                frame_name="pure",
                field_type="text",
                x_pos=1,
                y_pos=1,
                width=5,
                height=1,
                show_boundary=0,
                font_size=10,
                font_name="Helvetica",
            ),
            SimpleNamespace(
                frame_name="value",
                field_type="text",
                x_pos=1,
                y_pos=2.5,
                width=5,
                height=1,
                show_boundary=0,
                font_size=10,
                font_name="Helvetica",
            ),
        ]
        fake_template = SimpleNamespace(
            pk=1,
            print_option="O",
            base_template=None,
            dup_template=None,
            terms_template=None,
            form_d3_template=None,
            templateframe_set=SimpleNamespace(filter=lambda **kwargs: frames),
        )
        mock_filter.return_value.first.return_value = fake_template

        borrower = SimpleNamespace(
            name="Kiran",
            get_relatedas_display=lambda: "S/O",
            relatedto="Test",
            get_address=lambda: "Demo address",
            get_contactno=lambda: "9999999999",
            get_default_pic=lambda: None,
        )
        loan = SimpleNamespace(
            loan_id="GL-001",
            loan_date=datetime(2026, 4, 6, 18, 59, 0),
            loan_amount=1500,
            borrower=borrower,
            series=SimpleNamespace(
                license=SimpleNamespace(
                    name="LIC-1",
                    shopname="Demo Shop",
                    address="Demo Street",
                    propreitor="Owner",
                )
            ),
            loanitems=SimpleNamespace(all=lambda: [], first=lambda: None),
            formatted_pure_weight=lambda joiner=", ": "Gold 1.500g",
            current_value=2200,
        )

        pdf = build_loan_ticket_pdf(loan=loan, template_id=1)

        self.assertIsNotNone(pdf)
        self.assertTrue(pdf.startswith(b"%PDF"))

    @patch("apps.tenant_apps.girvi.documents.loan_ticket.LoanTemplate.objects.filter")
    def test_build_loan_ticket_pdf_supports_side_by_side_a4_output_without_assets(
        self,
        mock_filter,
    ):
        frames = [
            SimpleNamespace(
                frame_name="loan_id",
                field_type="text",
                x_pos=1,
                y_pos=1,
                width=5,
                height=1,
                show_boundary=0,
                font_size=10,
                font_name="Helvetica",
            ),
        ]
        fake_template = SimpleNamespace(
            pk=2,
            print_option="BA",
            base_template=None,
            dup_template=None,
            terms_template=None,
            form_d3_template=None,
            templateframe_set=SimpleNamespace(filter=lambda **kwargs: frames),
        )
        mock_filter.return_value.first.return_value = fake_template

        borrower = SimpleNamespace(
            name="Kiran",
            get_relatedas_display=lambda: "S/O",
            relatedto="Test",
            get_address=lambda: "Demo address",
            get_contactno=lambda: "9999999999",
            get_default_pic=lambda: None,
        )
        loan = SimpleNamespace(
            loan_id="GL-002",
            loan_date=datetime(2026, 4, 6, 18, 59, 0),
            loan_amount=1750,
            borrower=borrower,
            series=SimpleNamespace(
                license=SimpleNamespace(
                    license_number="LIC-1",
                    shopname="Demo Shop",
                    address="Demo Street",
                    propreitor="Owner",
                )
            ),
            loanitems=SimpleNamespace(all=lambda: [], first=lambda: None),
            formatted_pure_weight=lambda joiner=", ": "Gold 1.500g",
            current_value=2200,
        )

        pdf = build_loan_ticket_pdf(loan=loan, template_id=2)

        self.assertIsNotNone(pdf)
        self.assertTrue(pdf.startswith(b"%PDF"))

    def test_resolve_frame_value_uses_registry_and_unknown_fields_fall_back_to_none(self):
        party = SimpleNamespace(
            name="Kiran",
            get_relatedas_display=lambda: "S/O",
            relatedto="Test",
            get_address=lambda: "Demo address",
            get_contactno=lambda: "9999999999",
            get_default_pic=lambda: None,
        )
        loan = SimpleNamespace(
            loan_id="GL-003",
            loan_date=datetime(2026, 4, 6, 18, 59, 0),
            loan_amount=2100,
            borrower=party,
            series=SimpleNamespace(
                license=SimpleNamespace(
                    license_number="LIC-1",
                    shopname="Demo Shop",
                    address="Demo Street",
                    propreitor="Owner",
                )
            ),
            loanitems=SimpleNamespace(all=lambda: [], first=lambda: None),
            formatted_pure_weight=lambda joiner=", ": "Gold 1.500g",
            current_value=2200,
        )

        self.assertEqual(resolve_frame_value("loan_id", loan, party), "GL-003")
        self.assertEqual(resolve_frame_value("amount", loan, party), "2100")
        self.assertIsNone(resolve_frame_value("unknown_field", loan, party))
