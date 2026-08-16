from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.party.portal_selectors import _portal_loan_payment_row


class PortalLoanPaymentRowTests(SimpleTestCase):
    def test_builds_amount_from_canonical_repayment_components(self):
        row = _portal_loan_payment_row(
            SimpleNamespace(
                pk=17,
                effective_date=date(2026, 8, 16),
                payload={
                    "currency": "INR",
                    "values": {
                        "principal": "100.00",
                        "interest": "12.50",
                        "fees": "2.50",
                    },
                },
            )
        )

        self.assertEqual(row.payment_id, "PAWN-17")
        self.assertEqual(row.payment_date, date(2026, 8, 16))
        self.assertEqual(row.total_amount.amount, Decimal("115.00"))
        self.assertEqual(row.total_amount.currency.code, "INR")
