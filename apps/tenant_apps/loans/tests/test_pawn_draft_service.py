import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import (
    CollateralMetal,
    LoanDocumentKind,
    PawnLoanEventKind,
    PawnLoanState,
)
from apps.tenant_apps.loans.models import (
    LoanChangeLog,
    LoanLicense,
    LoanNumberSequence,
    LoanSeries,
    PawnCollateralItem,
    PawnLoan,
)
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    PawnDraftError,
    UpdatePawnDraftCommand,
    create_pawn_draft,
    update_pawn_draft,
)
from apps.tenant_apps.party.models import Party


class PawnDraftServiceTests(TenantTestCase):
    test_schema_name = f"loans_draft_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-draft-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="loans-draft-owner",
            defaults={"email": "loans-draft-owner@example.com"},
        )
        tenant.name = f"Loans Draft {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.actor = get_user_model().objects.create_user(
            username=f"draft-actor-{uuid.uuid4().hex[:8]}",
            email=f"draft-actor-{uuid.uuid4().hex[:8]}@example.com",
        )
        self.borrower = Party.objects.create(
            display_name="Active Borrower",
            status=Party.PartyStatus.ACTIVE,
        )
        self.license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Draft License",
            license_number=f"PBL-D-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        self.series = LoanSeries.objects.create(
            license=self.license,
            name="Main",
            code="A",
        )
        self.sequence = LoanNumberSequence.objects.create(
            series=self.series,
            document_kind=LoanDocumentKind.PAWN_LOAN.value,
            prefix="PL-A-",
            width=5,
            maximum_number=10000,
        )

    def collateral(self, **changes):
        values = {
            "description": "Gold bangles",
            "metal": CollateralMetal.GOLD,
            "gross_weight": Decimal("20.0000"),
            "net_weight": Decimal("18.0000"),
            "purity_percentage": Decimal("91.6000"),
            "latest_appraised_value": Decimal("120000.00"),
        }
        values.update(changes)
        return CollateralDraftInput(**values)

    def command(self, **changes):
        values = {
            "workspace_id": self.tenant.pk,
            "borrower_id": self.borrower.pk,
            "license_id": self.license.pk,
            "series_id": self.series.pk,
            "principal_amount": Decimal("50000.00"),
            "monthly_interest_rate": Decimal("2.000000"),
            "loan_date": date(2026, 7, 18),
            "tenure_months": 3,
            "collateral": (self.collateral(),),
        }
        values.update(changes)
        return CreatePawnDraftCommand(**values)

    def test_create_is_atomic_and_allocates_official_number_with_audit(self):
        loan = create_pawn_draft(self.command(), actor=self.actor)

        self.assertEqual(loan.loan_number, "PL-A-00001")
        self.assertEqual(loan.state, PawnLoanState.DRAFT.value)
        self.assertEqual(loan.borrower, self.borrower)
        self.assertEqual(loan.collateral_items.count(), 1)
        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.next_number, 2)
        event = LoanChangeLog.objects.get(loan=loan)
        self.assertEqual(event.event_kind, PawnLoanEventKind.DRAFT_CREATED.value)
        self.assertEqual(event.actor, self.actor)
        self.assertEqual(event.metadata["collateral_count"], 1)

    def test_invalid_party_setup_and_economics_fail_before_number_allocation(self):
        inactive = Party.objects.create(
            display_name="Inactive Borrower",
            status=Party.PartyStatus.INACTIVE,
        )
        other_license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Other License",
            license_number=f"PBL-O-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        wrong_series = LoanSeries.objects.create(
            license=other_license, name="Other", code="B"
        )
        cases = (
            self.command(workspace_id=self.tenant.pk + 1000),
            self.command(borrower_id=inactive.pk),
            self.command(license_id=999999),
            self.command(series_id=wrong_series.pk),
            self.command(principal_amount=Decimal("0")),
            self.command(monthly_interest_rate=Decimal("-1")),
            self.command(tenure_months=0),
        )

        for command in cases:
            with self.subTest(command=command):
                with self.assertRaises((PawnDraftError, ValidationError)):
                    create_pawn_draft(command, actor=self.actor)
                self.assertEqual(PawnLoan.objects.count(), 0)
                self.sequence.refresh_from_db()
                self.assertEqual(self.sequence.next_number, 1)

    def test_multiple_drafts_receive_distinct_official_numbers(self):
        first = create_pawn_draft(self.command(), actor=self.actor)
        second = create_pawn_draft(self.command(), actor=self.actor)

        self.assertEqual(first.loan_number, "PL-A-00001")
        self.assertEqual(second.loan_number, "PL-A-00002")
        self.assertEqual(
            PawnLoan.objects.values_list("loan_number", flat=True).distinct().count(),
            2,
        )

    def test_invalid_collateral_fails_atomically(self):
        cases = (
            (),
            (self.collateral(description=""),),
            (self.collateral(gross_weight=Decimal("0")),),
            (self.collateral(net_weight=Decimal("21")),),
            (self.collateral(purity_percentage=Decimal("0")),),
            (self.collateral(purity_percentage=Decimal("101")),),
            (self.collateral(latest_appraised_value=Decimal("0")),),
        )

        for collateral in cases:
            with self.subTest(collateral=collateral):
                with self.assertRaises((PawnDraftError, ValidationError)):
                    create_pawn_draft(
                        self.command(collateral=collateral), actor=self.actor
                    )
                self.assertEqual(PawnLoan.objects.count(), 0)
                self.assertEqual(PawnCollateralItem.objects.count(), 0)
                self.sequence.refresh_from_db()
                self.assertEqual(self.sequence.next_number, 1)

    def test_failure_after_allocation_rolls_back_number_and_draft(self):
        with patch.object(
            PawnCollateralItem.objects,
            "bulk_create",
            side_effect=RuntimeError("simulated persistence failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                create_pawn_draft(self.command(), actor=self.actor)

        self.assertEqual(PawnLoan.objects.count(), 0)
        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.next_number, 1)

    def test_update_replaces_validated_payload_and_audits_before_after(self):
        loan = create_pawn_draft(self.command(), actor=self.actor)
        second_borrower = Party.objects.create(display_name="Second Borrower")
        command = UpdatePawnDraftCommand(
            borrower_id=second_borrower.pk,
            principal_amount=Decimal("60000.00"),
            monthly_interest_rate=Decimal("2.250000"),
            loan_date=date(2026, 7, 18),
            tenure_months=6,
            collateral=(
                self.collateral(description="Gold chain"),
                self.collateral(
                    description="Gold ring",
                    gross_weight=Decimal("8"),
                    net_weight=Decimal("7"),
                ),
            ),
        )

        updated = update_pawn_draft(loan.pk, command, actor=self.actor)

        updated.refresh_from_db()
        self.assertEqual(updated.borrower, second_borrower)
        self.assertEqual(updated.principal_amount, Decimal("60000.00"))
        self.assertEqual(updated.collateral_items.count(), 2)
        events = list(updated.change_log.order_by("created_at", "pk"))
        self.assertEqual(events[-1].event_kind, PawnLoanEventKind.DRAFT_UPDATED.value)
        self.assertEqual(events[-1].metadata["before"]["collateral"][0]["description"], "Gold bangles")
        self.assertEqual(events[-1].metadata["after"]["collateral"][0]["description"], "Gold chain")
        self.assertEqual(updated.loan_number, "PL-A-00001")

    def test_invalid_update_preserves_existing_draft_and_collateral(self):
        loan = create_pawn_draft(self.command(), actor=self.actor)
        command = UpdatePawnDraftCommand(
            borrower_id=self.borrower.pk,
            principal_amount=Decimal("0"),
            monthly_interest_rate=Decimal("2"),
            loan_date=date(2026, 7, 18),
            tenure_months=3,
            collateral=(self.collateral(description="Replacement"),),
        )

        with self.assertRaises(ValidationError):
            update_pawn_draft(loan.pk, command, actor=self.actor)

        loan.refresh_from_db()
        self.assertEqual(loan.principal_amount, Decimal("50000.00"))
        self.assertEqual(
            loan.collateral_items.get().description,
            "Gold bangles",
        )
        self.assertEqual(loan.change_log.count(), 1)

    def test_non_draft_cannot_be_edited(self):
        loan = create_pawn_draft(self.command(), actor=self.actor)
        PawnLoan.objects.filter(pk=loan.pk).update(state=PawnLoanState.APPROVED.value)
        command = UpdatePawnDraftCommand(
            borrower_id=self.borrower.pk,
            principal_amount=Decimal("60000"),
            monthly_interest_rate=Decimal("2"),
            loan_date=date(2026, 7, 18),
            tenure_months=3,
            collateral=(self.collateral(),),
        )

        with self.assertRaisesRegex(PawnDraftError, "Only a draft"):
            update_pawn_draft(loan.pk, command, actor=self.actor)
