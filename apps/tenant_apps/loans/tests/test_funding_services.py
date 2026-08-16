import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import DatabaseError, close_old_connections, connection, transaction
from django.test import TransactionTestCase
from apps.tenancy.testing import WorkspaceTestCase
from apps.tenancy.context import without_workspace_context, workspace_context

from apps.orgs.models import Company, Domain
from apps.tenant_apps.loans.domain import CollateralCustodyState, CollateralMetal, PawnLoanState
from apps.tenant_apps.loans.domain.future_funding import FundingLoanState
from apps.tenant_apps.loans.models import (
    FundingLoan,
    FundingLoanCancellation,
    FundingLoanDraftCollateral,
    FundingLoanDraftTerms,
    FundingLoanEvent,
    FundingLoanSequence,
    FundingLoanTermsSnapshot,
    FundingPledge,
    FundingPledgeItem,
    FundingPledgeReversal,
    LoanLicense,
    LoanSeries,
    PawnCollateralCustodyEvent,
    PawnCollateralItem,
    PawnLoan,
)
from apps.tenant_apps.loans.services import (
    AccrueFundingInterest,
    ActivateFundingLoan,
    ActivateSavedFundingLoanDraft,
    AssessFundingFee,
    BeginFundingSettlement,
    CancelFundingLoanDraft,
    CloseFundingLoan,
    CreateFundingLoanDraft,
    FundingCollateralInput,
    FundingLoanServiceError,
    RecordFundingRepayment,
    ReverseFundingEvent,
    ReverseFundingPledge,
    ReverseFundingReturn,
    SaveFundingLoanDraftInputs,
    ReturnFundingCollateral,
    accrue_funding_interest,
    activate_funding_loan,
    activate_saved_funding_loan_draft,
    assess_funding_fee,
    begin_funding_settlement,
    cancel_funding_loan_draft,
    close_funding_loan,
    create_funding_loan_draft,
    record_funding_repayment,
    reverse_funding_event,
    reverse_funding_pledge,
    reverse_funding_return,
    return_funding_collateral,
    save_funding_loan_draft_inputs,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version
from apps.tenant_apps.loans.selectors import (
    FundingLoanSelectorError,
    get_funding_loan_detail,
    get_funding_loan_integrity_findings,
    get_funding_loan_summaries,
)


class FailingOutboundAdapter:
    def record(self, *, funding_loan_id, operation):
        raise RuntimeError(f"delivery failed for {funding_loan_id}:{operation}")


class FundingLoanServiceTests(WorkspaceTestCase):
    test_schema_name = f"funding_services_{uuid.uuid4().hex[:8]}"
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
            username="funding-service-owner",
            defaults={"email": "funding-service-owner@example.com"},
        )
        tenant.name = f"Funding Service {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        self.actor = get_user_model().objects.create_user(
            username=f"funding-service-{uuid.uuid4().hex[:8]}",
            email=f"funding-service-{uuid.uuid4().hex[:8]}@example.com",
        )
        self.lender = Party.objects.create(
            display_name="Funding lender",
            status=Party.PartyStatus.ACTIVE,
        )
        self.borrower = Party.objects.create(
            display_name="Pawn borrower",
            status=Party.PartyStatus.ACTIVE,
        )
        self.license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Funding service license",
            license_number=f"FSL-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        self.series = LoanSeries.objects.create(
            license=self.license,
            name="Main",
            code="FS",
        )
        self.first_loan, self.first_item = self._pawn_loan("ONE", Decimal("6000"))
        self.second_loan, self.second_item = self._pawn_loan("TWO", Decimal("4000"))

    def _pawn_loan(self, suffix, appraisal):
        loan = PawnLoan.objects.create(
            workspace=self.tenant,
            product_version=ensure_test_product_version(self.tenant),
            license=self.license,
            series=self.series,
            borrower=self.borrower,
            loan_number=f"PL-{suffix}-{uuid.uuid4().hex[:6]}",
            state=PawnLoanState.ACTIVE.value,
            principal_amount=Decimal("3000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 8, 1),
            tenure_months=3,
        )
        item = PawnCollateralItem.objects.create(
            loan=loan,
            description=f"Gold {suffix}",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10.0000"),
            net_weight=Decimal("9.0000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=appraisal,
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        return loan, item

    def _draft(self):
        return create_funding_loan_draft(
            CreateFundingLoanDraft(
                workspace_id=self.tenant.pk,
                lender_id=self.lender.pk,
            ),
            actor=self.actor,
        )

    def _activation(self, funding_loan, **changes):
        values = {
            "workspace_id": self.tenant.pk,
            "funding_loan_id": funding_loan.pk,
            "principal_amount": Decimal("7000.00"),
            "monthly_interest_rate": Decimal("1.500000"),
            "activated_on": date(2026, 8, 8),
            "maturity_on": date(2026, 11, 8),
            "maximum_funding_ltv_ratio": Decimal("0.800000"),
            "currency_quantum": Decimal("0.0100"),
            "collateral": (
                FundingCollateralInput(self.second_item.pk, Decimal("4000.00")),
                FundingCollateralInput(self.first_item.pk, Decimal("6000.00")),
            ),
            "request_key": "activate-funding-1",
        }
        values.update(changes)
        return ActivateFundingLoan(**values)

    def test_draft_allocates_workspace_sequence_and_cancel_is_idempotent(self):
        first = self._draft()
        second = self._draft()

        self.assertEqual(first.funding_number, "FL-000001")
        self.assertEqual(second.funding_number, "FL-000002")
        sequence = FundingLoanSequence.objects.get(workspace=self.tenant)
        self.assertEqual(sequence.next_value, 3)

        cancelled = cancel_funding_loan_draft(
            CancelFundingLoanDraft(self.tenant.pk, first.pk, "Facility withdrawn"),
            actor=self.actor,
        )
        repeated = cancel_funding_loan_draft(
            CancelFundingLoanDraft(self.tenant.pk, first.pk, "Ignored replay reason"),
            actor=self.actor,
        )
        self.assertEqual(cancelled.state, FundingLoanState.CANCELLED.value)
        self.assertEqual(repeated.pk, cancelled.pk)
        cancellation = FundingLoanCancellation.objects.get(funding_loan=first)
        self.assertEqual(cancellation.reason, "Facility withdrawn")
        self.assertEqual(cancellation.actor, self.actor)
        with self.assertRaises(DatabaseError), transaction.atomic():
            FundingLoanCancellation.objects.filter(pk=cancellation.pk).update(
                reason="Rewritten"
            )

    def test_draft_inputs_are_editable_and_policy_validated_before_activation(self):
        funding_loan = self._draft()
        command = SaveFundingLoanDraftInputs(
            workspace_id=self.tenant.pk,
            funding_loan_id=funding_loan.pk,
            principal_amount=Decimal("7000.00"),
            monthly_interest_rate=Decimal("1.500000"),
            activated_on=date(2026, 8, 8),
            maturity_on=date(2026, 11, 8),
            maximum_funding_ltv_ratio=Decimal("0.800000"),
            currency_quantum=Decimal("0.0100"),
            collateral=(
                FundingCollateralInput(self.first_item.pk, Decimal("6000.00")),
                FundingCollateralInput(self.second_item.pk, Decimal("4000.00")),
            ),
        )

        readiness = save_funding_loan_draft_inputs(command, actor=self.actor)

        self.assertTrue(readiness.ready)
        terms = FundingLoanDraftTerms.objects.get(funding_loan=funding_loan)
        self.assertEqual(terms.principal_amount, Decimal("7000.0000"))
        self.assertEqual(terms.updated_by, self.actor)
        self.assertEqual(
            set(FundingLoanDraftCollateral.objects.values_list("collateral_item_id", flat=True)),
            {self.first_item.pk, self.second_item.pk},
        )
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)
        self.assertFalse(hasattr(funding_loan, "terms_snapshot"))
        self.assertFalse(hasattr(funding_loan, "pledge"))
        self.first_item.refresh_from_db()
        self.assertEqual(self.first_item.custody_state, CollateralCustodyState.IN_VAULT.value)

        invalid = SaveFundingLoanDraftInputs(
            **{
                **command.__dict__,
                "principal_amount": Decimal("9000.00"),
            }
        )
        with self.assertRaisesRegex(FundingLoanServiceError, "LTV"):
            save_funding_loan_draft_inputs(invalid, actor=self.actor)
        terms.refresh_from_db()
        self.assertEqual(terms.principal_amount, Decimal("7000.0000"))

    def test_saved_draft_activation_consumes_inputs_and_revalidates_stale_collateral(self):
        funding_loan = self._draft()
        save_funding_loan_draft_inputs(
            SaveFundingLoanDraftInputs(
                workspace_id=self.tenant.pk,
                funding_loan_id=funding_loan.pk,
                principal_amount=Decimal("7000.00"),
                monthly_interest_rate=Decimal("1.500000"),
                activated_on=date(2026, 8, 8),
                maturity_on=date(2026, 11, 8),
                maximum_funding_ltv_ratio=Decimal("0.800000"),
                currency_quantum=Decimal("0.0100"),
                collateral=(
                    FundingCollateralInput(self.first_item.pk, Decimal("6000.00")),
                    FundingCollateralInput(self.second_item.pk, Decimal("4000.00")),
                ),
            ),
            actor=self.actor,
        )
        self.first_item.custody_state = CollateralCustodyState.WITH_CUSTOMER.value
        self.first_item.save(update_fields=["custody_state"])

        with self.assertRaisesRegex(FundingLoanServiceError, "branch vault"):
            activate_saved_funding_loan_draft(
                ActivateSavedFundingLoanDraft(self.tenant.pk, funding_loan.pk),
                actor=self.actor,
            )

        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)
        self.assertTrue(FundingLoanDraftTerms.objects.filter(funding_loan=funding_loan).exists())
        self.assertEqual(FundingLoanDraftCollateral.objects.filter(funding_loan=funding_loan).count(), 2)
        self.assertFalse(FundingLoanTermsSnapshot.objects.filter(funding_loan=funding_loan).exists())
        self.first_item.custody_state = CollateralCustodyState.IN_VAULT.value
        self.first_item.save(update_fields=["custody_state"])

        result = activate_saved_funding_loan_draft(
            ActivateSavedFundingLoanDraft(self.tenant.pk, funding_loan.pk),
            actor=self.actor,
        )

        self.assertFalse(result.already_activated)
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.ACTIVE.value)
        self.assertFalse(FundingLoanDraftTerms.objects.filter(funding_loan=funding_loan).exists())
        self.assertFalse(FundingLoanDraftCollateral.objects.filter(funding_loan=funding_loan).exists())
        self.assertEqual(result.event.actor, self.actor)
        self.assertEqual(result.pledge.actor, self.actor)
        self.first_item.refresh_from_db()
        self.second_item.refresh_from_db()
        self.assertEqual(self.first_item.custody_state, CollateralCustodyState.WITH_FUNDING_LENDER.value)
        self.assertEqual(self.second_item.custody_state, CollateralCustodyState.WITH_FUNDING_LENDER.value)

    def test_cancelling_draft_requires_reason(self):
        funding_loan = self._draft()

        with self.assertRaisesRegex(FundingLoanServiceError, "reason"):
            cancel_funding_loan_draft(
                CancelFundingLoanDraft(self.tenant.pk, funding_loan.pk, " "),
                actor=self.actor,
            )

        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)
        self.assertFalse(FundingLoanCancellation.objects.exists())

    def test_bounded_sequence_allocates_maximum_once_then_fails_closed(self):
        FundingLoanSequence.objects.create(
            workspace=self.tenant,
            prefix="CAP-",
            width=2,
            next_value=2,
            maximum_value=2,
        )

        maximum = self._draft()
        self.assertEqual(maximum.funding_number, "CAP-02")
        with self.assertRaisesRegex(FundingLoanServiceError, "exhausted"):
            self._draft()

        sequence = FundingLoanSequence.objects.get(workspace=self.tenant)
        self.assertEqual(sequence.next_value, 3)

    def test_activation_is_atomic_across_multiple_pawn_loans_and_replays(self):
        funding_loan = self._draft()
        command = self._activation(funding_loan)

        result = activate_funding_loan(command, actor=self.actor)
        repeated = activate_funding_loan(
            self._activation(
                funding_loan,
                collateral=tuple(reversed(command.collateral)),
            ),
            actor=self.actor,
        )

        funding_loan.refresh_from_db()
        self.first_item.refresh_from_db()
        self.second_item.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.ACTIVE.value)
        self.assertFalse(result.already_activated)
        self.assertTrue(repeated.already_activated)
        self.assertEqual(repeated.event.pk, result.event.pk)
        self.assertEqual(FundingLoanTermsSnapshot.objects.filter(funding_loan=funding_loan).count(), 1)
        self.assertEqual(FundingLoanEvent.objects.filter(funding_loan=funding_loan).count(), 1)
        self.assertEqual(FundingPledge.objects.filter(funding_loan=funding_loan).count(), 1)
        self.assertEqual(FundingPledgeItem.objects.filter(funding_pledge=result.pledge).count(), 2)
        self.assertEqual(result.pledge.total_collateral_value, Decimal("10000.0000"))
        self.assertEqual(result.pledge.maximum_funded_amount, Decimal("8000.0000"))
        self.assertEqual(PawnCollateralCustodyEvent.objects.filter(funding_pledge=result.pledge).count(), 2)
        self.assertEqual(self.first_item.custody_state, CollateralCustodyState.WITH_FUNDING_LENDER.value)
        self.assertEqual(self.second_item.custody_state, CollateralCustodyState.WITH_FUNDING_LENDER.value)

    def test_activation_request_key_reuse_with_changed_input_fails(self):
        funding_loan = self._draft()
        activate_funding_loan(self._activation(funding_loan), actor=self.actor)

        with self.assertRaisesRegex(FundingLoanServiceError, "different input"):
            activate_funding_loan(
                self._activation(
                    funding_loan,
                    monthly_interest_rate=Decimal("1.600000"),
                ),
                actor=self.actor,
            )

    def test_activation_failure_rolls_back_every_operational_fact(self):
        funding_loan = self._draft()

        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            activate_funding_loan(
                self._activation(funding_loan),
                actor=self.actor,
                outbound=FailingOutboundAdapter(),
            )

        funding_loan.refresh_from_db()
        self.first_item.refresh_from_db()
        self.second_item.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)
        self.assertFalse(FundingLoanTermsSnapshot.objects.exists())
        self.assertFalse(FundingLoanEvent.objects.exists())
        self.assertFalse(FundingPledge.objects.exists())
        self.assertFalse(FundingPledgeItem.objects.exists())
        self.assertFalse(PawnCollateralCustodyEvent.objects.filter(funding_pledge__isnull=False).exists())
        self.assertEqual(self.first_item.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertEqual(self.second_item.custody_state, CollateralCustodyState.IN_VAULT.value)

    def test_activation_rejects_wrong_workspace_inactive_party_and_ltv(self):
        with self.assertRaisesRegex(FundingLoanServiceError, "active tenant"):
            create_funding_loan_draft(
                CreateFundingLoanDraft(self.tenant.pk + 1, self.lender.pk),
                actor=self.actor,
            )
        inactive = Party.objects.create(
            display_name="Inactive lender",
            status=Party.PartyStatus.INACTIVE,
        )
        with self.assertRaisesRegex(FundingLoanServiceError, "active Party"):
            create_funding_loan_draft(
                CreateFundingLoanDraft(self.tenant.pk, inactive.pk),
                actor=self.actor,
            )

        funding_loan = self._draft()
        with self.assertRaisesRegex(FundingLoanServiceError, "LTV"):
            activate_funding_loan(
                self._activation(funding_loan, principal_amount=Decimal("9000.00")),
                actor=self.actor,
            )
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.DRAFT.value)

    def test_complete_operational_lifecycle_closes_without_accounting(self):
        funding_loan = self._draft()
        activate_funding_loan(self._activation(funding_loan), actor=self.actor)

        interest = accrue_funding_interest(
            AccrueFundingInterest(
                self.tenant.pk,
                funding_loan.pk,
                periods=1,
                effective_date=date(2026, 9, 8),
                request_key="interest-1",
            ),
            actor=self.actor,
        )
        fee = assess_funding_fee(
            AssessFundingFee(
                self.tenant.pk,
                funding_loan.pk,
                amount=Decimal("100.00"),
                effective_date=date(2026, 9, 8),
                request_key="fee-1",
            ),
            actor=self.actor,
        )
        repayment_command = RecordFundingRepayment(
            self.tenant.pk,
            funding_loan.pk,
            amount=Decimal("7205.00"),
            effective_date=date(2026, 10, 8),
            request_key="repayment-1",
        )
        repayment = record_funding_repayment(repayment_command, actor=self.actor)
        replay = record_funding_repayment(repayment_command, actor=self.actor)

        self.assertEqual(interest.interest_amount, Decimal("105.0000"))
        self.assertEqual(fee.fee_amount, Decimal("100.0000"))
        self.assertEqual(repayment.fee_amount, Decimal("100.0000"))
        self.assertEqual(repayment.interest_amount, Decimal("105.0000"))
        self.assertEqual(repayment.principal_amount, Decimal("7000.0000"))
        self.assertEqual(replay.pk, repayment.pk)

        begin_funding_settlement(
            BeginFundingSettlement(self.tenant.pk, funding_loan.pk),
            actor=self.actor,
        )
        with self.assertRaisesRegex(FundingLoanServiceError, "return to the branch vault"):
            close_funding_loan(
                CloseFundingLoan(self.tenant.pk, funding_loan.pk), actor=self.actor
            )

        return_command = ReturnFundingCollateral(
            self.tenant.pk,
            funding_loan.pk,
            collateral_item_ids=(self.second_item.pk, self.first_item.pk),
            effective_date=date(2026, 10, 8),
            request_key="return-all-1",
        )
        funding_return = return_funding_collateral(return_command, actor=self.actor)
        replayed_return = return_funding_collateral(
            ReturnFundingCollateral(
                self.tenant.pk,
                funding_loan.pk,
                collateral_item_ids=(self.first_item.pk, self.second_item.pk),
                effective_date=date(2026, 10, 8),
                request_key="return-all-1",
            ),
            actor=self.actor,
        )
        closed = close_funding_loan(
            CloseFundingLoan(self.tenant.pk, funding_loan.pk), actor=self.actor
        )

        self.assertEqual(replayed_return.pk, funding_return.pk)
        self.assertEqual(funding_return.items.count(), 2)
        self.assertEqual(closed.state, FundingLoanState.CLOSED.value)
        self.assertFalse(
            FundingPledgeItem.objects.filter(
                funding_pledge__funding_loan=funding_loan,
                released_at__isnull=True,
            ).exists()
        )
        self.assertEqual(
            PawnCollateralCustodyEvent.objects.filter(
                funding_return=funding_return
            ).count(),
            2,
        )

    def test_partial_return_enforces_retained_collateral_ltv(self):
        funding_loan = self._draft()
        activate_funding_loan(self._activation(funding_loan), actor=self.actor)

        with self.assertRaisesRegex(FundingLoanServiceError, "fully settled"):
            begin_funding_settlement(
                BeginFundingSettlement(self.tenant.pk, funding_loan.pk),
                actor=self.actor,
            )
        funding_loan.refresh_from_db()
        self.assertEqual(funding_loan.state, FundingLoanState.ACTIVE.value)

        with self.assertRaisesRegex(FundingLoanServiceError, "LTV"):
            return_funding_collateral(
                ReturnFundingCollateral(
                    self.tenant.pk,
                    funding_loan.pk,
                    collateral_item_ids=(self.first_item.pk,),
                    effective_date=date(2026, 9, 1),
                    request_key="return-too-soon",
                ),
                actor=self.actor,
            )

        record_funding_repayment(
            RecordFundingRepayment(
                self.tenant.pk,
                funding_loan.pk,
                amount=Decimal("4000.00"),
                effective_date=date(2026, 9, 2),
                request_key="principal-repayment-1",
            ),
            actor=self.actor,
        )
        funding_return = return_funding_collateral(
            ReturnFundingCollateral(
                self.tenant.pk,
                funding_loan.pk,
                collateral_item_ids=(self.second_item.pk,),
                effective_date=date(2026, 9, 2),
                request_key="partial-return-1",
            ),
            actor=self.actor,
        )

        self.assertEqual(funding_return.principal_outstanding, Decimal("3000.0000"))
        self.assertEqual(funding_return.retained_collateral_value, Decimal("6000.0000"))
        self.assertEqual(funding_return.retained_ltv_ratio, Decimal("0.500000"))

    def test_financial_reversal_is_exact_newest_first_and_idempotent(self):
        funding_loan = self._draft()
        activate_funding_loan(self._activation(funding_loan), actor=self.actor)
        interest = accrue_funding_interest(
            AccrueFundingInterest(
                self.tenant.pk,
                funding_loan.pk,
                periods=1,
                effective_date=date(2026, 9, 8),
                request_key="interest-to-reverse",
            ),
            actor=self.actor,
        )
        fee = assess_funding_fee(
            AssessFundingFee(
                self.tenant.pk,
                funding_loan.pk,
                amount=Decimal("75.00"),
                effective_date=date(2026, 9, 8),
                request_key="fee-to-reverse",
            ),
            actor=self.actor,
        )

        with self.assertRaisesRegex(FundingLoanServiceError, "Later FundingLoan"):
            reverse_funding_event(
                ReverseFundingEvent(
                    self.tenant.pk,
                    funding_loan.pk,
                    original_event_id=interest.pk,
                    effective_date=date(2026, 9, 9),
                    reason="Interest was entered in error",
                    request_key="reverse-interest-too-soon",
                ),
                actor=self.actor,
            )

        command = ReverseFundingEvent(
            self.tenant.pk,
            funding_loan.pk,
            original_event_id=fee.pk,
            effective_date=date(2026, 9, 9),
            reason="Fee was entered in error",
            request_key="reverse-fee-1",
        )
        reversal = reverse_funding_event(command, actor=self.actor)
        replay = reverse_funding_event(command, actor=self.actor)

        self.assertEqual(replay.pk, reversal.pk)
        self.assertEqual(reversal.reversal_of_id, fee.pk)
        self.assertEqual(reversal.fee_amount, fee.fee_amount)
        self.assertEqual(reversal.principal_amount, Decimal("0.0000"))
        self.assertEqual(reversal.interest_amount, Decimal("0.0000"))
        with self.assertRaisesRegex(FundingLoanServiceError, "different input"):
            reverse_funding_event(
                ReverseFundingEvent(
                    self.tenant.pk,
                    funding_loan.pk,
                    original_event_id=fee.pk,
                    effective_date=date(2026, 9, 9),
                    reason="A changed correction reason",
                    request_key="reverse-fee-1",
                ),
                actor=self.actor,
            )

    def test_financial_reversal_failure_rolls_back_and_activation_is_excluded(self):
        funding_loan = self._draft()
        activation = activate_funding_loan(
            self._activation(funding_loan), actor=self.actor
        ).event
        fee = assess_funding_fee(
            AssessFundingFee(
                self.tenant.pk,
                funding_loan.pk,
                amount=Decimal("50.00"),
                effective_date=date(2026, 9, 8),
                request_key="fee-rollback",
            ),
            actor=self.actor,
        )

        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            reverse_funding_event(
                ReverseFundingEvent(
                    self.tenant.pk,
                    funding_loan.pk,
                    original_event_id=fee.pk,
                    effective_date=date(2026, 9, 9),
                    reason="Rollback correction",
                    request_key="reverse-fee-rollback",
                ),
                actor=self.actor,
                outbound=FailingOutboundAdapter(),
            )
        self.assertFalse(
            FundingLoanEvent.objects.filter(reversal_of=fee).exists()
        )

        with self.assertRaisesRegex(FundingLoanServiceError, "activation cannot"):
            reverse_funding_event(
                ReverseFundingEvent(
                    self.tenant.pk,
                    funding_loan.pk,
                    original_event_id=activation.pk,
                    effective_date=date(2026, 9, 9),
                    reason="Invalid activation correction",
                    request_key="reverse-activation",
                ),
                actor=self.actor,
            )

    def test_return_reversal_restores_pledge_and_allows_corrected_return(self):
        funding_loan = self._draft()
        activate_funding_loan(self._activation(funding_loan), actor=self.actor)
        record_funding_repayment(
            RecordFundingRepayment(
                self.tenant.pk,
                funding_loan.pk,
                amount=Decimal("7000.00"),
                effective_date=date(2026, 9, 1),
                request_key="settle-for-return-reversal",
            ),
            actor=self.actor,
        )
        funding_return = return_funding_collateral(
            ReturnFundingCollateral(
                self.tenant.pk,
                funding_loan.pk,
                collateral_item_ids=(self.first_item.pk,),
                effective_date=date(2026, 9, 2),
                request_key="return-before-correction",
            ),
            actor=self.actor,
        )
        command = ReverseFundingReturn(
            self.tenant.pk,
            funding_loan.pk,
            funding_return_id=funding_return.pk,
            effective_date=date(2026, 9, 3),
            reason="Return receipt was issued in error",
            request_key="reverse-return-1",
        )

        reversal = reverse_funding_return(command, actor=self.actor)
        replay = reverse_funding_return(command, actor=self.actor)

        self.first_item.refresh_from_db()
        pledge_item = FundingPledgeItem.objects.get(
            funding_pledge__funding_loan=funding_loan,
            collateral_item=self.first_item,
        )
        self.assertEqual(replay.pk, reversal.pk)
        self.assertIsNone(pledge_item.released_at)
        self.assertEqual(
            self.first_item.custody_state,
            CollateralCustodyState.WITH_FUNDING_LENDER.value,
        )
        inverse = PawnCollateralCustodyEvent.objects.get(
            funding_return_reversal=reversal
        )
        self.assertEqual(inverse.funding_return_id, funding_return.pk)
        self.assertEqual(inverse.from_state, CollateralCustodyState.IN_VAULT.value)
        self.assertEqual(
            inverse.to_state,
            CollateralCustodyState.WITH_FUNDING_LENDER.value,
        )

        corrected = return_funding_collateral(
            ReturnFundingCollateral(
                self.tenant.pk,
                funding_loan.pk,
                collateral_item_ids=(self.first_item.pk,),
                effective_date=date(2026, 9, 4),
                request_key="corrected-return",
            ),
            actor=self.actor,
        )
        self.assertNotEqual(corrected.pk, funding_return.pk)
        with self.assertRaisesRegex(FundingLoanServiceError, "different input"):
            reverse_funding_return(
                ReverseFundingReturn(
                    self.tenant.pk,
                    funding_loan.pk,
                    funding_return_id=funding_return.pk,
                    effective_date=date(2026, 9, 3),
                    reason="Changed reason",
                    request_key="reverse-return-1",
                ),
                actor=self.actor,
            )

    def test_pledge_reversal_requires_settlement_and_is_exact(self):
        funding_loan = self._draft()
        result = activate_funding_loan(self._activation(funding_loan), actor=self.actor)
        with self.assertRaisesRegex(FundingLoanServiceError, "settlement pending"):
            reverse_funding_pledge(
                ReverseFundingPledge(
                    self.tenant.pk,
                    funding_loan.pk,
                    effective_date=date(2026, 9, 1),
                    reason="Activation handoff was invalid",
                    request_key="reverse-pledge-too-soon",
                ),
                actor=self.actor,
            )
        record_funding_repayment(
            RecordFundingRepayment(
                self.tenant.pk,
                funding_loan.pk,
                amount=Decimal("7000.00"),
                effective_date=date(2026, 9, 1),
                request_key="settle-for-pledge-reversal",
            ),
            actor=self.actor,
        )
        begin_funding_settlement(
            BeginFundingSettlement(self.tenant.pk, funding_loan.pk), actor=self.actor
        )
        command = ReverseFundingPledge(
            self.tenant.pk,
            funding_loan.pk,
            effective_date=date(2026, 9, 2),
            reason="Activation handoff was invalid",
            request_key="reverse-pledge-1",
        )

        reversal = reverse_funding_pledge(command, actor=self.actor)
        replay = reverse_funding_pledge(command, actor=self.actor)

        self.first_item.refresh_from_db()
        self.second_item.refresh_from_db()
        self.assertEqual(replay.pk, reversal.pk)
        self.assertEqual(reversal.funding_pledge_id, result.pledge.pk)
        self.assertEqual(
            PawnCollateralCustodyEvent.objects.filter(
                funding_pledge_reversal=reversal
            ).count(),
            2,
        )
        self.assertFalse(
            FundingPledgeItem.objects.filter(
                funding_pledge=result.pledge, released_at__isnull=True
            ).exists()
        )
        self.assertEqual(self.first_item.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertEqual(self.second_item.custody_state, CollateralCustodyState.IN_VAULT.value)

    def test_return_reversal_outbound_failure_rolls_back_all_projections(self):
        funding_loan = self._draft()
        activate_funding_loan(self._activation(funding_loan), actor=self.actor)
        record_funding_repayment(
            RecordFundingRepayment(
                self.tenant.pk,
                funding_loan.pk,
                amount=Decimal("7000.00"),
                effective_date=date(2026, 9, 1),
                request_key="settle-for-return-rollback",
            ),
            actor=self.actor,
        )
        funding_return = return_funding_collateral(
            ReturnFundingCollateral(
                self.tenant.pk,
                funding_loan.pk,
                collateral_item_ids=(self.first_item.pk,),
                effective_date=date(2026, 9, 2),
                request_key="return-before-rollback",
            ),
            actor=self.actor,
        )

        with self.assertRaisesRegex(RuntimeError, "delivery failed"):
            reverse_funding_return(
                ReverseFundingReturn(
                    self.tenant.pk,
                    funding_loan.pk,
                    funding_return_id=funding_return.pk,
                    effective_date=date(2026, 9, 3),
                    reason="Rollback this correction",
                    request_key="reverse-return-rollback",
                ),
                actor=self.actor,
                outbound=FailingOutboundAdapter(),
            )

        self.first_item.refresh_from_db()
        pledge_item = FundingPledgeItem.objects.get(
            funding_pledge__funding_loan=funding_loan,
            collateral_item=self.first_item,
        )
        self.assertFalse(hasattr(funding_return, "reversal"))
        self.assertFalse(
            PawnCollateralCustodyEvent.objects.filter(
                funding_return_reversal__isnull=False
            ).exists()
        )
        self.assertIsNotNone(pledge_item.released_at)
        self.assertEqual(
            self.first_item.custody_state, CollateralCustodyState.IN_VAULT.value
        )

    def test_read_selectors_project_balance_collateral_timeline_and_integrity(self):
        funding_loan = self._draft()
        activate_funding_loan(self._activation(funding_loan), actor=self.actor)
        fee = assess_funding_fee(
            AssessFundingFee(
                self.tenant.pk,
                funding_loan.pk,
                amount=Decimal("80.00"),
                effective_date=date(2026, 9, 1),
                request_key="selector-fee",
            ),
            actor=self.actor,
        )
        before_correction = get_funding_loan_detail(funding_loan.pk)
        self.assertEqual(before_correction.financial_correction.source_id, fee.pk)
        reverse_funding_event(
            ReverseFundingEvent(
                self.tenant.pk,
                funding_loan.pk,
                original_event_id=fee.pk,
                effective_date=date(2026, 9, 2),
                reason="Selector correction",
                request_key="selector-fee-reversal",
            ),
            actor=self.actor,
        )

        summaries = get_funding_loan_summaries(states=(FundingLoanState.ACTIVE,))
        detail = get_funding_loan_detail(funding_loan.pk)
        findings = get_funding_loan_integrity_findings()

        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0].total_due, Decimal("7000.0000"))
        self.assertEqual(summaries[0].active_collateral_count, 2)
        self.assertEqual(detail.summary.funding_number, funding_loan.funding_number)
        self.assertEqual(len(detail.collateral), 2)
        self.assertTrue(any(row.operation == "PLEDGE" for row in detail.timeline))
        self.assertTrue(
            any(row.operation == "REVERSE_EVENT" and row.reversal for row in detail.timeline)
        )
        self.assertIsNone(detail.financial_correction)
        self.assertEqual(
            tuple((row.fee_effect, row.total_balance) for row in detail.statement),
            (
                (Decimal("0.0000"), Decimal("7000.0000")),
                (Decimal("80.0000"), Decimal("7080.0000")),
                (Decimal("-80.0000"), Decimal("7000.0000")),
            ),
        )
        self.assertEqual(findings, ())

        PawnCollateralItem.objects.filter(pk=self.first_item.pk).update(
            custody_state=CollateralCustodyState.IN_VAULT.value
        )
        try:
            findings = get_funding_loan_integrity_findings()
            self.assertEqual(
                {finding.code for finding in findings},
                {"COLLATERAL_PROJECTION", "CUSTODY_TIMELINE"},
            )
        finally:
            PawnCollateralItem.objects.filter(pk=self.first_item.pk).update(
                custody_state=CollateralCustodyState.WITH_FUNDING_LENDER.value
            )

    def test_read_selectors_reject_missing_tenant_and_unknown_loan(self):
        funding_loan = self._draft()
        with self.assertRaisesRegex(FundingLoanSelectorError, "not found"):
            get_funding_loan_detail(funding_loan.pk + 1000)

        with without_workspace_context():
            with self.assertRaisesRegex(FundingLoanSelectorError, "active tenant"):
                get_funding_loan_summaries()


class FundingLoanConcurrencyTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        token = uuid.uuid4().hex[:8]
        User = get_user_model()
        cls.owner = User.objects.create_user(username=f"funding-race-owner-{token}")
        cls.tenant = Company(
            schema_name=f"funding_race_{token}",
            name=f"Funding Race {token}",
            owner=cls.owner,
            creator=cls.owner,
        )
        cls.tenant.save()
        cls.domain = Domain.objects.create(
            tenant=cls.tenant,
            domain=f"{cls.tenant.schema_name}.test.com",
            is_primary=True,
        )

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.tenant.delete()
        super().tearDownClass()

    def _fixture_teardown(self):
        pass

    def setUp(self):
        context = workspace_context(self.tenant.pk)
        context.__enter__()
        token = uuid.uuid4().hex[:8]
        self.actor = get_user_model().objects.create_user(
            username=f"funding-race-actor-{token}"
        )
        self.lender = Party.objects.create(
            display_name="Concurrent funding lender",
            status=Party.PartyStatus.ACTIVE,
        )
        borrower = Party.objects.create(
            display_name="Concurrent pawn borrower",
            status=Party.PartyStatus.ACTIVE,
        )
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Concurrent funding license",
            license_number=f"FRC-{token}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        series = LoanSeries.objects.create(license=license, name="Race", code="FR")
        pawn_loan = PawnLoan.objects.create(
            workspace=self.tenant,
            product_version=ensure_test_product_version(self.tenant),
            license=license,
            series=series,
            borrower=borrower,
            loan_number=f"PL-RACE-{token}",
            state=PawnLoanState.ACTIVE.value,
            principal_amount=Decimal("3000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=date(2026, 8, 1),
            tenure_months=3,
        )
        self.collateral = PawnCollateralItem.objects.create(
            loan=pawn_loan,
            description="Concurrent gold",
            metal=CollateralMetal.GOLD.value,
            gross_weight=Decimal("10.0000"),
            net_weight=Decimal("9.0000"),
            purity_percentage=Decimal("91.6000"),
            latest_appraised_value=Decimal("10000.00"),
            custody_state=CollateralCustodyState.IN_VAULT.value,
        )
        self.drafts = tuple(
            create_funding_loan_draft(
                CreateFundingLoanDraft(self.tenant.pk, self.lender.pk),
                actor=self.actor,
            )
            for _ in range(2)
        )
        context.__exit__(None, None, None)

    def _activate_in_own_connection(self, funding_loan_id):
        close_old_connections()
        try:
            with workspace_context(self.tenant.pk):
                try:
                    result = activate_funding_loan(
                    ActivateFundingLoan(
                        workspace_id=self.tenant.pk,
                        funding_loan_id=funding_loan_id,
                        principal_amount=Decimal("7000.00"),
                        monthly_interest_rate=Decimal("1.500000"),
                        activated_on=date(2026, 8, 8),
                        maturity_on=date(2026, 11, 8),
                        maximum_funding_ltv_ratio=Decimal("0.800000"),
                        currency_quantum=Decimal("0.0100"),
                        collateral=(
                            FundingCollateralInput(
                                self.collateral.pk, Decimal("10000.00")
                            ),
                        ),
                        request_key=f"activate-race-{funding_loan_id}",
                    ),
                    actor=self.actor,
                )
                    return "OK", result.funding_loan.pk
                except FundingLoanServiceError as exc:
                    return "REJECTED", str(exc)
        finally:
            close_old_connections()

    def test_concurrent_double_pledge_has_exactly_one_winner(self):
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(
                executor.map(
                    self._activate_in_own_connection,
                    (self.drafts[0].pk, self.drafts[1].pk),
                )
            )

        self.collateral.refresh_from_db()
        self.assertEqual(
            sum(status == "OK" for status, _ in results), 1, msg=results
        )
        self.assertEqual(sum(status == "REJECTED" for status, _ in results), 1)
        self.assertEqual(
            FundingLoan.objects.filter(state=FundingLoanState.ACTIVE.value).count(),
            1,
        )
        self.assertEqual(
            FundingPledgeItem.objects.filter(released_at__isnull=True).count(), 1
        )
        self.assertEqual(
            self.collateral.custody_state,
            CollateralCustodyState.WITH_FUNDING_LENDER.value,
        )
