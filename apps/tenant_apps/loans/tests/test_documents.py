from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

import fitz
from django.test import SimpleTestCase

from apps.tenant_apps.loans.domain import TransactionKind
from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer,
    DocumentPayload,
    PawnLoanDocumentProjectionBuilder,
    starter_layout,
)
from apps.tenant_apps.loans.services import (
    PawnLoanDocumentError,
    PawnLoanDocumentService,
)


class _Manager:
    def __init__(self, *values):
        self.values = values

    def all(self):
        return self.values

    def __iter__(self):
        return iter(self.values)

    def order_by(self, *args):
        return self

    def select_related(self, *args):
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
            renewed_from_id=None,
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
        document = fitz.open(stream=result.pdf, filetype="pdf")
        self.assertEqual(document.page_count, 2)
        self.assertIn("Original copy", document[0].get_text())
        self.assertIn("Duplicate copy", document[1].get_text())
        for page in document:
            text = page.get_text()
            self.assertIn(result.verification_id, text)
            self.assertIn("Borrower / customer signature", text)
            self.assertIn("Authorized pawnbroker signature", text)

    def test_loan_ticket_projection_is_typed_versioned_and_renderer_independent(self):
        payload = PawnLoanDocumentProjectionBuilder.loan_ticket(self.loan)

        self.assertIsInstance(payload, DocumentPayload)
        self.assertEqual(payload.schema_version, 1)
        self.assertEqual(payload.document_type, "loan_ticket")
        self.assertEqual(payload.title, "Pawn Loan Ticket")
        self.assertEqual(payload.fields[0].key, "workspace.name")
        self.assertEqual(payload.sections[0].key, "collateral.items")
        self.assertEqual(payload.sections[0].heading, "Collateral")
        self.assertIn(("Approval fingerprint", "approval-fingerprint-1"), payload.details)

        with self.assertRaises(AttributeError):
            payload.title = "Changed"

    def test_repayment_receipt_uses_immutable_event_amount_split(self):
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
            repayment_allocation_lines=_Manager(
                SimpleNamespace(
                    collateral_item_id=17,
                    collateral_item=self.loan.collateral_items.first(),
                    monthly_interest_rate=Decimal("2"),
                    balance_before=Decimal("10000"),
                    principal_applied=Decimal("440"),
                    balance_after=Decimal("9560"),
                )
            ),
        )

        result = PawnLoanDocumentService.render_repayment_receipt(event)

        self.assertTrue(result.pdf.startswith(b"%PDF"))
        self.assertEqual(result.file_name, "pawn_repayment_PL-A-00019_23.pdf")
        self.assertIn("repayment:23:repayment-fingerprint-23", result.verification_id)
        self.assertIn(b"Collateral principal allocation", result.pdf)
        self.assertIn(b"Gold chain", result.pdf)
        custom = ConfigurableDocumentRenderer.render(
            PawnLoanDocumentProjectionBuilder.repayment_receipt(event),
            starter_layout("repayment_receipt"),
        )
        self.assertTrue(custom.pdf.startswith(b"%PDF"))

    def test_release_memo_uses_immutable_release_and_item_snapshot(self):
        event = SimpleNamespace(pk=29, payload_fingerprint="release-fingerprint-29")
        collateral = self.loan.collateral_items.first()
        event.principal_closing_lines = _Manager(
            SimpleNamespace(
                collateral_item_id=collateral.pk,
                collateral_item=collateral,
                monthly_interest_rate=Decimal("2"),
                balance_before=Decimal("10000"),
                principal_settled=Decimal("10000"),
                balance_after=Decimal("0"),
            )
        )
        release_item = SimpleNamespace(
            collateral_item_id=collateral.pk,
            collateral_item=collateral,
            valuation_snapshot={"valuation_amount": "45000"},
            returned_at=datetime(2026, 8, 3, 12, 30),
        )
        release = SimpleNamespace(
            pk=27,
            loan=self.loan,
            loan_event=event,
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
        self.assertIn(b"Item principal settled", result.pdf)
        self.assertIn(b"Gold chain", result.pdf)
        text = "".join(
            page.get_text()
            for page in fitz.open(stream=result.pdf, filetype="pdf")
        )
        self.assertIn("Borrower / customer signature", text)
        self.assertIn("Authorized pawnbroker signature", text)
        custom = ConfigurableDocumentRenderer.render(
            PawnLoanDocumentProjectionBuilder.release_memo(release),
            starter_layout("release_memo"),
        )
        self.assertIn(b"Gold chain", custom.pdf)

    def test_renewal_memo_exposes_returned_retained_added_and_principal_evidence(self):
        source_item = self.loan.collateral_items.first()
        returned_item = SimpleNamespace(
            pk=18,
            description="Returned bracelet",
            latest_appraised_value=Decimal("20000"),
            renewed_from_id=None,
        )
        self.loan.collateral_items = _Manager(source_item, returned_item)
        retained = SimpleNamespace(
            pk=31,
            description="Gold chain",
            latest_appraised_value=Decimal("50000"),
            renewed_from_id=source_item.pk,
        )
        additional = SimpleNamespace(
            pk=32,
            description="Added silver anklet",
            latest_appraised_value=Decimal("15000"),
            renewed_from_id=None,
        )
        successor = SimpleNamespace(
            loan_number="PL-A-00020",
            collateral_items=_Manager(retained, additional),
        )
        posted = SimpleNamespace(get_status_display=lambda: "Posted")
        settlement_event = SimpleNamespace(
            payload_fingerprint="renewal-settlement-41",
            outbox=posted,
            principal_closing_lines=_Manager(
                SimpleNamespace(
                    collateral_item_id=source_item.pk,
                    monthly_interest_rate=Decimal("2"),
                    balance_before=Decimal("10000"),
                    principal_settled=Decimal("10000"),
                    balance_after=Decimal("0"),
                )
            ),
        )
        opening_event = SimpleNamespace(
            outbox=posted,
            principal_opening_lines=_Manager(
                SimpleNamespace(
                    collateral_item_id=retained.pk,
                    predecessor_collateral_item_id=source_item.pk,
                    monthly_interest_rate=Decimal("2"),
                    principal_opened=Decimal("7000"),
                ),
                SimpleNamespace(
                    collateral_item_id=additional.pk,
                    predecessor_collateral_item_id=None,
                    monthly_interest_rate=Decimal("4"),
                    principal_opened=Decimal("3000"),
                ),
            ),
        )
        renewal = SimpleNamespace(
            pk=41,
            source_loan=self.loan,
            successor_loan=successor,
            settlement_event=settlement_event,
            opening_event=opening_event,
            renewal_number="REN-PL-A-00019",
            renewal_date=date(2026, 8, 3),
            source_principal_amount=Decimal("10000"),
            interest_settled=Decimal("0"),
            fees_settled=Decimal("0"),
            successor_advance_interest=Decimal("200"),
            successor_deducted_fees=Decimal("50"),
            principal_paid=Decimal("0"),
            top_up_amount=Decimal("0"),
            successor_principal_amount=Decimal("10000"),
            valuation_snapshot={
                "items": [
                    {"source_item_id": source_item.pk, "valuation_amount": "50000"},
                    {"source_item_id": returned_item.pk, "valuation_amount": "20000"},
                ]
            },
            get_mode_display=lambda: "Pay and renew",
        )

        result = PawnLoanDocumentService.render_renewal_memo(renewal)

        self.assertTrue(result.pdf.startswith(b"%PDF"))
        self.assertIn(b"Collateral movement", result.pdf)
        self.assertIn(b"Source item principal settled", result.pdf)
        self.assertIn(b"Successor item principal opened", result.pdf)
        self.assertIn(b"Returned bracelet", result.pdf)
        self.assertIn(b"Added silver anklet", result.pdf)
        self.assertEqual(
            result.file_name,
            "pawn_renewal_agreement_REN-PL-A-00019.pdf",
        )
        text = "".join(
            page.get_text()
            for page in fitz.open(stream=result.pdf, filetype="pdf")
        )
        self.assertIn("Pawn Loan Renewal Agreement", text)
        self.assertIn("Successor advance interest", text)
        self.assertIn("Successor deducted fees", text)
        self.assertIn("Net cash handoff", text)
        custom = ConfigurableDocumentRenderer.render(
            PawnLoanDocumentProjectionBuilder.renewal_memo(renewal),
            starter_layout("renewal"),
        )
        self.assertIn(b"Added silver anklet", custom.pdf)

    def test_operational_release_memo_does_not_require_an_outbox(self):
        event = SimpleNamespace(pk=30, payload_fingerprint="operational-release-30")
        release = SimpleNamespace(
            pk=28,
            loan=self.loan,
            loan_event=event,
            release_number="RL-A-00002",
            effective_date=date(2026, 8, 3),
            is_full_release=False,
            principal_amount=Decimal("0"),
            interest_amount=Decimal("0"),
            fee_amount=Decimal("0"),
            settlement_amount=Decimal("0"),
            items=_Manager(),
        )

        result = PawnLoanDocumentService.render_release_memo(release)

        self.assertTrue(result.pdf.startswith(b"%PDF"))
        self.assertEqual(result.file_name, "pawn_release_RL-A-00002.pdf")

    def test_auction_notice_and_recovery_use_typed_projection_path(self):
        collateral = self.loan.collateral_items.first()
        notice = SimpleNamespace(notification_job_id=73)
        event = SimpleNamespace(
            effective_date=date(2026, 8, 5),
            payload_fingerprint="auction-recovery-71",
        )
        auction_item = SimpleNamespace(
            collateral_item_id=collateral.pk,
            collateral_item=collateral,
            snapshot={
                "description": "Gold chain at auction",
                "metal": "GOLD",
                "net_weight": "9.0000",
                "purity_percentage": "91.6000",
            },
        )
        auction = SimpleNamespace(
            pk=71,
            loan=self.loan,
            auction_number="AUC-00071",
            notice_date=date(2026, 8, 4),
            scheduled_date=date(2026, 8, 5),
            notice=notice,
            loan_event_id=72,
            loan_event=event,
            buyer_name="Test Buyer",
            buyer_reference="BUY-1",
            principal_amount=Decimal("10000"),
            interest_amount=Decimal("500"),
            fee_amount=Decimal("0"),
            recovery_amount=Decimal("10500"),
            items=_Manager(auction_item),
            get_state_display=lambda: "Completed",
        )

        notice_result = PawnLoanDocumentService.render_auction_notice(auction)
        recovery_result = PawnLoanDocumentService.render_auction_recovery_memo(auction)

        self.assertEqual(notice_result.file_name, "pawn_auction_notice_AUC-00071.pdf")
        self.assertIn(b"Notice delivery job", notice_result.pdf)
        self.assertEqual(
            recovery_result.file_name,
            "pawn_auction_recovery_AUC-00071.pdf",
        )
        self.assertIn(b"Gold chain at", recovery_result.pdf)
        self.assertIn(b"(auction)", recovery_result.pdf)
        custom_notice = ConfigurableDocumentRenderer.render(
            PawnLoanDocumentProjectionBuilder.auction_notice(auction),
            starter_layout("auction_notice"),
        )
        custom_recovery = ConfigurableDocumentRenderer.render(
            PawnLoanDocumentProjectionBuilder.auction_recovery_memo(auction),
            starter_layout("auction_recovery"),
        )
        self.assertTrue(custom_notice.pdf.startswith(b"%PDF"))
        self.assertIn(b"Gold chain at", custom_recovery.pdf)

    def test_receipt_rejects_non_repayment_source(self):
        event = SimpleNamespace(event_kind=TransactionKind.DISBURSAL.value)

        with self.assertRaises(PawnLoanDocumentError):
            PawnLoanDocumentService.render_repayment_receipt(event)

    def test_loan_ticket_rejects_mutable_unapproved_draft(self):
        self.loan.approval_snapshots = _Manager()

        with self.assertRaises(PawnLoanDocumentError):
            PawnLoanDocumentService.render_loan_ticket(self.loan)
