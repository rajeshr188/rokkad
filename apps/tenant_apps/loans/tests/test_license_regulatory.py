import shutil
import tempfile
import uuid
from datetime import date
from unittest.mock import patch

import fitz
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, connection, transaction
from django.test import override_settings
from apps.tenancy.testing import WorkspaceTestCase

from apps.tenant_apps.loans.documents.payloads import PawnLoanDocumentProjectionBuilder
from apps.tenant_apps.loans.models import LoanLicenseRevision, PawnLoan
from apps.tenant_apps.loans.selectors import get_loan_license_register
from apps.tenant_apps.loans.services import (
    LicenseSeriesError,
    create_license,
    create_series,
    render_loan_license_register_pdf,
    renew_license,
    update_license,
)
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.loans.tests.factories import ensure_test_product_version


TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="rokkad-license-regulatory-")


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class LoanLicenseRegulatoryTests(WorkspaceTestCase):
    test_schema_name = f"loans_regulatory_{uuid.uuid4().hex[:8]}"
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
            username="loans-regulatory-owner",
            defaults={"email": "loans-regulatory-owner@example.com"},
        )
        tenant.name = f"Loans Regulatory {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        super().setUp()
        self.user = get_user_model().objects.create_user(
            username=f"regulatory-user-{uuid.uuid4().hex[:8]}",
            email=f"regulatory-{uuid.uuid4().hex[:8]}@example.com",
        )
        audit = patch(
            "apps.tenant_apps.loans.services.license_series.AuditLog.log"
        )
        audit.start()
        self.addCleanup(audit.stop)

    @staticmethod
    def document(name="license.pdf"):
        return SimpleUploadedFile(
            name,
            b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF",
            content_type="application/pdf",
        )

    def create_license(self, *, expires_on=date(2027, 1, 1)):
        return create_license(
            workspace=self.tenant,
            name="Pawn Broker License",
            license_number="PBL-REG-1",
            issuing_authority="State Authority",
            issued_on=date(2026, 1, 1),
            expires_on=expires_on,
            supporting_document=self.document(),
            actor=self.user,
        )

    def test_issue_amendment_and_renewal_append_immutable_revision_history(self):
        license = self.create_license()
        initial = license.revisions.get(revision_number=1)
        self.assertEqual(initial.kind, LoanLicenseRevision.Kind.INITIAL)
        self.assertTrue(initial.has_document)

        update_license(
            license,
            actor=self.user,
            name="Pawn Broker License Updated",
        )
        renewal = renew_license(
            license,
            issued_on=date(2027, 1, 2),
            expires_on=date(2028, 1, 1),
            supporting_document=self.document("renewal.pdf"),
            actor=self.user,
        )

        self.assertEqual(renewal.revisions.count(), 3)
        self.assertEqual(
            list(renewal.revisions.values_list("kind", flat=True)),
            ["INITIAL", "AMENDMENT", "RENEWAL"],
        )
        initial.refresh_from_db()
        self.assertEqual(initial.name, "Pawn Broker License")
        with self.assertRaises(ValidationError):
            initial.save()
        with self.assertRaises(DatabaseError), transaction.atomic():
            LoanLicenseRevision.objects.filter(pk=initial.pk).update(notes="mutated")

    def test_renewal_requires_supported_document(self):
        license = self.create_license()
        with self.assertRaisesRegex(LicenseSeriesError, "required"):
            renew_license(
                license,
                issued_on=date(2027, 1, 2),
                expires_on=date(2028, 1, 1),
                supporting_document=None,
                actor=self.user,
            )
        with self.assertRaisesRegex(LicenseSeriesError, "PDF, PNG, or JPEG"):
            renew_license(
                license,
                issued_on=date(2027, 1, 2),
                expires_on=date(2028, 1, 1),
                supporting_document=SimpleUploadedFile("bad.txt", b"not legal evidence"),
                actor=self.user,
            )

    def test_register_surfaces_expiry_and_document_readiness_and_renders_pdf(self):
        ready = self.create_license(expires_on=date(2027, 1, 1))
        missing = create_license(
            workspace=self.tenant,
            name="Legacy License",
            license_number="PBL-REG-2",
            issued_on=date(2025, 1, 1),
            expires_on=date(2026, 1, 1),
            actor=self.user,
        )

        rows = get_loan_license_register(
            self.tenant.pk,
            as_of_date=date(2026, 8, 8),
        )
        by_id = {row.license.pk: row for row in rows}
        self.assertEqual(by_id[ready.pk].status, "READY")
        self.assertEqual(by_id[missing.pk].status, "EXPIRED")
        self.assertIn("Current license document is missing.", by_id[missing.pk].blockers)

        pdf = render_loan_license_register_pdf(
            workspace=self.tenant,
            rows=rows,
            as_of_date=date(2026, 8, 8),
        )
        self.assertTrue(pdf.startswith(b"%PDF-"))
        document = fitz.open(stream=pdf, filetype="pdf")
        text = "\n".join(page.get_text() for page in document)
        document.close()
        self.assertIn("PBL-REG-1", text)

    def test_existing_loan_keeps_original_license_revision_after_renewal(self):
        license = self.create_license()
        initial = license.revisions.get(revision_number=1)
        series = create_series(license=license, name="Main", code="A")
        borrower = Party.objects.create(
            party_code="P-REG-1",
            display_name="Regulatory Borrower",
            party_type=Party.PartyType.INDIVIDUAL,
            status=Party.PartyStatus.ACTIVE,
        )
        loan = PawnLoan.objects.create(
            workspace=self.tenant,
            product_version=ensure_test_product_version(self.tenant),
            license=license,
            license_revision=initial,
            series=series,
            borrower=borrower,
            loan_number="PL-REG-1",
            state="APPROVED",
            principal_amount="1000.00",
            monthly_interest_rate="2.000000",
            loan_date=date(2026, 1, 1),
            tenure_months=3,
        )
        renew_license(
            license,
            issued_on=date(2027, 1, 2),
            expires_on=date(2028, 1, 1),
            supporting_document=self.document("renewal.pdf"),
            actor=self.user,
        )
        renewal = license.revisions.get(kind=LoanLicenseRevision.Kind.RENEWAL)

        loan.refresh_from_db()
        self.assertEqual(loan.license_revision_id, initial.pk)
        identity = dict(PawnLoanDocumentProjectionBuilder._identity_rows(loan))
        self.assertEqual(identity["License source ID"], f"LoanLicenseRevision:{initial.pk}")
        self.assertEqual(identity["License validity"], "2026-01-01 to 2027-01-01")
        with self.assertRaises(DatabaseError), transaction.atomic():
            PawnLoan.objects.filter(pk=loan.pk).update(license_revision=renewal)
