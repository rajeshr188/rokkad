from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.documents.release_forms import generate_form_h


class ReleaseFormDocumentTests(SimpleTestCase):
    @patch("apps.tenant_apps.girvi.documents.release_forms._build_settlement_balance")
    def test_generate_form_h_supports_refactored_loan_without_legacy_methods(
        self,
        mock_build_settlement_balance,
    ):
        mock_build_settlement_balance.return_value = SimpleNamespace(
            interest_due=Decimal("125.00"),
            total_outstanding=Decimal("1125.00"),
        )

        loan = SimpleNamespace(
            series=SimpleNamespace(
                license=SimpleNamespace(name="PBL-001", shopname="Demo Shop", address="Demo Address")
            ),
            loan_id="GL-001",
            loan_date=datetime(2026, 6, 1),
            loan_amount=Decimal("1000.00"),
        )
        release = SimpleNamespace(
            id=4,
            loan=loan,
            release_date=datetime(2026, 6, 27),
            released_by=SimpleNamespace(name="Demo Customer"),
        )

        pdf = generate_form_h(release)

        self.assertIsInstance(pdf, bytes)
        self.assertTrue(pdf.startswith(b"%PDF"))
        mock_build_settlement_balance.assert_called_once_with(loan)
