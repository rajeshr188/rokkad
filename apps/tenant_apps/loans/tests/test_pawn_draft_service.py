import uuid
from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.utils import timezone
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
    PawnLoanDisbursalSnapshot,
    PawnLoanInterestAccrualLine,
    PawnLoanPrincipalClosingLine,
    PawnLoanRepaymentAllocationLine,
)
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    PawnDraftError,
    UpdatePawnDraftCommand,
    approve_pawn_loan,
    append_collateral_photo,
    create_pawn_draft,
    create_pawn_loan_economic_policy,
    create_pawn_metal_interest_rate_policy,
    disburse_pawn_loan,
    finalize_pawn_loan_accrual,
    preview_pawn_loan_accruals,
    record_pawn_loan_repayment,
    release_pawn_loan_in_full,
    reverse_pawn_loan_event,
    update_pawn_draft,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.rates.models import Rate, RateSource


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

    def _add_photo(self, loan):
        for item in loan.collateral_items.all():
            append_collateral_photo(
                item.pk,
                upload=SimpleUploadedFile(
                    f"collateral-{item.pk}.jpg",
                    b"\xff\xd8\xff\xe0evidence",
                    content_type="image/jpeg",
                ),
                actor=self.actor,
            )

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

    def test_item_allocations_derive_mixed_metal_principal_and_effective_rate(self):
        self._economic_setup()
        command = self.command(
            principal_amount=Decimal("1.00"),
            monthly_interest_rate=Decimal("0"),
            collateral=(
                self.collateral(allocated_principal=Decimal("60000.00")),
                self.collateral(
                    description="Silver anklet",
                    metal=CollateralMetal.SILVER,
                    latest_appraised_value=Decimal("80000.00"),
                    allocated_principal=Decimal("40000.00"),
                ),
            ),
        )

        loan = create_pawn_draft(command, actor=self.actor)

        self.assertEqual(loan.principal_amount, Decimal("100000.00"))
        self.assertEqual(loan.monthly_interest_rate, Decimal("2.800000"))
        items = list(loan.collateral_items.order_by("pk"))
        self.assertEqual(items[0].monthly_interest_rate, Decimal("2.000000"))
        self.assertEqual(items[1].monthly_interest_rate, Decimal("4.000000"))
        self.assertTrue(all(item.interest_rate_policy_id for item in items))

    def test_item_allocation_above_its_own_ltv_fails_before_number_allocation(self):
        self._economic_setup()
        command = self.command(
            collateral=(
                self.collateral(allocated_principal=Decimal("96000.01")),
            )
        )

        with self.assertRaisesRegex(ValueError, "exceeds its maximum"):
            create_pawn_draft(command, actor=self.actor)

        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.next_number, 1)
        self.assertFalse(PawnLoan.objects.exists())

    def test_approval_revalidates_and_snapshots_item_economics(self):
        self._economic_setup()
        loan = create_pawn_draft(
            self.command(
                collateral=(
                    self.collateral(allocated_principal=Decimal("50000.00")),
                )
            ),
            actor=self.actor,
        )

        self._add_photo(loan)
        snapshot = approve_pawn_loan(loan.pk, actor=self.actor)

        self.assertEqual(
            snapshot.payload["collateral"][0]["allocated_principal"],
            "50000.00",
        )
        self.assertEqual(
            snapshot.payload["collateral_economics"]["monthly_interest"],
            "1000.00",
        )
        self.assertEqual(
            snapshot.payload["collateral_economics"]["net_disbursed"],
            "49000.00",
        )
        self.assertEqual(
            snapshot.payload["collateral_economics"]["tranches"][0][
                "maximum_principal"
            ],
            "96000.00",
        )

    @patch(
        "apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness"
    )
    def test_disbursal_freezes_approved_gross_net_and_tranche_evidence(self, readiness):
        self._economic_setup()
        loan = create_pawn_draft(
            self.command(
                collateral=(
                    self.collateral(allocated_principal=Decimal("50000.00")),
                )
            ),
            actor=self.actor,
        )
        self._add_photo(loan)
        approval = approve_pawn_loan(loan.pk, actor=self.actor)

        result = disburse_pawn_loan(
            loan.pk,
            effective_date=date(2026, 7, 18),
            actor=self.actor,
        )

        snapshot = PawnLoanDisbursalSnapshot.objects.get(loan=loan)
        self.assertEqual(snapshot.approval_snapshot, approval)
        self.assertEqual(snapshot.gross_principal, Decimal("50000.0000"))
        self.assertEqual(snapshot.advance_interest, Decimal("1000.0000"))
        self.assertEqual(snapshot.net_disbursed, Decimal("49000.0000"))
        self.assertEqual(snapshot.evidence["tranches"][0]["collateral_item_id"], loan.collateral_items.get().pk)
        self.assertEqual(result.accounting_event.payload["values"]["net_cash"], "49000")
        self.assertEqual(result.accounting_event.payload["values"]["advance_interest"], "1000")
        with self.assertRaisesRegex(ValidationError, "immutable"):
            snapshot.save()
        with self.assertRaisesRegex(ValidationError, "cannot be deleted"):
            snapshot.delete()
        readiness.assert_called_once()

    @patch(
        "apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness"
    )
    def test_item_accrual_consumes_advance_interest_once(self, _readiness):
        self._economic_setup()
        loan = create_pawn_draft(
            self.command(
                collateral=(
                    self.collateral(allocated_principal=Decimal("60000.00")),
                    self.collateral(
                        description="Silver anklet",
                        metal=CollateralMetal.SILVER,
                        latest_appraised_value=Decimal("80000.00"),
                        allocated_principal=Decimal("40000.00"),
                    ),
                )
            ),
            actor=self.actor,
        )
        self._add_photo(loan)
        approve_pawn_loan(loan.pk, actor=self.actor)
        posted = lambda _event: type(
            "Receipt", (), {"dea_voucher_id": None, "dea_journal_entry_id": None}
        )()
        with self.captureOnCommitCallbacks(execute=True):
            disburse_pawn_loan(
                loan.pk,
                effective_date=date(2026, 7, 18),
                actor=self.actor,
                delivery_handler=posted,
            )

        previews = preview_pawn_loan_accruals(
            loan.pk, as_of_date=date(2026, 9, 17), include_partial=False
        )
        self.assertEqual(len(previews), 2)
        self.assertEqual(previews[0].calculated_interest, Decimal("2800.00"))
        self.assertEqual(previews[0].advance_interest_applied, Decimal("2800.00"))
        self.assertEqual(previews[0].recognized_interest, Decimal("0.00"))
        self.assertEqual(previews[1].advance_interest_applied, Decimal("0.00"))
        self.assertEqual(previews[1].recognized_interest, Decimal("2800.00"))

        with patch(
            "apps.tenant_apps.loans.services.pawn_interest.timezone.localdate",
            return_value=date(2026, 8, 17),
        ):
            first = finalize_pawn_loan_accrual(
                loan.pk, period_number=1, actor=self.actor
            )
        self.assertIsNone(first.accounting_event)
        lines = list(first.accrual.lines.order_by("collateral_item_id"))
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            sum((line.calculated_interest for line in lines), Decimal("0")),
            Decimal("2800.00"),
        )
        self.assertEqual(
            sum((line.advance_interest_applied for line in lines), Decimal("0")),
            Decimal("2800.00"),
        )
        with self.assertRaisesRegex(ValidationError, "immutable"):
            lines[0].save()

        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate",
            return_value=date(2026, 8, 18),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_repayment.require_pawn_loan_accounting_readiness"
        ):
            with self.captureOnCommitCallbacks(execute=True):
                repayment = record_pawn_loan_repayment(
                    loan.pk,
                    amount=Decimal("3000.00"),
                    request_key="mixed-metal-principal-payment",
                    actor=self.actor,
                    delivery_handler=posted,
                )
        repayment_lines = list(
            PawnLoanRepaymentAllocationLine.objects.filter(
                accounting_event=repayment.accounting_event
            ).order_by("allocation_order")
        )
        silver = loan.collateral_items.get(metal=CollateralMetal.SILVER.value)
        gold = loan.collateral_items.get(metal=CollateralMetal.GOLD.value)
        self.assertEqual(repayment_lines[0].collateral_item_id, silver.pk)
        self.assertEqual(repayment_lines[0].principal_applied, Decimal("3000.0000"))
        self.assertEqual(repayment_lines[0].balance_after, Decimal("37000.0000"))
        self.assertEqual(repayment_lines[1].collateral_item_id, gold.pk)
        self.assertEqual(repayment_lines[1].principal_applied, Decimal("0.0000"))
        self.assertEqual(
            sum(
                (line.principal_applied for line in repayment_lines),
                Decimal("0"),
            ),
            repayment.allocation.principal,
        )
        with self.assertRaisesRegex(ValidationError, "immutable"):
            repayment_lines[0].save()
        repeated = record_pawn_loan_repayment(
            loan.pk,
            amount=Decimal("3000.00"),
            request_key="mixed-metal-principal-payment",
            actor=self.actor,
        )
        self.assertTrue(repeated.already_recorded)
        self.assertEqual(len(repeated.item_allocations), 2)
        self.assertEqual(
            PawnLoanRepaymentAllocationLine.objects.filter(
                accounting_event=repayment.accounting_event
            ).count(),
            2,
        )

        second_preview = preview_pawn_loan_accruals(
            loan.pk, as_of_date=date(2026, 9, 17), include_partial=False
        )[0]
        self.assertEqual(second_preview.period_number, 2)
        self.assertEqual(second_preview.calculation_base, Decimal("97000.0000"))
        self.assertEqual(second_preview.recognized_interest, Decimal("2680.00"))

        with patch(
            "apps.tenant_apps.loans.services.pawn_reversal.timezone.localdate",
            return_value=date(2026, 8, 18),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                reverse_pawn_loan_event(
                    repayment.accounting_event.pk,
                    reason="Correct repayment allocation",
                    actor=self.tenant.owner,
                    delivery_handler=posted,
                )
        restored_preview = preview_pawn_loan_accruals(
            loan.pk, as_of_date=date(2026, 9, 17), include_partial=False
        )[0]
        self.assertEqual(restored_preview.calculation_base, Decimal("100000.0000"))
        self.assertEqual(restored_preview.recognized_interest, Decimal("2800.00"))

        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate",
            return_value=date(2026, 8, 18),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_repayment.require_pawn_loan_accounting_readiness"
        ):
            with self.captureOnCommitCallbacks(execute=True):
                record_pawn_loan_repayment(
                    loan.pk,
                    amount=Decimal("3000.00"),
                    request_key="replacement-principal-payment",
                    actor=self.actor,
                    delivery_handler=posted,
                )

        with patch(
            "apps.tenant_apps.loans.services.pawn_interest.timezone.localdate",
            return_value=date(2026, 9, 17),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                second = finalize_pawn_loan_accrual(
                    loan.pk,
                    period_number=2,
                    actor=self.actor,
                    delivery_handler=posted,
                )
        self.assertEqual(second.accounting_event.payload["values"]["interest"], "2680")
        self.assertEqual(
            second.accounting_event.payload["values"]["advance_interest_applied"],
            "0",
        )
        self.assertEqual(PawnLoanInterestAccrualLine.objects.filter(accrual=second.accrual).count(), 2)

    def _economic_setup(self):
        create_pawn_loan_economic_policy(
            workspace=self.tenant,
            license=self.license,
            valuation_method="LATEST_APPRAISAL",
            maximum_ltv_ratio=Decimal("0.80"),
            advance_interest_periods=1,
            effective_from=date(2026, 1, 1),
        )
        for metal, rate in (
            (CollateralMetal.GOLD, Decimal("2")),
            (CollateralMetal.SILVER, Decimal("4")),
        ):
            create_pawn_metal_interest_rate_policy(
                workspace=self.tenant,
                license=self.license,
                metal=metal,
                monthly_interest_rate=rate,
                effective_from=date(2026, 1, 1),
            )

    @patch(
        "apps.tenant_apps.loans.services.pawn_release.require_pawn_loan_accounting_readiness"
    )
    @patch(
        "apps.tenant_apps.loans.services.pawn_disbursal.require_pawn_loan_accounting_readiness"
    )
    def test_full_release_freezes_item_principal_closing_evidence(
        self, _disbursal_readiness, _release_readiness
    ):
        self._economic_setup()
        LoanNumberSequence.objects.create(
            series=self.series,
            document_kind=LoanDocumentKind.PAWN_LOAN_RELEASE.value,
            prefix="RL-A-",
            width=5,
            maximum_number=10000,
        )
        rate_source = RateSource.objects.create(name="Release", location="Market")
        for metal in (Rate.Metal.GOLD, Rate.Metal.SILVER):
            rate = Rate.objects.create(
                metal=metal,
                currency=Rate.Currency.INR,
                purity=Rate.Purity.K24,
                buying_rate=Decimal("10000.00"),
                selling_rate=Decimal("10100.00"),
                rate_source=rate_source,
            )
            Rate.objects.filter(pk=rate.pk).update(
                timestamp=timezone.make_aware(datetime(2026, 7, 18, 12, 0))
            )
        loan = create_pawn_draft(
            self.command(
                principal_amount=Decimal("100000.00"),
                collateral=(
                    self.collateral(
                        allocated_principal=Decimal("60000.00"),
                    ),
                    self.collateral(
                        description="Silver anklet",
                        metal=CollateralMetal.SILVER,
                        latest_appraised_value=Decimal("80000.00"),
                        allocated_principal=Decimal("40000.00"),
                    ),
                ),
            ),
            actor=self.actor,
        )
        self._add_photo(loan)
        approve_pawn_loan(loan.pk, actor=self.actor)
        posted = lambda _event: type(
            "Receipt", (), {"dea_voucher_id": None, "dea_journal_entry_id": None}
        )()
        with self.captureOnCommitCallbacks(execute=True):
            disburse_pawn_loan(
                loan.pk,
                effective_date=date(2026, 7, 18),
                actor=self.actor,
                delivery_handler=posted,
            )

        with patch(
            "apps.tenant_apps.loans.services.pawn_release.timezone.localdate",
            return_value=date(2026, 7, 18),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                result = release_pawn_loan_in_full(
                    loan.pk,
                    settlement_amount=Decimal("100000.00"),
                    request_key="itemized-full-release",
                    actor=self.actor,
                    delivery_handler=posted,
                )

        lines = list(
            PawnLoanPrincipalClosingLine.objects.filter(
                accounting_event=result.accounting_event
            ).order_by("allocation_order")
        )
        self.assertEqual(len(lines), 2)
        self.assertEqual(
            [line.monthly_interest_rate for line in lines],
            [Decimal("4.000000"), Decimal("2.000000")],
        )
        self.assertEqual(
            [line.balance_before for line in lines],
            [Decimal("40000.0000"), Decimal("60000.0000")],
        )
        self.assertEqual(
            sum((line.principal_settled for line in lines), Decimal("0")),
            Decimal("100000.0000"),
        )
        self.assertTrue(all(line.balance_after == 0 for line in lines))
        with self.assertRaisesRegex(ValidationError, "immutable"):
            lines[0].save()
