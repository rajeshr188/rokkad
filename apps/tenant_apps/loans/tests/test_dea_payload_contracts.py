from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import TransactionKind
from apps.tenant_apps.loans.integrations import (
    LoanDeaPayloadError,
    accrual_payload,
    auction_recovery_payload,
    capitalization_payload,
    disbursal_payload,
    release_receipt_payload,
    repayment_payload,
    reversal_payload,
    resolve_borrower_account,
)
from apps.tenant_apps.loans.integrations.dea_delivery import (
    deliver_loan_accounting_event,
)
from apps.tenant_apps.dea.posting.rules.pawn_loan_auction import (
    PawnLoanAuctionRecoveryRule,
)


class PawnLoanDeaPayloadContractTests(SimpleTestCase):
    def setUp(self):
        self.loan = SimpleNamespace(
            pk=71,
            loan_number="PL-2026-00071",
            borrower_id=31,
            borrower=SimpleNamespace(pk=31),
        )
        self.effective_date = date(2026, 8, 3)

    def test_each_mvp_accounting_event_has_a_complete_stable_contract(self):
        payloads = [
            disbursal_payload(
                self.loan,
                effective_date=self.effective_date,
                principal_amount="10000",
                source_event_id=1,
            ),
            repayment_payload(
                self.loan,
                effective_date=self.effective_date,
                principal_amount="800",
                interest_amount="200",
                source_event_id=2,
            ),
            accrual_payload(
                self.loan,
                effective_date=self.effective_date,
                interest_amount="200",
                source_event_id=3,
            ),
            capitalization_payload(
                self.loan,
                effective_date=self.effective_date,
                interest_amount="200",
                source_event_id=4,
            ),
            release_receipt_payload(
                self.loan,
                effective_date=self.effective_date,
                principal_amount="9200",
                interest_amount="200",
                source_event_id=5,
            ),
            auction_recovery_payload(
                self.loan,
                effective_date=self.effective_date,
                principal_amount="9200",
                interest_amount="200",
                source_event_id=6,
            ),
            reversal_payload(
                self.loan,
                effective_date=self.effective_date,
                original_event_id=5,
                original_event_kind=TransactionKind.RELEASE_RECEIPT,
                values={"principal": "9200", "interest": "200"},
                reason="Customer receipt entered twice.",
                source_event_id=7,
            ),
        ]

        self.assertEqual(
            [payload.event_kind for payload in payloads],
            [
                TransactionKind.DISBURSAL,
                TransactionKind.REPAYMENT,
                TransactionKind.INTEREST_ACCRUAL,
                TransactionKind.INTEREST_CAPITALIZATION,
                TransactionKind.RELEASE_RECEIPT,
                TransactionKind.AUCTION_RECOVERY,
                TransactionKind.REVERSAL,
            ],
        )
        for payload in payloads:
            contract = payload.to_dict()
            self.assertEqual(contract["source_identity"]["loan_id"], self.loan.pk)
            self.assertEqual(contract["effective_date"], self.effective_date.isoformat())
            self.assertTrue(contract["values"])
            self.assertEqual(len(payload.fingerprint), 64)
            self.assertEqual(
                payload.idempotency_key,
                f"loans:dea:{self.loan.pk}:{payload.event_kind.value}:{payload.fingerprint}",
            )
        self.assertEqual(
            payloads[-1].to_dict()["reversal"]["original_event_kind"],
            TransactionKind.RELEASE_RECEIPT.value,
        )

    def test_fingerprint_and_idempotency_key_change_with_economic_values(self):
        first = disbursal_payload(
            self.loan,
            effective_date=self.effective_date,
            principal_amount=Decimal("10000"),
        )
        equivalent = disbursal_payload(
            self.loan,
            effective_date=self.effective_date,
            principal_amount="10000.00",
        )
        changed = disbursal_payload(
            self.loan,
            effective_date=self.effective_date,
            principal_amount="10001",
        )

        self.assertEqual(first.fingerprint, equivalent.fingerprint)
        self.assertEqual(first.idempotency_key, equivalent.idempotency_key)
        self.assertNotEqual(first.fingerprint, changed.fingerprint)
        self.assertNotEqual(first.idempotency_key, changed.idempotency_key)

    def test_reversal_requires_reason_and_cannot_reverse_a_reversal(self):
        with self.assertRaises(LoanDeaPayloadError):
            reversal_payload(
                self.loan,
                effective_date=self.effective_date,
                original_event_id=1,
                original_event_kind=TransactionKind.DISBURSAL,
                values={"principal": "10000"},
                reason="",
            )
        with self.assertRaises(LoanDeaPayloadError):
            reversal_payload(
                self.loan,
                effective_date=self.effective_date,
                original_event_id=1,
                original_event_kind=TransactionKind.REVERSAL,
                values={"principal": "10000"},
                reason="Cannot reverse a reversal.",
            )

    def test_borrower_account_is_resolved_only_through_dea_facade(self):
        with patch(
            "apps.tenant_apps.loans.integrations.dea_payloads.dea_facade.resolve_party_account",
            return_value="resolved-account",
        ) as resolve:
            result = resolve_borrower_account(self.loan, create=False)

        self.assertEqual(result, "resolved-account")
        resolve.assert_called_once_with(
            self.loan.borrower,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
            create=False,
        )

    def test_payload_adapter_cannot_bypass_the_public_dea_facade(self):
        adapter_source = Path(__file__).parents[1] / "integrations" / "dea_payloads.py"
        source = adapter_source.read_text(encoding="utf-8")

        self.assertIn("from apps.tenant_apps.dea import facade as dea_facade", source)
        self.assertNotIn("apps.tenant_apps.dea.models", source)
        self.assertNotIn("apps.tenant_apps.dea.posting", source)
        self.assertNotIn("apps.tenant_apps.dea.services", source)

    def test_zero_settlement_release_is_operational_only(self):
        event = SimpleNamespace(
            event_kind=TransactionKind.RELEASE_RECEIPT.value,
            payload={
                "values": {"principal": "0", "interest": "0", "fees": "0"}
            },
            created_by=None,
        )
        with patch(
            "apps.tenant_apps.loans.integrations.dea_delivery.dea_facade."
            "post_pawn_loan_release_event"
        ) as post:
            receipt = deliver_loan_accounting_event(event)

        self.assertIsNone(receipt.dea_voucher_id)
        self.assertIsNone(receipt.dea_journal_entry_id)
        post.assert_not_called()

    def test_auction_delivery_uses_dedicated_dea_facade(self):
        event = SimpleNamespace(
            event_kind=TransactionKind.AUCTION_RECOVERY.value,
            payload={"values": {"principal": "10000", "interest": "0", "fees": "0"}},
            created_by=None,
        )
        expected = SimpleNamespace(dea_voucher_id=41, dea_journal_entry_id=42)
        with patch(
            "apps.tenant_apps.loans.integrations.dea_delivery.dea_facade."
            "post_pawn_loan_auction_recovery_event",
            return_value=expected,
        ) as post:
            receipt = deliver_loan_accounting_event(event)

        self.assertIs(receipt, expected)
        post.assert_called_once_with(event, actor=None)

    def test_auction_rule_reads_accrual_recognition_from_auction_snapshot(self):
        event = SimpleNamespace(
            event_kind=TransactionKind.AUCTION_RECOVERY.value,
            payload={
                "currency": "INR",
                "values": {
                    "principal": "10000",
                    "capitalized_interest_principal": "0",
                    "interest": "200",
                    "fees": "0",
                },
                "auction": {"accounting_recognition": "ACCRUAL"},
            },
            loan=SimpleNamespace(borrower=object()),
        )
        ledger_ids = {
            "CASH": 1,
            "LOAN_PRINCIPAL_CTRL": 2,
            "INTEREST_RECEIVABLE": 3,
            "INTEREST_INCOME": 4,
            "DOCUMENT_CHARGE_INCOME": 5,
            "BORROWER_LOAN_CTRL": 6,
        }
        with patch(
            "apps.tenant_apps.dea.posting.rules.pawn_loan_release.resolve_party_account",
            return_value=SimpleNamespace(account=SimpleNamespace(pk=99)),
        ), patch(
            "apps.tenant_apps.dea.posting.rules.pawn_loan_release._ledger_id",
            side_effect=lambda key: ledger_ids[key],
        ):
            bundle = PawnLoanAuctionRecoveryRule().build_posting(
                SimpleNamespace(doc=event)
            )

        self.assertIn(ledger_ids["INTEREST_RECEIVABLE"], [line.credit_ledger_id for line in bundle.ledger_lines])
        self.assertNotIn(ledger_ids["INTEREST_INCOME"], [line.credit_ledger_id for line in bundle.ledger_lines])
