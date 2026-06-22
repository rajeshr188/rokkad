from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.selectors import build_loan_accounting_reconciliation_report


class LoanAccountingReconciliationSelectorTests(SimpleTestCase):
    def test_build_report_detects_expected_mismatch_categories(self):
        class FakePayments(list):
            def all(self):
                return self

        class FakePayment:
            def __init__(
                self,
                *,
                payment_id,
                posted,
                payment_type,
                direction,
                reference_number="",
                create_release=False,
                reversal_of_id=None,
                pk=1,
            ):
                self.payment_id = payment_id
                self.posted = posted
                self.payment_type = payment_type
                self.direction = direction
                self.reference_number = reference_number
                self.create_release = create_release
                self.reversal_of_id = reversal_of_id
                self.pk = pk

        loan_missing_disbursal = SimpleNamespace(
            pk=1,
            loan_id="GL-001",
            borrower=SimpleNamespace(name="Asha"),
            status="ActiveCurrent",
            payments=FakePayments([]),
        )
        loan_failed_posting = SimpleNamespace(
            pk=2,
            loan_id="GL-002",
            borrower=SimpleNamespace(name="Ravi"),
            status="Approved",
            payments=FakePayments(
                [
                    FakePayment(
                        payment_id="RCP-1",
                        posted=False,
                        payment_type="RECEIPT",
                        direction="RECEIPT",
                        pk=21,
                    )
                ]
            ),
        )
        loan_release_without_voucher = SimpleNamespace(
            pk=3,
            loan_id="GL-003",
            borrower=SimpleNamespace(name="Mina"),
            status="Closed",
            release=SimpleNamespace(pk=301),
            payments=FakePayments(
                [
                    FakePayment(
                        payment_id="DIS-3",
                        posted=True,
                        payment_type="DISBURSAL",
                        direction="PAYMENT",
                        pk=31,
                    )
                ]
            ),
        )
        loan_state_mismatch = SimpleNamespace(
            pk=4,
            loan_id="GL-004",
            borrower=SimpleNamespace(name="Kiran"),
            status="Draft",
            payments=FakePayments(
                [
                    FakePayment(
                        payment_id="DIS-4",
                        posted=True,
                        payment_type="DISBURSAL",
                        direction="PAYMENT",
                        pk=41,
                    )
                ]
            ),
        )

        report = build_loan_accounting_reconciliation_report(
            loans=[
                loan_missing_disbursal,
                loan_failed_posting,
                loan_release_without_voucher,
                loan_state_mismatch,
            ]
        )

        self.assertEqual(report["counts"]["missing_disbursal_voucher"], 1)
        self.assertEqual(report["counts"]["failed_payment_posting"], 1)
        self.assertEqual(report["counts"]["release_without_voucher"], 1)
        self.assertEqual(report["counts"]["posted_voucher_state_mismatch"], 1)
        self.assertEqual(report["total_issues"], 4)
