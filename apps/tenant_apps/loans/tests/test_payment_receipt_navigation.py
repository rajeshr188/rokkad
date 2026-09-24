from datetime import date
from types import SimpleNamespace

from django.template.loader import render_to_string
from django.test import SimpleTestCase
from django.urls import reverse


class PaymentReceiptNavigationTests(SimpleTestCase):
    def test_receipts_keep_the_source_event_and_reversal_status(self):
        rows = [
            {"event": SimpleNamespace(pk=31, effective_date=date(2026, 9, 24)), "reversed_event": None},
            {"event": SimpleNamespace(pk=30, effective_date=date(2026, 9, 23)), "reversed_event": object()},
        ]
        html = render_to_string("loans/pawn/_payment_receipts.html", {
            "request": SimpleNamespace(workspace=SimpleNamespace(slug="receipt-test")),
            "loan": SimpleNamespace(pk=7), "repayment_rows": rows,
        })
        for event_id in (31, 30):
            self.assertIn(reverse("workspace_loans:pawn_repayment_receipt_pdf", args=["receipt-test", 7, event_id]), html)
        self.assertIn("this payment was reversed", html)
        self.assertIn("24 Sep 2026", html)
        self.assertEqual(html.count("Print payment receipt"), 2)

    def test_no_receipts_section_without_a_payment(self):
        self.assertEqual(render_to_string("loans/pawn/_payment_receipts.html", {"repayment_rows": []}).strip(), "")
