import uuid
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.domain import CollateralMetal, LoanDocumentKind, PawnLoanEventKind, PawnLoanState
from apps.tenant_apps.loans.models import LoanLicense, LoanNumberSequence, LoanSeries, PawnLoanApprovalSnapshot
from apps.tenant_apps.loans.services import (
    CollateralDraftInput,
    CreatePawnDraftCommand,
    PawnLifecycleError,
    approve_pawn_loan,
    append_collateral_photo,
    cancel_pawn_loan,
    create_pawn_draft,
    reopen_pawn_loan,
    transfer_expired_draft_setup,
    seed_default_loan_products,
)
from apps.tenant_apps.party.models import Party


class PawnLifecycleServiceTests(TenantTestCase):
    test_schema_name = f"loans_lifecycle_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-lifecycle-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="loans-lifecycle-owner",
            defaults={"email": "loans-lifecycle-owner@example.com"},
        )
        tenant.name = f"Loans Lifecycle {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.actor = get_user_model().objects.create_user(
            username=f"lifecycle-{uuid.uuid4().hex[:8]}",
            email=f"lifecycle-{uuid.uuid4().hex[:8]}@example.com",
        )
        self.borrower = Party.objects.create(display_name="Lifecycle Borrower")
        self.license, self.series = self._setup("A", "PL-A-")
        product_version = seed_default_loan_products()[0]
        type(product_version).objects.filter(pk=product_version.pk).update(status="ACTIVE")
        self.loan = create_pawn_draft(
            CreatePawnDraftCommand(
                workspace_id=self.tenant.pk,
                borrower_id=self.borrower.pk,
                license_id=self.license.pk,
                series_id=self.series.pk,
                product_version_id=product_version.pk,
                principal_amount=Decimal("50000.00"),
                monthly_interest_rate=Decimal("2.000000"),
                loan_date=date(2026, 7, 18),
                tenure_months=3,
                collateral=(CollateralDraftInput(
                    description="Gold bangles",
                    metal=CollateralMetal.GOLD,
                    gross_weight=Decimal("20.0000"),
                    net_weight=Decimal("18.0000"),
                    purity_percentage=Decimal("91.6000"),
                    latest_appraised_value=Decimal("120000.00"),
                ),),
            ),
            actor=self.actor,
        )
        append_collateral_photo(
            self.loan.collateral_items.get().pk,
            upload=SimpleUploadedFile(
                "bangles.jpg", b"\xff\xd8\xff\xe0evidence", content_type="image/jpeg"
            ),
            actor=self.actor,
        )

    def test_approval_freezes_complete_immutable_payload_and_audits(self):
        snapshot = approve_pawn_loan(self.loan.pk, actor=self.actor)
        self.loan.refresh_from_db()

        self.assertEqual(self.loan.state, PawnLoanState.APPROVED.value)
        self.assertEqual(snapshot.version, 1)
        self.assertEqual(snapshot.payload["principal_amount"], "50000.00")
        self.assertEqual(snapshot.payload["collateral"][0]["purity_percentage"], "91.6000")
        self.assertEqual(len(snapshot.fingerprint), 64)
        event = self.loan.change_log.get(event_kind=PawnLoanEventKind.APPROVED.value)
        self.assertEqual(event.metadata["approval_snapshot_id"], snapshot.pk)
        snapshot.payload = {}
        with self.assertRaises(ValidationError):
            snapshot.save()
        with self.assertRaises(ValidationError):
            snapshot.delete()

    def test_reopen_requires_reason_and_reapproval_appends_version(self):
        first = approve_pawn_loan(self.loan.pk, actor=self.actor)
        with self.assertRaises(PawnLifecycleError):
            reopen_pawn_loan(self.loan.pk, reason=" ", actor=self.actor)
        reopen_pawn_loan(self.loan.pk, reason="Correct valuation", actor=self.actor)
        second = approve_pawn_loan(self.loan.pk, actor=self.actor)

        self.assertEqual((first.version, second.version), (1, 2))
        self.assertEqual(PawnLoanApprovalSnapshot.objects.filter(loan=self.loan).count(), 2)
        event = self.loan.change_log.get(event_kind=PawnLoanEventKind.RETURNED_TO_DRAFT.value)
        self.assertEqual(event.reason, "Correct valuation")

    def test_cancel_draft_or_approved_requires_reason(self):
        with self.assertRaises(PawnLifecycleError):
            cancel_pawn_loan(self.loan.pk, reason="", actor=self.actor)
        approve_pawn_loan(self.loan.pk, actor=self.actor)
        cancel_pawn_loan(self.loan.pk, reason="Borrower withdrew", actor=self.actor)
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, PawnLoanState.CANCELLED.value)
        self.assertEqual(self.loan.change_log.get(event_kind=PawnLoanEventKind.CANCELLED.value).reason, "Borrower withdrew")

    def test_invalid_transitions_fail_without_extra_audit(self):
        approve_pawn_loan(self.loan.pk, actor=self.actor)
        with self.assertRaises(PawnLifecycleError):
            approve_pawn_loan(self.loan.pk, actor=self.actor)
        cancel_pawn_loan(self.loan.pk, reason="Cancelled", actor=self.actor)
        with self.assertRaises(PawnLifecycleError):
            reopen_pawn_loan(self.loan.pk, reason="Not allowed", actor=self.actor)
        self.assertEqual(self.loan.change_log.count(), 3)

    def test_expired_setup_transfer_allocates_new_number_and_requires_reapproval(self):
        approve_pawn_loan(self.loan.pk, actor=self.actor)
        reopen_pawn_loan(self.loan.pk, reason="License expired", actor=self.actor)
        self.license.is_active = False
        self.license.save(update_fields=["is_active"])
        replacement_license, replacement_series = self._setup("B", "PL-B-")

        transfer_expired_draft_setup(
            self.loan.pk,
            license_id=replacement_license.pk,
            series_id=replacement_series.pk,
            reason="Move to replacement license",
            actor=self.actor,
        )
        self.loan.refresh_from_db()
        self.assertEqual(self.loan.state, PawnLoanState.DRAFT.value)
        self.assertEqual(self.loan.loan_number, "PL-B-00001")
        self.assertEqual(self.loan.approval_snapshots.count(), 1)
        approve_pawn_loan(self.loan.pk, actor=self.actor)
        self.assertEqual(self.loan.approval_snapshots.count(), 2)

    def _setup(self, code, prefix):
        license = LoanLicense.objects.create(
            workspace=self.tenant,
            name=f"License {code}",
            license_number=f"PBL-{code}-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
        )
        series = LoanSeries.objects.create(license=license, name=f"Series {code}", code=code)
        LoanNumberSequence.objects.create(
            series=series,
            document_kind=LoanDocumentKind.PAWN_LOAN.value,
            prefix=prefix,
            width=5,
            maximum_number=10000,
        )
        return license, series
