import tempfile
from datetime import date
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import DatabaseError, transaction
from django.test import override_settings

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.services.license_continuation import verify_legacy_license, numbering_review_digest
from apps.tenant_apps.loans.services.license_series import create_legacy_license_reference, create_configured_series, reserve_sequence_through
from apps.tenant_apps.loans.services.number_allocation import allocate_pawn_loan_number, allocate_release_number
from apps.tenant_apps.loans.tests.test_opening_import import OpeningImportFixture


class LicenseContinuationTests(OpeningImportFixture):
    def setUp(self):
        super().setUp()
        media = tempfile.TemporaryDirectory()
        self.addCleanup(media.cleanup)
        settings = override_settings(MEDIA_ROOT=media.name, STORAGES={
            "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
            "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
        settings.enable()
        self.addCleanup(settings.disable)
        clock = patch("apps.tenant_apps.loans.services.license_continuation.timezone.localdate", return_value=date(2026, 9, 22))
        clock.start()
        self.addCleanup(clock.stop)
        with self.scoped():
            self.legacy = create_legacy_license_reference(workspace=self.a, actor=self.actor,
                name="Historic license", source_label="813/94", evidence_reference="Original import")
            self.legacy_series = create_configured_series(license=self.legacy, name="C", code="C",
                is_active=True, pawn_loan_prefix="C", release_prefix="CR", number_width=5,
                maximum_number=99999, actor=self.actor)
            reserve_sequence_through(series=self.legacy_series, document_kind="PAWN_LOAN",
                last_used_number=500, evidence_reference="Includes closed and excluded source loans", actor=self.actor)
            self.old_revision = self.legacy.revisions.get()

    def verification_args(self, **changes):
        sequences = list(m.LoanNumberSequence.objects.filter(series__license=self.legacy).order_by("pk"))
        args = dict(workspace_id=self.a.pk, license_id=self.legacy.pk, actor=self.actor,
            issued_on=date(2026, 1, 1), expires_on=date(2027, 1, 1), issuing_authority="Test authority",
            supporting_document=SimpleUploadedFile("license.pdf", b"%PDF-1.4\nfixture"),
            source_sha256="a" * 64, source_as_of=date(2026, 9, 22), source_reference="Frozen dump and reviewed full register",
            confirmed_complete=True, expected_revision_id=self.old_revision.pk,
            expected_numbering_digest=numbering_review_digest(sequences),
            counters={s.pk: (520 if s.document_kind == "PAWN_LOAN" else 20) for s in sequences})
        return {**args, **changes}

    def test_same_license_series_and_old_evidence_survive_continuation(self):
        with self.scoped():
            before = m.LoanLicenseRevision.objects.filter(pk=self.old_revision.pk).values().get()
            result = verify_legacy_license(**self.verification_args())
            self.assertEqual(result.pk, self.legacy.pk)
            self.assertTrue(result.is_active)
            self.assertFalse(result.is_legacy_reference)
            self.assertEqual(before, m.LoanLicenseRevision.objects.filter(pk=self.old_revision.pk).values().get())
            revision = result.revisions.latest("revision_number")
            self.assertEqual(revision.kind, "VERIFICATION")
            self.assertEqual(revision.created_by_id, self.actor.pk)
            self.assertTrue(revision.has_document)
            self.assertEqual(revision.verification_evidence["previous_revision_id"], self.old_revision.pk)
            self.legacy_series.refresh_from_db()
            self.assertEqual(allocate_pawn_loan_number(series=self.legacy_series, actor=self.actor).value, "C00521")
            self.assertEqual(allocate_release_number(series=self.legacy_series, actor=self.actor).value, "CR00021")
            with self.assertRaisesMessage(ValueError, "already verified"):
                verify_legacy_license(**self.verification_args())
            self.assertEqual(result.revisions.count(), 2)

    def test_invalid_or_incomplete_review_leaves_license_and_counters_unchanged(self):
        with self.scoped():
            before = list(self.legacy_series.number_sequences.order_by("pk").values())
            for changes in ({"confirmed_complete": False}, {"source_sha256": "bad"},
                {"supporting_document": None}, {"supporting_document": SimpleUploadedFile("bad.pdf", b"not a PDF")},
                {"issuing_authority": ""}, {"counters": {}},
                {"expires_on": date(2025, 1, 1)}, {"source_as_of": date(2030, 1, 1)},
                {"expected_revision_id": -1}, {"expected_numbering_digest": "stale"}):
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    verify_legacy_license(**self.verification_args(**changes))
            for value in (499, 100000, True):
                args = self.verification_args()
                args["counters"][before[0]["id"]] = value
                with self.subTest(value=value), self.assertRaises(ValueError):
                    verify_legacy_license(**args)
            self.assertEqual(before, list(self.legacy_series.number_sequences.order_by("pk").values()))
            self.legacy.refresh_from_db()
            self.assertTrue(self.legacy.is_legacy_reference)
            self.assertEqual(self.legacy.revisions.count(), 1)

    def test_numbering_changes_and_overlapping_namespaces_require_review(self):
        with self.scoped():
            args = self.verification_args()
            allocate_release_number(series=self.legacy_series, actor=self.actor)
            with self.assertRaisesMessage(ValueError, "Numbering changed"):
                verify_legacy_license(**args)
            create_configured_series(license=self.legacy, name="Conflict", code="OTHER",
                is_active=False, pawn_loan_prefix="C0", release_prefix="OTHER-R", number_width=5,
                maximum_number=99999, actor=self.actor)
            with self.assertRaisesMessage(ValueError, "overlaps"):
                verify_legacy_license(**self.verification_args())

    def test_scope_permissions_and_database_guards_remain_enforced(self):
        with self.scoped():
            with self.assertRaises(PermissionDenied):
                verify_legacy_license(**self.verification_args(actor=self.other_actor))
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanLicense.objects.filter(pk=self.legacy.pk).update(is_legacy_reference=False,
                    is_active=True, issued_on=date(2026, 1, 1), expires_on=date(2027, 1, 1))
            result = verify_legacy_license(**self.verification_args())
            with self.assertRaises(DatabaseError), transaction.atomic():
                result.revisions.update(verification_evidence={})
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanLicense.objects.filter(pk=result.pk).update(is_legacy_reference=True,
                    is_active=False, issued_on=None, expires_on=None)
        with self.scoped(self.b):
            self.assertFalse(m.LoanLicense.objects.filter(pk=self.legacy.pk).exists())
            with self.assertRaises(PermissionDenied):
                verify_legacy_license(**self.verification_args())

    def test_imported_opening_keeps_export_balances_and_release_after_verification(self):
        from apps.tenant_apps.loans.services.opening_export import export_opening
        from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
        from apps.tenant_apps.loans.services.pawn_release import release_pawn_loan_in_full
        self.review["mapping"].update(licence_revision_id=self.old_revision.pk, series_id=self.legacy_series.pk)
        self.setup.update(source_license_number="813/94", legacy_license_evidence="Original source evidence")
        with self.scoped():
            origin = self.write()
            loan_id = origin.loan_id
            before = export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=loan_id)
            balance = get_pawn_loan_balance(loan_id, as_of_date=date(2021, 1, 21))
            verify_legacy_license(**self.verification_args())
            self.assertEqual(before, export_opening(workspace_id=self.a.pk, actor=self.actor, loan_id=loan_id))
            self.assertEqual(balance, get_pawn_loan_balance(loan_id, as_of_date=date(2021, 1, 21)))
            self.assertEqual(m.PawnLoan.objects.get(pk=loan_id).license_revision_id, self.old_revision.pk)
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.PawnLoanEvent.objects.create(loan_id=loan_id, event_kind="DISBURSAL", effective_date=date(2021, 1, 21),
                    payload={}, payload_fingerprint="b" * 64, idempotency_key="no-new-disbursal", created_by=self.actor)
            with patch("django.utils.timezone.localdate", return_value=date(2021, 2, 2)):
                release = release_pawn_loan_in_full(loan_id, settlement_amount=1010, request_key="after-verification", actor=self.actor)
            self.assertIsNotNone(release)
            self.assertEqual(m.PawnLoan.objects.get(pk=loan_id).state, "CLOSED")

    def test_new_draft_uses_existing_series_next_number_and_verified_revision(self):
        self._assert_new_draft()

    def test_owner_attested_license_supports_new_lending_without_fabricated_document(self):
        self._assert_new_draft(supporting_document=None, document_deferral_reason="Owner will upload original later")

    def _assert_new_draft(self, **verification_changes):
        from decimal import Decimal
        from apps.tenant_apps.loans.services import (create_pawn_draft, CreatePawnDraftCommand, CollateralDraftInput,
            approve_pawn_loan, disburse_pawn_loan, append_collateral_photo,
            create_pawn_loan_economic_policy, create_pawn_metal_interest_rate_policy)
        from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
        with self.scoped():
            license = verify_legacy_license(**self.verification_args(**verification_changes))
            product = _seed_default_loan_products()[0]
            m.LoanProductVersion.objects.filter(pk=product.pk).update(status="ACTIVE")
            create_pawn_loan_economic_policy(workspace=self.a, license=license, valuation_method="LATEST_APPRAISAL",
                maximum_ltv_ratio=Decimal("0.8"), advance_interest_periods=1, effective_from=date(2026, 1, 1), actor=self.actor)
            create_pawn_metal_interest_rate_policy(workspace=self.a, license=license, metal="GOLD",
                monthly_interest_rate=Decimal("2"), effective_from=date(2026, 1, 1), actor=self.actor)
            draft = create_pawn_draft(CreatePawnDraftCommand(workspace_id=self.a.pk,
                borrower_id=self.source_party.identity.party_id, license_id=license.pk,
                series_id=self.legacy_series.pk, product_version_id=product.pk,
                principal_amount=Decimal("1000"), monthly_interest_rate=Decimal("2"),
                loan_date=date(2026, 9, 22), tenure_months=3,
                collateral=(CollateralDraftInput(description="Ring", metal="GOLD", gross_weight=Decimal("20"),
                    net_weight=Decimal("18"), purity_percentage=Decimal("91.6"), latest_appraised_value=Decimal("120000"),
                    allocated_principal=Decimal("1000")),)),
                actor=self.actor)
            self.assertEqual(draft.loan_number, "C00521")
            self.assertEqual(draft.series_id, self.legacy_series.pk)
            self.assertEqual(draft.license_revision_id, license.revisions.latest("revision_number").pk)
            append_collateral_photo(draft.collateral_items.get().pk,
                upload=SimpleUploadedFile("ring.jpg", b"\xff\xd8\xff\xe0fixture", content_type="image/jpeg"), actor=self.actor)
            approve_pawn_loan(draft.pk, actor=self.actor)
            result = disburse_pawn_loan(draft.pk, effective_date=draft.loan_date, actor=self.actor)
            self.assertEqual(result.loan_event.event_kind, "DISBURSAL")

    def test_attestation_preserves_history_and_later_document_is_an_amendment(self):
        from apps.tenant_apps.loans.services.license_series import update_license
        from apps.tenant_apps.loans.selectors.regulatory import get_loan_license_register
        with self.scoped():
            before = m.LoanLicenseRevision.objects.filter(pk=self.old_revision.pk).values().get()
            license = verify_legacy_license(**self.verification_args(supporting_document=None,
                document_deferral_reason="Original document will be supplied later"))
            revision = license.revisions.latest("revision_number")
            self.assertEqual(revision.kind, "ATTESTATION")
            self.assertFalse(revision.has_document)
            self.assertTrue(license.document_pending)
            register = {row.license.pk: row for row in get_loan_license_register(self.a.pk)}
            self.assertEqual(register[license.pk].status, "DOCUMENT_PENDING")
            self.assertEqual(revision.verification_evidence["validity_basis"], "owner_attested")
            self.assertEqual(before, m.LoanLicenseRevision.objects.filter(pk=self.old_revision.pk).values().get())
            saved = m.LoanLicenseRevision.objects.filter(pk=revision.pk).values().get()
            update_license(license, actor=self.actor,
                supporting_document=SimpleUploadedFile("actual-license.pdf", b"%PDF-1.4\nfixture"))
            self.assertFalse(license.document_pending)
            self.assertEqual(license.revisions.latest("revision_number").kind, "AMENDMENT")
            self.assertEqual(saved, m.LoanLicenseRevision.objects.filter(pk=revision.pk).values().get())

    def test_deferral_requires_owner_reason_and_no_substitute(self):
        with self.scoped():
            before = list(self.legacy_series.number_sequences.order_by("pk").values())
            for changes in ({"document_deferral_reason": ""}, {"document_deferral_reason": " "},
                            {"document_deferral_reason": "x" * 1001}, {"document_deferral_reason": True},
                            {"supporting_document": SimpleUploadedFile("substitute.pdf", b"%PDF-1.4\nfixture")}):
                args = self.verification_args(supporting_document=None, document_deferral_reason="Later")
                args.update(changes)
                with self.subTest(changes=changes), self.assertRaises(ValueError):
                    verify_legacy_license(**args)
            # Even a privileged setup administrator cannot attest for the owner.
            from django.contrib.auth import get_user_model
            admin = get_user_model().objects.create_superuser(username="attestation-platform", email="admin@example.test")
            with self.assertRaises(PermissionDenied):
                verify_legacy_license(**self.verification_args(actor=admin, supporting_document=None,
                    document_deferral_reason="Not the Workspace owner"))
            self.assertEqual(before, list(self.legacy_series.number_sequences.order_by("pk").values()))

    def test_database_rejects_incomplete_or_falsely_verified_attestation(self):
        import copy
        with self.scoped():
            with transaction.atomic():
                license = verify_legacy_license(**self.verification_args(supporting_document=None,
                    document_deferral_reason="Owner pending original"))
                revision = license.revisions.latest("revision_number")
                fields = {f.attname: getattr(revision, f.attname) for f in revision._meta.concrete_fields if not f.primary_key}
                transaction.set_rollback(True)
            for kind, last in (("PAWN_LOAN", 520), ("PAWN_LOAN_RELEASE", 20)):
                reserve_sequence_through(series=self.legacy_series, document_kind=kind,
                    last_used_number=last, evidence_reference="Reviewed source", actor=self.actor)
            for changes in ({"kind": "VERIFICATION"}, {"created_by_id": self.other_actor.pk},
                            {"supporting_document": "substitute.pdf", "sha256": "b" * 64, "byte_size": 10},
                            {"verification_evidence": {**fields["verification_evidence"], "document_deferral_reason": ""}},
                            {"verification_evidence": {**fields["verification_evidence"], "document_deferred": False}},
                            {"verification_evidence": {**fields["verification_evidence"], "confirmed_complete": False}}):
                with self.subTest(changes=changes), self.assertRaises(DatabaseError), transaction.atomic():
                    m.LoanLicenseRevision.objects.bulk_create([m.LoanLicenseRevision(**{**copy.deepcopy(fields), **changes})])
            with transaction.atomic():
                m.LoanLicenseRevision.objects.bulk_create([m.LoanLicenseRevision(**fields)])
                transaction.set_rollback(True)

    def test_destination_numbers_above_reviewed_range_are_rejected(self):
        with self.scoped():
            # Simulate an older destination whose counter was not reserved correctly.
            m.PawnLoan.objects.create(workspace=self.a, license=self.legacy, license_revision=self.old_revision,
                series=self.legacy_series, borrower_id=self.source_party.identity.party_id,
                product_version_id=self.review["mapping"]["product_version_id"],
                loan_number="C00599", principal_amount=1000, monthly_interest_rate=2)
            with self.assertRaisesMessage(ValueError, "omits existing number C00599"):
                verify_legacy_license(**self.verification_args())
            self.legacy.refresh_from_db()
            self.assertTrue(self.legacy.is_legacy_reference)

    def test_raw_verification_without_numbering_evidence_is_rejected(self):
        with self.scoped():
            revision = m.LoanLicenseRevision(workspace=self.a, license=self.legacy, revision_number=2,
                kind="VERIFICATION", name=self.legacy.name, license_number=self.legacy.license_number,
                issued_on=date(2026, 1, 1), expires_on=date(2027, 1, 1), issuing_authority="Test",
                supporting_document="fake.pdf", sha256="a" * 64, byte_size=20, created_by=self.actor,
                verification_evidence={"profile": "legacy-license-continuation/1", "confirmed_complete": True,
                    "previous_revision_id": self.old_revision.pk, "source_sha256": "b" * 64,
                    "source_reference": "Test", "source_as_of": "2026-09-22", "sequences": []})
            with self.assertRaises(DatabaseError), transaction.atomic():
                m.LoanLicenseRevision.objects.bulk_create([revision])
