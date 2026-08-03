from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import TransactionKind
from apps.tenant_apps.loans.services import (
    PawnLoanDocumentError,
    PawnLoanDocumentService,
)


class _Manager:
    def __init__(self, *values):
        self.values = values

    def all(self):
        return self.values

    def order_by(self, *args):
        return self

    def first(self):
        return self.values[0] if self.values else None


class PawnLoanDocumentServiceTests(SimpleTestCase):
    def setUp(self):
        workspace = SimpleNamespace(pk=7, name="Rokkad Test Workspace")
        license = SimpleNamespace(
            pk=11,
            name="Pawnbroker License",
            license_number="PBL-77",
            issuing_authority="District Registrar",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        borrower = SimpleNamespace(pk=13, display_name="Asha Devi", party_code="P-000013")
        collateral = SimpleNamespace(
            pk=17,
            description="Gold chain",
            net_weight=Decimal("9.0000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("50000"),
            get_metal_display=lambda: "Gold",
            get_custody_state_display=lambda: "In Vault",
        )
        approval = SimpleNamespace(
            pk=21,
            version=1,
            fingerprint="approval-fingerprint-1",
            payload={
                "loan_number": "PL-A-00019",
                "loan_date": "2026-07-18",
                "principal_amount": "10000",
                "monthly_interest_rate": "2",
                "tenure_months": 3,
                "borrower_id": borrower.pk,
                "collateral": [
                    {
                        "item_id": collateral.pk,
                        "description": collateral.description,
                        "metal": "GOLD",
                        "net_weight": "9.0000",
                        "purity_percentage": "91.6000",
                        "latest_appraised_value": "50000",
                    }
                ],
            },
        )
        self.loan = SimpleNamespace(
            pk=19,
            workspace=workspace,
            workspace_id=workspace.pk,
            license=license,
            borrower=borrower,
            borrower_id=borrower.pk,
            loan_number="PL-A-00019",
            state="ACTIVE",
            loan_date=date(2026, 7, 18),
            principal_amount=Decimal("10000"),
            monthly_interest_rate=Decimal("2"),
            tenure_months=3,
            collateral_items=_Manager(collateral),
            approval_snapshots=_Manager(approval),
            get_state_display=lambda: "Active",
        )

    def test_loan_ticket_contains_stable_source_verification_fixture(self):
        result = PawnLoanDocumentService.render_loan_ticket(self.loan)

        self.assertTrue(result.pdf.startswith(b"%PDF"))
        self.assertGreater(len(result.pdf), 1000)
        self.assertEqual(result.file_name, "pawn_loan_ticket_PL-A-00019.pdf")
        self.assertEqual(
            result.verification_id,
            "ROKKAD|workspace:7|loan:19|approval:21:v1:approval-fingerprint-1",
        )

    def test_repayment_receipt_uses_immutable_event_amount_split(self):
        outbox = SimpleNamespace(
            dea_voucher_id=31,
            dea_journal_entry_id=32,
            get_status_display=lambda: "Posted",
        )
        event = SimpleNamespace(
            pk=23,
            loan=self.loan,
            event_kind=TransactionKind.REPAYMENT.value,
            effective_date=date(2026, 8, 3),
            payload_fingerprint="repayment-fingerprint-23",
            payload={
                "values": {
                    "fees": "10",
                    "overdue_interest": "20",
                    "current_interest": "30",
                    "interest": "50",
                    "principal": "440",
                },
                "repayment": {"amount_received": "500"},
            },
            outbox=outbox,
        )

        result = PawnLoanDocumentService.render_repayment_receipt(event)

        self.assertTrue(result.pdf.startswith(b"%PDF"))
        self.assertEqual(result.file_name, "pawn_repayment_PL-A-00019_23.pdf")
        self.assertIn("repayment:23:repayment-fingerprint-23", result.verification_id)

    def test_release_memo_uses_immutable_release_and_item_snapshot(self):
        event = SimpleNamespace(pk=29, payload_fingerprint="release-fingerprint-29")
        event.outbox = SimpleNamespace(
            dea_voucher_id=41,
            dea_journal_entry_id=42,
            get_status_display=lambda: "Posted",
        )
        collateral = self.loan.collateral_items.first()
        release_item = SimpleNamespace(
            collateral_item_id=collateral.pk,
            collateral_item=collateral,
            valuation_snapshot={"valuation_amount": "45000"},
            returned_at=datetime(2026, 8, 3, 12, 30),
        )
        release = SimpleNamespace(
            pk=27,
            loan=self.loan,
            accounting_event=event,
            release_number="RL-A-00001",
            effective_date=date(2026, 8, 3),
            is_full_release=True,
            principal_amount=Decimal("10000"),
            interest_amount=Decimal("500"),
            fee_amount=Decimal("0"),
            settlement_amount=Decimal("10500"),
            items=_Manager(release_item),
        )

        result = PawnLoanDocumentService.render_release_memo(release)

        self.assertTrue(result.pdf.startswith(b"%PDF"))
        self.assertEqual(result.file_name, "pawn_release_RL-A-00001.pdf")
        self.assertIn("release:27:RL-A-00001:release-fingerprint-29", result.verification_id)

    def test_receipt_rejects_non_repayment_source(self):
        event = SimpleNamespace(event_kind=TransactionKind.DISBURSAL.value)

        with self.assertRaises(PawnLoanDocumentError):
            PawnLoanDocumentService.render_repayment_receipt(event)

    def test_loan_ticket_rejects_mutable_unapproved_draft(self):
        self.loan.approval_snapshots = _Manager()

        with self.assertRaises(PawnLoanDocumentError):
            PawnLoanDocumentService.render_loan_ticket(self.loan)
