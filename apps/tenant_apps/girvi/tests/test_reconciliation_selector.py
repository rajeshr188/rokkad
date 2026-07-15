from types import SimpleNamespace
from decimal import Decimal

from django.test import SimpleTestCase

from apps.tenant_apps.girvi.selectors import (
    ReconciliationDataUnavailableError,
    build_loan_accounting_reconciliation_report,
)


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
                interest_amount=0,
            ):
                self.payment_id = payment_id
                self.posted = posted
                self.payment_type = payment_type
                self.direction = direction
                self.reference_number = reference_number
                self.create_release = create_release
                self.reversal_of_id = reversal_of_id
                self.pk = pk
                self.interest_amount = interest_amount

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

    def test_build_report_detects_release_integrity_mismatches(self):
        class FakeRelated(list):
            def all(self):
                return self

        class FakePayment:
            def __init__(self, *, interest_amount):
                self.payment_id = "REL-PAY"
                self.posted = True
                self.payment_type = "RECEIPT"
                self.direction = "RECEIPT"
                self.reference_number = "RELEASE-1"
                self.create_release = True
                self.reversal_of_id = None
                self.pk = 1
                self.interest_amount = interest_amount

        closed_without_release = SimpleNamespace(
            pk=10,
            loan_id="GL-010",
            borrower=SimpleNamespace(name="Asha"),
            status="Closed",
            payments=FakeRelated([]),
            loanitems=FakeRelated([]),
        )
        custody_mismatch = SimpleNamespace(
            pk=11,
            loan_id="GL-011",
            borrower=SimpleNamespace(name="Ravi"),
            status="Closed",
            release=SimpleNamespace(pk=1101, settlement_interest_amount=Decimal("0.00")),
            payments=FakeRelated([FakePayment(interest_amount=Decimal("0.00"))]),
            loanitems=FakeRelated([SimpleNamespace(custody_status="in_vault")]),
        )
        interest_mismatch = SimpleNamespace(
            pk=12,
            loan_id="GL-012",
            borrower=SimpleNamespace(name="Mina"),
            status="Closed",
            release=SimpleNamespace(pk=1201, settlement_interest_amount=Decimal("125.00")),
            payments=FakeRelated([FakePayment(interest_amount=Decimal("100.00"))]),
            loanitems=FakeRelated([SimpleNamespace(custody_status="with_customer")]),
        )

        report = build_loan_accounting_reconciliation_report(
            loans=[closed_without_release, custody_mismatch, interest_mismatch]
        )

        self.assertEqual(report["counts"]["closed_without_release"], 1)
        self.assertEqual(report["counts"]["release_custody_mismatch"], 1)
        self.assertEqual(report["counts"]["release_receipt_interest_mismatch"], 1)
        issue_codes = {row["issue_code"] for row in report["rows"]}
        self.assertIn("closed_without_release", issue_codes)
        self.assertIn("release_custody_mismatch", issue_codes)
        self.assertIn("release_receipt_interest_mismatch", issue_codes)

    def test_build_report_detects_repayment_idempotency_and_variance_mismatches(self):
        class FakeRelated(list):
            def all(self):
                return self

        class FakePayment:
            def __init__(self, reference_number):
                self.payment_id = f"PAY-{reference_number or 'BLANK'}"
                self.posted = True
                self.payment_type = "RECEIPT"
                self.direction = "RECEIPT"
                self.reference_number = reference_number
                self.create_release = False
                self.reversal_of_id = None
                self.pk = 1
                self.interest_amount = Decimal("0.00")

        loan = SimpleNamespace(
            pk=20,
            loan_id="GL-020",
            borrower=SimpleNamespace(name="Asha"),
            status="ActiveCurrent",
            release=SimpleNamespace(
                pk=2001,
                settlement_interest_amount=Decimal("0.00"),
                interest_basis_variance=Decimal("5.00"),
                settlement_basis="SELECTOR_COMPATIBILITY",
            ),
            payments=FakeRelated(
                [
                    FakePayment("REPAYMENT-GIVEN-20-idem"),
                    FakePayment("REPAYMENT-GIVEN-20-idem"),
                    FakePayment(""),
                ]
            ),
            loanitems=FakeRelated([SimpleNamespace(custody_status="with_customer")]),
        )

        report = build_loan_accounting_reconciliation_report(loans=[loan])

        self.assertEqual(report["counts"]["release_interest_basis_variance"], 1)
        self.assertEqual(report["counts"]["release_selector_compatibility_basis"], 1)
        self.assertEqual(report["counts"]["duplicate_repayment_reference"], 1)
        self.assertEqual(report["counts"]["repayment_missing_idempotency_marker"], 1)
        issue_codes = {row["issue_code"] for row in report["rows"]}
        self.assertIn("release_interest_basis_variance", issue_codes)
        self.assertIn("release_selector_compatibility_basis", issue_codes)
        self.assertIn("duplicate_repayment_reference", issue_codes)
        self.assertIn("repayment_missing_idempotency_marker", issue_codes)

    def test_build_report_fails_closed_when_release_relation_is_unavailable(self):
        class BrokenLoan:
            pk = 30
            loan_id = "GL-030"
            borrower = SimpleNamespace(name="Asha")
            status = "Closed"
            payments = []

            @property
            def release(self):
                raise RuntimeError("release relation broken")

        with self.assertRaises(ReconciliationDataUnavailableError):
            build_loan_accounting_reconciliation_report(loans=[BrokenLoan()])
