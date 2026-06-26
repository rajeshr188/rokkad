from datetime import datetime
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from apps.tenant_apps.girvi.service_modules.loan_workflow import LoanWorkflowService


class LoanWorkflowServiceTests(SimpleTestCase):
    def test_parse_preview_loan_date_accepts_datetime(self):
        now = datetime.now()
        self.assertEqual(LoanWorkflowService.parse_preview_loan_date(now), now)

    def test_build_preview_initial_item_inputs_skips_blank_rows(self):
        data = {
            "items-TOTAL_FORMS": "2",
            "items-0-itemdesc": "Ring",
            "items-0-itemtype": "Gold",
            "items-0-quantity": "1",
            "items-0-weight": "10",
            "items-0-purity": "75",
            "items-0-loanamount": "1000",
            "items-0-interestrate": "2",
            "items-1-itemdesc": "",
            "items-1-weight": "",
            "items-1-loanamount": "",
        }

        rows = LoanWorkflowService.build_preview_initial_item_inputs(data)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].itemdesc, "Ring")

    def test_extract_initial_item_inputs_skips_deleted_rows(self):
        formset = SimpleNamespace(
            cleaned_data=[
                {"DELETE": True, "itemdesc": "A"},
                {
                    "itemdesc": "B",
                    "itemtype": "Gold",
                    "quantity": 1,
                    "weight": 5,
                    "purity": 75,
                    "loanamount": 100,
                    "interestrate": 2,
                },
            ]
        )

        rows = LoanWorkflowService.extract_initial_item_inputs(formset)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].itemdesc, "B")

    @patch("apps.tenant_apps.girvi.service_modules.loan_workflow.ensure_party_customer")
    def test_build_loan_create_command_uses_bridge_customer(self, bridge_mock):
        borrower_party = SimpleNamespace(id=9)
        customer = SimpleNamespace(id=4)
        bridge_mock.return_value = {"customer": customer}
        form = SimpleNamespace(
            cleaned_data={
                "borrower_party": borrower_party,
                "series": SimpleNamespace(id=1),
                "loan_date": datetime.now(),
                "tenure": 3,
                "interest_type": "Simple",
                "loan_id": "A001",
            }
        )

        command = LoanWorkflowService.build_loan_create_command(form, user=SimpleNamespace())

        self.assertEqual(command.borrower, customer)
        self.assertEqual(command.borrower_party, borrower_party)

    def test_persist_loan_update_requires_valid_form(self):
        form = SimpleNamespace(is_valid=MagicMock(return_value=False))

        with self.assertRaises(ValidationError):
            LoanWorkflowService.persist_loan_update(form, user=SimpleNamespace())
