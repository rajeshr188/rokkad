import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import DatabaseError, IntegrityError, connection, transaction
from django.utils import timezone
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
    CollateralMetal,
    PawnLoanState,
)
from apps.tenant_apps.loans.domain.future_funding import (
    FundingLoanEventKind,
    FundingLoanState,
)
from apps.tenant_apps.loans.models import (
    FundingLoan,
    FundingLoanEvent,
    FundingLoanTermsSnapshot,
    FundingPledge,
    FundingPledgeItem,
    FundingPledgeReversal,
    FundingReturn,
    FundingReturnItem,
    FundingReturnReversal,
    LoanLicense,
    LoanSeries,
    PawnCollateralCustodyEvent,
    PawnCollateralItem,
    PawnLoan,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version


class FundingLoanPersistenceTests(TenantTestCase):
    test_schema_name = f"funding_persistence_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        User = get_user_model()
        owner, _ = User.objects.get_or_create(
            username="funding-persistence-owner",
            defaults={"email": "funding-persistence-owner@example.com"},
        )
        tenant.name = f"Funding Persistence {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        User = get_user_model()
        self.actor = User.objects.create_user(
            username=f"funding-actor-{uuid.uuid4().hex[:8]}",
            email=f"funding-actor-{uuid.uuid4().hex[:8]}@example.com",
        )
        self.borrower = Party.objects.create(
            party_code=f"BOR-{uuid.uuid4().hex[:8]}",
            display_name="Funding collateral borrower",
        )
        self.lender = Party.objects.create(
            party_code=f"LND-{uuid.uuid4().hex[:8]}",
            display_name="Funding lender",
        )
        self.license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Funding Test License",
            license_number=f"FTL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        self.series = LoanSeries.objects.create(
            license=self.license,
            name="Funding Test Series",
            code=f"F{uuid.uuid4().hex[:6]}",
        )
        self.pawn_loan = PawnLoan.objects.create(
            workspace=self.tenant,
            license=self.license,
            series=self.series,
            product_version=ensure_test_product_version(self.tenant),
            borrower=self.borrower,
            loan_number=f"PL-{uuid.uuid4().hex[:8]}",
            state=PawnLoanState.ACTIVE.value,
            principal_amount=Decimal("5000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 8, 1),
            tenure_months=3,
        )
        self.collateral = PawnCollateralItem.objects.create(
            loan=self.pawn_loan,
            description="Gold chain",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10.0000"),
            net_weight=Decimal("9.5000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("10000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )

    def create_funding_loan(self, suffix="A"):
        return FundingLoan.objects.create(
            workspace=self.tenant,
            lender=self.lender,
            funding_number=f"FL-{suffix}-{uuid.uuid4().hex[:6]}",
            created_by=self.actor,
            updated_by=self.actor,
        )

    def create_activation_evidence(self, funding_loan):
        terms = FundingLoanTermsSnapshot.objects.create(
            funding_loan=funding_loan,
            principal_amount=Decimal("6000.0000"),
            monthly_interest_rate=Decimal("1.500000"),
            activated_on=date(2026, 8, 8),
            maturity_on=date(2026, 11, 8),
            maximum_funding_ltv_ratio=Decimal("0.800000"),
            currency_quantum=Decimal("0.0100"),
            fingerprint="terms-fingerprint",
            created_by=self.actor,
        )
        event = FundingLoanEvent.objects.create(
            funding_loan=funding_loan,
            sequence=1,
            event_kind=FundingLoanEventKind.ACTIVATION.value,
            operation="ACTIVATE",
            effective_date=date(2026, 8, 8),
            principal_amount=Decimal("6000.0000"),
            request_key="activate-request",
            request_fingerprint="activation-fingerprint",
            actor=self.actor,
        )
        pledge = FundingPledge.objects.create(
            workspace=self.tenant,
            funding_loan=funding_loan,
            effective_date=date(2026, 8, 8),
            request_key="pledge-request",
            request_fingerprint="pledge-fingerprint",
            total_collateral_value=Decimal("10000.0000"),
            maximum_funded_amount=Decimal("8000.0000"),
            valuation_method="LATEST_APPRAISAL",
            valuation_snapshot={"source": "test"},
            actor=self.actor,
        )
        return terms, event, pledge

    def create_pledge_item(self, pledge):
        return FundingPledgeItem.objects.create(
            funding_pledge=pledge,
            collateral_item=self.collateral,
            source_pawn_loan_id=self.pawn_loan.pk,
            selected_collateral_value=Decimal("10000.0000"),
            valuation_snapshot={"value": "10000.0000"},
            valuation_fingerprint="item-fingerprint",
        )

    def test_schema_seeds_no_funding_rows(self):
        self.assertEqual(FundingLoan.objects.count(), 0)

    def test_database_blocks_evidence_update_and_delete_bypasses(self):
        funding_loan = self.create_funding_loan()
        terms, event, _ = self.create_activation_evidence(funding_loan)

        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingLoanTermsSnapshot.objects.filter(pk=terms.pk).update(
                principal_amount=Decimal("1.0000")
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingLoanEvent.objects.filter(pk=event.pk).delete()

    def test_database_requires_activation_evidence_and_legal_transitions(self):
        funding_loan = self.create_funding_loan()

        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingLoan.objects.filter(pk=funding_loan.pk).update(
                state=FundingLoanState.ACTIVE.value
            )

        _, _, pledge = self.create_activation_evidence(funding_loan)
        self.create_pledge_item(pledge)
        with transaction.atomic():
            PawnCollateralCustodyEvent.objects.create(
                collateral_item=self.collateral,
                funding_pledge=pledge,
                from_state=CollateralCustodyState.IN_VAULT.value,
                to_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
                effective_date=date(2026, 8, 8),
                actor=self.actor,
            )
            self.collateral.custody_state = CollateralCustodyState.WITH_FUNDING_LENDER.value
            self.collateral.save(update_fields=["custody_state", "updated_at"])
            FundingLoan.objects.filter(pk=funding_loan.pk).update(
                state=FundingLoanState.ACTIVE.value
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingLoan.objects.filter(pk=funding_loan.pk).update(
                state=FundingLoanState.CLOSED.value
            )

    def test_database_requires_exact_newest_first_event_reversal(self):
        funding_loan = self.create_funding_loan()
        _, activation, _ = self.create_activation_evidence(funding_loan)
        interest = FundingLoanEvent.objects.create(
            funding_loan=funding_loan,
            sequence=2,
            event_kind=FundingLoanEventKind.INTEREST_ACCRUAL.value,
            operation="ACCRUE_INTEREST",
            effective_date=date(2026, 9, 8),
            interest_amount=Decimal("90.0000"),
            request_key="interest-request",
            request_fingerprint="interest-fingerprint",
            actor=self.actor,
        )

        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingLoanEvent.objects.bulk_create(
                [
                    FundingLoanEvent(
                        funding_loan=funding_loan,
                        sequence=3,
                        event_kind=FundingLoanEventKind.REVERSAL.value,
                        operation="REVERSE_EVENT",
                        effective_date=date(2026, 9, 9),
                        principal_amount=activation.principal_amount,
                        request_key="reverse-activation-first",
                        request_fingerprint="reverse-activation-first",
                        reversal_of=activation,
                        reason="Wrong order",
                    )
                ]
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingLoanEvent.objects.bulk_create(
                [
                    FundingLoanEvent(
                        funding_loan=funding_loan,
                        sequence=3,
                        event_kind=FundingLoanEventKind.REVERSAL.value,
                        operation="REVERSE_EVENT",
                        effective_date=date(2026, 9, 9),
                        interest_amount=Decimal("89.0000"),
                        request_key="reverse-wrong-amount",
                        request_fingerprint="reverse-wrong-amount",
                        reversal_of=interest,
                        reason="Wrong amount",
                    )
                ]
            )

        reversal = FundingLoanEvent.objects.create(
            funding_loan=funding_loan,
            sequence=3,
            event_kind=FundingLoanEventKind.REVERSAL.value,
            operation="REVERSE_EVENT",
            effective_date=date(2026, 9, 9),
            interest_amount=interest.interest_amount,
            request_key="reverse-interest",
            request_fingerprint="reverse-interest",
            reversal_of=interest,
            reason="Correct interest evidence",
        )
        self.assertEqual(reversal.reversal_of_id, interest.pk)

    def test_database_rejects_invalid_pledge_source_and_double_pledge(self):
        first_loan = self.create_funding_loan("FIRST")
        _, _, first_pledge = self.create_activation_evidence(first_loan)

        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingPledgeItem.objects.bulk_create(
                [
                    FundingPledgeItem(
                        funding_pledge=first_pledge,
                        collateral_item=self.collateral,
                        source_pawn_loan_id=self.pawn_loan.pk + 1000,
                        selected_collateral_value=Decimal("10000.0000"),
                        valuation_fingerprint="wrong-source",
                    )
                ]
            )

        self.create_pledge_item(first_pledge)
        second_loan = self.create_funding_loan("SECOND")
        _, _, second_pledge = self.create_activation_evidence(second_loan)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FundingPledgeItem.objects.bulk_create(
                [
                    FundingPledgeItem(
                        funding_pledge=second_pledge,
                        collateral_item=self.collateral,
                        source_pawn_loan_id=self.pawn_loan.pk,
                        selected_collateral_value=Decimal("10000.0000"),
                        valuation_fingerprint="duplicate-active",
                    )
                ]
            )

    def test_funding_pledge_custody_source_updates_shared_projection(self):
        funding_loan = self.create_funding_loan()
        _, _, pledge = self.create_activation_evidence(funding_loan)
        self.create_pledge_item(pledge)

        with transaction.atomic():
            event = PawnCollateralCustodyEvent.objects.create(
                collateral_item=self.collateral,
                funding_pledge=pledge,
                from_state=CollateralCustodyState.IN_VAULT.value,
                to_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
                effective_date=date(2026, 8, 8),
                actor=self.actor,
            )
            self.collateral.custody_state = CollateralCustodyState.WITH_FUNDING_LENDER.value
            self.collateral.save(update_fields=["custody_state", "updated_at"])

        self.assertEqual(event.funding_pledge_id, pledge.pk)
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnCollateralCustodyEvent.objects.filter(pk=event.pk).update(
                effective_date=date(2026, 8, 9)
            )

    def test_funding_return_requires_evidence_and_updates_both_projections(self):
        funding_loan = self.create_funding_loan()
        _, _, pledge = self.create_activation_evidence(funding_loan)
        pledge_item = self.create_pledge_item(pledge)
        self.collateral.custody_state = CollateralCustodyState.WITH_FUNDING_LENDER.value
        self.collateral.save(update_fields=["custody_state", "updated_at"])

        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingPledgeItem.objects.filter(pk=pledge_item.pk).update(
                released_at=timezone.now()
            )

        funding_return = FundingReturn.objects.create(
            workspace=self.tenant,
            funding_loan=funding_loan,
            effective_date=date(2026, 9, 8),
            request_key="return-request",
            request_fingerprint="return-fingerprint",
            principal_outstanding=Decimal("0.0000"),
            retained_collateral_value=Decimal("0.0000"),
            evidence_snapshot={"settled": True},
            actor=self.actor,
        )
        with transaction.atomic():
            FundingReturnItem.objects.create(
                funding_return=funding_return,
                pledge_item=pledge_item,
                evidence_snapshot={"returned": True},
            )
            FundingPledgeItem.objects.filter(pk=pledge_item.pk).update(
                released_at=timezone.now()
            )
            PawnCollateralCustodyEvent.objects.create(
                collateral_item=self.collateral,
                funding_return=funding_return,
                from_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
                to_state=CollateralCustodyState.IN_VAULT.value,
                effective_date=date(2026, 9, 8),
                actor=self.actor,
            )
            self.collateral.custody_state = CollateralCustodyState.IN_VAULT.value
            self.collateral.save(update_fields=["custody_state", "updated_at"])

        pledge_item.refresh_from_db()
        self.collateral.refresh_from_db()
        self.assertIsNotNone(pledge_item.released_at)
        self.assertEqual(
            self.collateral.custody_state,
            CollateralCustodyState.IN_VAULT.value,
        )

    def test_database_rejects_custody_event_without_projection_update(self):
        funding_loan = self.create_funding_loan()
        _, _, pledge = self.create_activation_evidence(funding_loan)
        self.create_pledge_item(pledge)

        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnCollateralCustodyEvent.objects.create(
                collateral_item=self.collateral,
                funding_pledge=pledge,
                from_state=CollateralCustodyState.IN_VAULT.value,
                to_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
                effective_date=date(2026, 8, 8),
                actor=self.actor,
            )
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")

    def test_database_enforces_exact_latest_funding_custody_reversal(self):
        funding_loan = self.create_funding_loan()
        _, _, pledge = self.create_activation_evidence(funding_loan)
        pledge_item = self.create_pledge_item(pledge)
        with transaction.atomic():
            PawnCollateralCustodyEvent.objects.create(
                collateral_item=self.collateral,
                funding_pledge=pledge,
                from_state=CollateralCustodyState.IN_VAULT.value,
                to_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
                effective_date=date(2026, 8, 8),
                actor=self.actor,
            )
            self.collateral.custody_state = CollateralCustodyState.WITH_FUNDING_LENDER.value
            self.collateral.save(update_fields=["custody_state", "updated_at"])
        funding_return = FundingReturn.objects.create(
            workspace=self.tenant,
            funding_loan=funding_loan,
            effective_date=date(2026, 9, 8),
            request_key="return-before-guard-reversal",
            request_fingerprint="return-before-guard-reversal",
            principal_outstanding=Decimal("0.0000"),
            retained_collateral_value=Decimal("0.0000"),
            evidence_snapshot={"source": "database guard test"},
            actor=self.actor,
        )
        with transaction.atomic():
            FundingReturnItem.objects.create(
                funding_return=funding_return,
                pledge_item=pledge_item,
                evidence_snapshot={"source": "database guard test"},
            )
            FundingPledgeItem.objects.filter(pk=pledge_item.pk).update(
                released_at=timezone.now()
            )
            PawnCollateralCustodyEvent.objects.create(
                collateral_item=self.collateral,
                funding_return=funding_return,
                from_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
                to_state=CollateralCustodyState.IN_VAULT.value,
                effective_date=date(2026, 9, 8),
                actor=self.actor,
            )
            self.collateral.custody_state = CollateralCustodyState.IN_VAULT.value
            self.collateral.save(update_fields=["custody_state", "updated_at"])

        pledge_reversal = FundingPledgeReversal.objects.create(
            funding_pledge=pledge,
            effective_date=date(2026, 9, 9),
            request_key="late-pledge-reversal",
            request_fingerprint="late-pledge-reversal",
            reason="Database guard test",
            actor=self.actor,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnCollateralCustodyEvent.objects.bulk_create(
                [
                    PawnCollateralCustodyEvent(
                        collateral_item=self.collateral,
                        funding_pledge=pledge,
                        funding_pledge_reversal=pledge_reversal,
                        from_state=CollateralCustodyState.IN_VAULT.value,
                        to_state=CollateralCustodyState.WITH_FUNDING_LENDER.value,
                        effective_date=date(2026, 9, 9),
                    )
                ]
            )

        return_reversal = FundingReturnReversal.objects.create(
            funding_return=funding_return,
            effective_date=date(2026, 9, 9),
            request_key="return-guard-reversal",
            request_fingerprint="return-guard-reversal",
            reason="Database guard test",
            actor=self.actor,
        )
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnCollateralCustodyEvent.objects.bulk_create(
                [
                    PawnCollateralCustodyEvent(
                        collateral_item=self.collateral,
                        funding_return=funding_return,
                        funding_return_reversal=return_reversal,
                        from_state=CollateralCustodyState.IN_VAULT.value,
                        to_state=CollateralCustodyState.AUCTION_DISPOSED.value,
                        effective_date=date(2026, 9, 9),
                    )
                ]
            )

        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingReturnReversal.objects.filter(pk=return_reversal.pk).update(
                reason="Mutated"
            )
