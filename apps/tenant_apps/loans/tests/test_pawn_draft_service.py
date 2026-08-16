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
    CollateralCustodyState,
    CollateralMetal,
    LoanDocumentKind,
    PawnLoanEventKind,
    PawnLoanRenewalMode,
    PawnLoanState,
    TransactionKind,
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
    PawnLoanAuction,
    PawnLoanAuctionReversal,
    PawnLoanPrincipalClosingLine,
    PawnLoanRepaymentAllocationLine,
    PawnLoanRenewal,
)
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    DraftCollateralPhotoInput,
    PawnDraftError,
    UpdatePawnDraftCommand,
    approve_pawn_loan,
    append_collateral_photo,
    create_pawn_draft,
    create_pawn_draft_with_photos,
    create_pawn_loan_economic_policy,
    create_pawn_metal_interest_rate_policy,
    disburse_pawn_loan,
    cancel_pawn_loan_auction,
    complete_pawn_loan_auction,
    finalize_pawn_loan_accrual,
    preview_pawn_loan_accruals,
    record_pawn_loan_repayment,
    initiate_pawn_loan_auction,
    renew_pawn_loan,
    reverse_pawn_loan_auction,
    seed_default_loan_products,
    release_pawn_loan_in_full,
    reverse_pawn_loan_event,
    start_pawn_loan_auction,
    update_pawn_draft,
    update_pawn_draft_with_photos,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.notify_v2.models import NotificationJob
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
        self.product_version = seed_default_loan_products()[0]
        type(self.product_version).objects.filter(pk=self.product_version.pk).update(status="ACTIVE")
        self.product_version.refresh_from_db()

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
            "product_version_id": self.product_version.pk,
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
        self.assertEqual(loan.product_version, self.product_version)
        self.assertEqual(loan.collateral_items.count(), 1)
        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.next_number, 2)
        event = LoanChangeLog.objects.get(loan=loan)
        self.assertEqual(event.event_kind, PawnLoanEventKind.DRAFT_CREATED.value)
        self.assertEqual(event.actor, self.actor)
        self.assertEqual(event.metadata["collateral_count"], 1)

    def test_create_with_photos_maps_media_to_created_collateral(self):
        upload = SimpleUploadedFile(
            "gold-bangles.jpg",
            b"\xff\xd8\xff\xe0draft-evidence",
            content_type="image/jpeg",
        )

        loan = create_pawn_draft_with_photos(
            self.command(),
            photos=(DraftCollateralPhotoInput(None, upload),),
            actor=self.actor,
        )

        photo = loan.collateral_items.get().photos.get()
        self.assertEqual(photo.original_filename, "gold-bangles.jpg")
        self.assertEqual(photo.workflow_source, "DRAFT")

    def test_invalid_photo_fails_before_number_allocation(self):
        upload = SimpleUploadedFile(
            "not-an-image.txt", b"invalid", content_type="text/plain"
        )

        with self.assertRaisesRegex(ValueError, "JPEG or PNG"):
            create_pawn_draft_with_photos(
                self.command(),
                photos=(DraftCollateralPhotoInput(None, upload),),
                actor=self.actor,
            )

        self.assertFalse(PawnLoan.objects.exists())
        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.next_number, 1)

    def test_later_photo_failure_rolls_back_draft_number_and_written_file(self):
        command = self.command(
            collateral=(
                self.collateral(description="Gold bangles"),
                self.collateral(description="Gold ring"),
            )
        )
        written = []

        def persist_then_fail(item_id, **kwargs):
            if written:
                raise RuntimeError("second photo failed")
            photo = append_collateral_photo(item_id, **kwargs)
            written.append((photo.file.storage, photo.file.name))
            return photo

        with patch(
            "apps.tenant_apps.loans.services.pawn_drafts.append_collateral_photo",
            side_effect=persist_then_fail,
        ):
            with self.assertRaisesRegex(RuntimeError, "second photo failed"):
                create_pawn_draft_with_photos(
                    command,
                    photos=(
                        DraftCollateralPhotoInput(
                            None,
                            SimpleUploadedFile(
                                "first.jpg",
                                b"\xff\xd8\xfffirst",
                                content_type="image/jpeg",
                            ),
                        ),
                        DraftCollateralPhotoInput(
                            None,
                            SimpleUploadedFile(
                                "second.jpg",
                                b"\xff\xd8\xffsecond",
                                content_type="image/jpeg",
                            ),
                        ),
                    ),
                    actor=self.actor,
                )

        self.assertFalse(PawnLoan.objects.exists())
        self.sequence.refresh_from_db()
        self.assertEqual(self.sequence.next_number, 1)
        self.assertFalse(written[0][0].exists(written[0][1]))

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
            self.command(product_version_id=999999),
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

    def test_update_with_photos_maps_existing_and_new_collateral(self):
        loan = create_pawn_draft(self.command(), actor=self.actor)
        existing = loan.collateral_items.get()
        command = UpdatePawnDraftCommand(
            borrower_id=self.borrower.pk,
            principal_amount=Decimal("60000.00"),
            monthly_interest_rate=Decimal("2.000000"),
            loan_date=loan.loan_date,
            tenure_months=loan.tenure_months,
            collateral=(
                self.collateral(collateral_item_id=existing.pk),
                self.collateral(description="Gold ring"),
            ),
        )

        update_pawn_draft_with_photos(
            loan.pk,
            command,
            photos=(
                DraftCollateralPhotoInput(
                    existing.pk,
                    SimpleUploadedFile(
                        "existing.jpg", b"\xff\xd8\xffexisting", content_type="image/jpeg"
                    ),
                ),
                DraftCollateralPhotoInput(
                    None,
                    SimpleUploadedFile(
                        "new.jpg", b"\xff\xd8\xffnew", content_type="image/jpeg"
                    ),
                ),
            ),
            actor=self.actor,
        )

        self.assertEqual(existing.photos.get().original_filename, "existing.jpg")
        self.assertEqual(
            loan.collateral_items.get(description="Gold ring").photos.get().original_filename,
            "new.jpg",
        )

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

    def test_disbursal_freezes_approved_gross_net_and_tranche_evidence(self):
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
        self.assertEqual(result.loan_event.payload["values"]["net_cash"], "49000")
        self.assertEqual(result.loan_event.payload["values"]["advance_interest"], "1000")
        with self.assertRaisesRegex(ValidationError, "immutable"):
            snapshot.save()
        with self.assertRaisesRegex(ValidationError, "cannot be deleted"):
            snapshot.delete()

    def test_item_accrual_consumes_advance_interest_once(self):
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
        with self.captureOnCommitCallbacks(execute=True):
            disburse_pawn_loan(
                loan.pk,
                effective_date=date(2026, 7, 18),
                actor=self.actor,
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
        self.assertIsNone(first.loan_event)
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
        ):
            with self.captureOnCommitCallbacks(execute=True):
                repayment = record_pawn_loan_repayment(
                    loan.pk,
                    amount=Decimal("3000.00"),
                    request_key="mixed-metal-principal-payment",
                    actor=self.actor,
                )
        repayment_lines = list(
            PawnLoanRepaymentAllocationLine.objects.filter(
                loan_event=repayment.loan_event
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
                loan_event=repayment.loan_event
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
                    repayment.loan_event.pk,
                    reason="Correct repayment allocation",
                    actor=self.tenant.owner,
                )
        restored_preview = preview_pawn_loan_accruals(
            loan.pk, as_of_date=date(2026, 9, 17), include_partial=False
        )[0]
        self.assertEqual(restored_preview.calculation_base, Decimal("100000.0000"))
        self.assertEqual(restored_preview.recognized_interest, Decimal("2800.00"))

        with patch(
            "apps.tenant_apps.loans.services.pawn_repayment.timezone.localdate",
            return_value=date(2026, 8, 18),
        ):
            with self.captureOnCommitCallbacks(execute=True):
                record_pawn_loan_repayment(
                    loan.pk,
                    amount=Decimal("3000.00"),
                    request_key="replacement-principal-payment",
                    actor=self.actor,
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
                )
        self.assertEqual(second.loan_event.payload["values"]["interest"], "2680")
        self.assertEqual(
            second.loan_event.payload["values"]["advance_interest_applied"],
            "0",
        )
        self.assertEqual(PawnLoanInterestAccrualLine.objects.filter(accrual=second.accrual).count(), 2)

    def test_renewal_is_idempotent_and_records_successor_events(self):
        self._economic_setup()
        rate_source = RateSource.objects.create(name="Renewal", location="Market")
        rate = Rate.objects.create(
            metal=Rate.Metal.GOLD,
            currency=Rate.Currency.INR,
            purity=Rate.Purity.K24,
            buying_rate=Decimal("10000.00"),
            selling_rate=Decimal("10100.00"),
            rate_source=rate_source,
        )
        Rate.objects.filter(pk=rate.pk).update(
            timestamp=timezone.make_aware(datetime(2026, 7, 18, 12, 0))
        )
        loan = create_pawn_draft(self.command(), actor=self.actor)
        self._add_photo(loan)
        approve_pawn_loan(loan.pk, actor=self.actor)
        disburse_pawn_loan(
            loan.pk,
            effective_date=date(2026, 7, 18),
            actor=self.actor,
        )
        call = dict(
            mode=PawnLoanRenewalMode.PAY_AND_RENEW,
            renewal_date=date(2026, 7, 18),
            principal_paid=Decimal("11000.00"),
            top_up_amount=Decimal("0.00"),
            successor_license_id=self.license.pk,
            successor_series_id=self.series.pk,
            monthly_interest_rate=Decimal("2.000000"),
            tenure_months=3,
            request_key="loans-only-renewal-idempotency",
            actor=self.actor,
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_renewals.timezone.localdate",
            return_value=date(2026, 7, 18),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_renewals.preview_pawn_loan_accruals",
            return_value=(),
        ):
            first = renew_pawn_loan(loan.pk, **call)
            second = renew_pawn_loan(loan.pk, **call)

        self.assertFalse(first.already_renewed)
        self.assertTrue(second.already_renewed)
        self.assertEqual(first.renewal.pk, second.renewal.pk)
        self.assertEqual(PawnLoanRenewal.objects.filter(source_loan=loan).count(), 1)
        self.assertEqual(first.settlement_event.loan_id, loan.pk)
        self.assertEqual(first.opening_event.loan_id, first.successor_loan.pk)
        self.assertEqual(first.successor_loan.state, PawnLoanState.ACTIVE.value)
        self.assertEqual(first.renewal.successor_principal_amount, Decimal("39000.00"))

    def test_auction_initiation_is_idempotent_and_cancellation_is_auditable(self):
        self._economic_setup()
        self.borrower.primary_email = "auction-borrower@example.com"
        self.borrower.save(update_fields=["primary_email"])
        loan = create_pawn_draft(self.command(), actor=self.actor)
        self._add_photo(loan)
        approve_pawn_loan(loan.pk, actor=self.actor)
        disburse_pawn_loan(
            loan.pk,
            effective_date=date(2026, 7, 18),
            actor=self.actor,
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 4),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_notices.timezone.localdate",
            return_value=date(2026, 12, 4),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_notices.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 12, 4, 10, 0)),
        ):
            first = initiate_pawn_loan_auction(
                loan.pk,
                scheduled_date=date(2026, 12, 10),
                channel="EMAIL",
                request_key="loans-only-auction-idempotency",
                actor=self.tenant.owner,
            )
            second = initiate_pawn_loan_auction(
                loan.pk,
                scheduled_date=date(2026, 12, 10),
                channel="EMAIL",
                request_key="loans-only-auction-idempotency",
                actor=self.tenant.owner,
            )

        self.assertEqual(first.pk, second.pk)
        self.assertEqual(PawnLoanAuction.objects.filter(loan=loan).count(), 1)
        self.assertIsNotNone(first.notice.notification_job_id)
        cancelled = cancel_pawn_loan_auction(
            first.pk,
            reason="Borrower settled before auction",
            actor=self.tenant.owner,
        )
        self.assertEqual(cancelled.state, "CANCELLED")
        self.assertEqual(cancelled.cancellation_reason, "Borrower settled before auction")

    def test_auction_completion_and_reversal_restore_loan_and_custody(self):
        self._economic_setup()
        self.borrower.primary_email = "auction-recovery@example.com"
        self.borrower.save(update_fields=["primary_email"])
        loan = create_pawn_draft(self.command(), actor=self.actor)
        self._add_photo(loan)
        approve_pawn_loan(loan.pk, actor=self.actor)
        disburse_pawn_loan(
            loan.pk,
            effective_date=date(2026, 7, 18),
            actor=self.actor,
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 4),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_notices.timezone.localdate",
            return_value=date(2026, 12, 4),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_notices.timezone.now",
            return_value=timezone.make_aware(datetime(2026, 12, 4, 10, 0)),
        ):
            auction = initiate_pawn_loan_auction(
                loan.pk,
                scheduled_date=date(2026, 12, 5),
                channel="EMAIL",
                request_key="loans-only-auction-recovery",
                actor=self.tenant.owner,
            )
        NotificationJob.objects.filter(
            pk=auction.notice.notification_job_id
        ).update(
            status=NotificationJob.Status.SENT,
            sent_at=timezone.make_aware(datetime(2026, 12, 4, 10, 5)),
        )
        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 5),
        ), patch(
            "apps.tenant_apps.loans.services.pawn_auctions.preview_pawn_loan_accruals",
            return_value=(),
        ):
            auction = start_pawn_loan_auction(
                auction.pk,
                actor=self.tenant.owner,
            )
            completed = complete_pawn_loan_auction(
                auction.pk,
                recovery_amount=Decimal("50000.00"),
                buyer_name="Auction Buyer",
                buyer_reference="SALE-001",
                actor=self.tenant.owner,
            )

        loan.refresh_from_db()
        collateral = loan.collateral_items.get()
        collateral.refresh_from_db()
        self.assertEqual(completed.loan_event.event_kind, TransactionKind.AUCTION_RECOVERY.value)
        self.assertEqual(loan.state, PawnLoanState.CLOSED.value)
        self.assertEqual(collateral.custody_state, CollateralCustodyState.AUCTION_DISPOSED.value)
        self.assertEqual(completed.auction.items.count(), 1)
        recovery_allocation = completed.loan_event.obligation_allocations.get()
        self.assertEqual(recovery_allocation.amount, Decimal("50000.0000"))

        with patch(
            "apps.tenant_apps.loans.services.pawn_auctions.timezone.localdate",
            return_value=date(2026, 12, 5),
        ):
            reversed_auction = reverse_pawn_loan_auction(
                completed.auction.pk,
                reason="Buyer settlement was voided",
                actor=self.tenant.owner,
            )

        loan.refresh_from_db()
        collateral.refresh_from_db()
        self.assertEqual(loan.state, PawnLoanState.ACTIVE.value)
        self.assertEqual(collateral.custody_state, CollateralCustodyState.IN_VAULT.value)
        self.assertEqual(
            reversed_auction.recovery_reversal_event.reversal_of_id,
            completed.loan_event.pk,
        )
        inverse = reversed_auction.recovery_reversal_event.obligation_allocations.get()
        self.assertEqual(inverse.reversal_of_id, recovery_allocation.pk)
        self.assertEqual(inverse.amount, Decimal("-50000.0000"))
        self.assertTrue(
            PawnLoanAuctionReversal.objects.filter(auction=completed.auction).exists()
        )

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

    def test_full_release_freezes_item_principal_closing_evidence(self):
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
        with self.captureOnCommitCallbacks(execute=True):
            disburse_pawn_loan(
                loan.pk,
                effective_date=date(2026, 7, 18),
                actor=self.actor,
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
                )

        lines = list(
            PawnLoanPrincipalClosingLine.objects.filter(
                loan_event=result.loan_event
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
