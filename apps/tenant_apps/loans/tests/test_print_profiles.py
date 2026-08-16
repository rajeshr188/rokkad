import uuid
from datetime import date
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase
from apps.tenancy.testing import WorkspaceTestCase

from apps.orgs.models import Membership, Role
from apps.tenant_apps.loans.documents import (
    BUILT_IN_PRINT_PROFILE_COMPOSITIONS,
    PrintProfileValidationError,
    PrintProfileValidator,
    built_in_print_profile,
    legacy_print_profile,
    starter_layout,
)
from apps.tenant_apps.loans.documents.integrity import get_document_integrity_findings
from apps.tenant_apps.loans.models import LoanDocumentPrintProfileRevision
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries
from apps.tenant_apps.loans.services import (
    LoanDocumentPrintProfileService,
    LoanDocumentLayoutService,
    PrintProfileServiceError,
)


class PrintProfileContractTests(SimpleTestCase):
    def test_all_built_in_profiles_are_deterministic_valid_contracts(self):
        for composition in BUILT_IN_PRINT_PROFILE_COMPOSITIONS:
            with self.subTest(composition=composition):
                first = built_in_print_profile(composition)
                second = PrintProfileValidator.load(first.canonical_dict())
                self.assertEqual(first.content_hash, second.content_hash)
                self.assertTrue(first.sheets)
                self.assertEqual(first.document_type, "loan_ticket")

    def test_composition_rejects_contradictory_physical_settings(self):
        definition = built_in_print_profile("A4_SIDE_BY_SIDE").canonical_dict()
        definition["paper_size"] = "A5"

        with self.assertRaisesMessage(
            PrintProfileValidationError, "requires paper_size=A4"
        ):
            PrintProfileValidator.load(definition)

    def test_simplex_profile_rejects_flip_edge_guidance(self):
        definition = built_in_print_profile("A5_BOTH_SIMPLEX").canonical_dict()
        definition["flip_edge_guidance"] = "SHORT_EDGE"

        with self.assertRaisesMessage(
            PrintProfileValidationError, "Simplex profiles"
        ):
            PrintProfileValidator.load(definition)

    def test_every_legacy_sheet_composition_has_an_exact_profile(self):
        compositions = (
            "A5_ORIGINAL", "A5_ORIGINAL_TERMS_DUPLEX",
            "A5_DUPLICATE", "A5_DUPLICATE_D3_DUPLEX",
            "A5_BOTH_SIMPLEX", "A5_BOTH_DUPLEX",
            "A4_SIDE_BY_SIDE", "A4_SIDE_BY_SIDE_DUPLEX",
        )
        for composition in compositions:
            with self.subTest(composition=composition):
                profile = legacy_print_profile(SimpleNamespace(
                    document_type="loan_ticket", page_size="A5",
                    copy_mode="SINGLE", sheet=SimpleNamespace(composition=composition),
                ))
                self.assertEqual(profile.composition, composition)

    def test_legacy_sequential_copy_modes_preserve_page_size_and_surfaces(self):
        cases = (
            ("SINGLE", "LEGACY_ORIGINAL", {"ORIGINAL_FRONT"}),
            ("ORIGINAL_DUPLICATE", "LEGACY_BOTH_SIMPLEX", {"ORIGINAL_FRONT", "DUPLICATE_FRONT"}),
            ("ORIGINAL_DUPLICATE_DUPLEX", "LEGACY_BOTH_DUPLEX", {
                "ORIGINAL_FRONT", "ORIGINAL_TERMS", "DUPLICATE_FRONT", "DUPLICATE_D3",
            }),
        )
        for copy_mode, composition, surfaces in cases:
            with self.subTest(copy_mode=copy_mode):
                profile = legacy_print_profile(SimpleNamespace(
                    document_type="loan_ticket", page_size="LETTER",
                    copy_mode=copy_mode, sheet=None,
                ))
                self.assertEqual(profile.composition, composition)
                self.assertEqual(profile.paper_size, "LETTER")
                self.assertEqual(profile.included_surfaces, surfaces)


class PrintProfilePersistenceTests(WorkspaceTestCase):
    test_schema_name = f"loans_print_profile_{uuid.uuid4().hex[:8]}"
    test_domain = f"loans-print-profile-{uuid.uuid4().hex[:8]}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        owner, _ = get_user_model().objects.get_or_create(
            username="loans-print-profile-owner",
            defaults={"email": "loans-print-profile-owner@example.com"},
        )
        tenant.name = f"Loans Print Profile {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner
        tenant.save()
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        Membership.objects.get_or_create(
            user=owner, company=tenant, defaults={"role": owner_role}
        )

    def setUp(self):
        super().setUp()
        self.actor = self.tenant.owner
        self.license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Print Profile License",
            license_number="P12-LPD7",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.actor,
        )
        self.series_a = LoanSeries.objects.create(
            license=self.license, name="Series A", code="A"
        )
        self.series_b = LoanSeries.objects.create(
            license=self.license, name="Series B", code="B"
        )

    @staticmethod
    def _definition(name, composition):
        definition = built_in_print_profile(composition).canonical_dict()
        definition["name"] = name
        return definition

    def _published(self, name, composition):
        revision = LoanDocumentPrintProfileService.create_profile(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=name,
            definition=self._definition(name, composition),
            actor=self.actor,
        )
        return LoanDocumentPrintProfileService.publish(
            revision=revision, actor=self.actor
        )

    def test_resolution_precedence_is_series_then_workspace_then_built_in(self):
        fallback = LoanDocumentPrintProfileService.resolve(
            workspace=self.tenant,
            document_type="loan_ticket",
            series=self.series_a,
        )
        self.assertTrue(fallback.is_built_in)
        self.assertEqual(fallback.source_scope, "BUILT_IN")
        self.assertEqual(fallback.definition.composition, "A5_BOTH_SIMPLEX")

        workspace_revision = self._published("Workspace A5", "A5_BOTH_DUPLEX")
        LoanDocumentPrintProfileService.assign(
            revision=workspace_revision,
            workspace=self.tenant,
            actor=self.actor,
        )
        series_revision = self._published("Series A4", "A4_SIDE_BY_SIDE_DUPLEX")
        LoanDocumentPrintProfileService.assign(
            revision=series_revision,
            workspace=self.tenant,
            series=self.series_a,
            actor=self.actor,
        )

        series_result = LoanDocumentPrintProfileService.resolve(
            workspace=self.tenant,
            document_type="loan_ticket",
            series=self.series_a,
        )
        workspace_result = LoanDocumentPrintProfileService.resolve(
            workspace=self.tenant,
            document_type="loan_ticket",
            series=self.series_b,
        )

        self.assertEqual(series_result.source_scope, "SERIES")
        self.assertEqual(series_result.revision, series_revision)
        self.assertEqual(series_result.definition.composition, "A4_SIDE_BY_SIDE_DUPLEX")
        self.assertEqual(workspace_result.source_scope, "WORKSPACE")
        self.assertEqual(workspace_result.revision, workspace_revision)

    def test_published_revision_is_immutable_and_retirement_removes_assignment(self):
        revision = self._published("Immutable A5", "A5_BOTH_SIMPLEX")
        LoanDocumentPrintProfileService.assign(
            revision=revision, workspace=self.tenant, actor=self.actor
        )
        revision.definition = self._definition("Immutable A5", "A5_BOTH_DUPLEX")
        with self.assertRaisesMessage(ValidationError, "immutable"):
            revision.save()

        LoanDocumentPrintProfileService.retire(
            revision=revision, actor=self.actor
        )
        resolved = LoanDocumentPrintProfileService.resolve(
            workspace=self.tenant, document_type="loan_ticket"
        )
        self.assertTrue(resolved.is_built_in)

    def test_pilot_assignment_rejects_a_single_copy_profile(self):
        revision = self._published("Original only", "A5_ORIGINAL")

        with self.assertRaisesMessage(
            PrintProfileServiceError, "Original and Duplicate"
        ):
            LoanDocumentPrintProfileService.assign(
                revision=revision, workspace=self.tenant, actor=self.actor
            )

    def test_clone_update_publish_and_reassign_preserve_revision_history(self):
        first = self._published("Evolving profile", "A5_BOTH_SIMPLEX")
        first_assignment = LoanDocumentPrintProfileService.assign(
            revision=first, workspace=self.tenant, actor=self.actor
        )
        clone = LoanDocumentPrintProfileService.clone_revision(
            revision=first, actor=self.actor
        )
        self.assertEqual(clone.version, 2)
        updated = LoanDocumentPrintProfileService.update_draft(
            revision=clone,
            definition=self._definition(
                "Evolving profile", "A4_SIDE_BY_SIDE_DUPLEX"
            ),
            actor=self.actor,
        )
        second = LoanDocumentPrintProfileService.publish(
            revision=updated, actor=self.actor
        )
        second_assignment = LoanDocumentPrintProfileService.assign(
            revision=second, workspace=self.tenant, actor=self.actor
        )

        first_assignment.refresh_from_db()
        self.assertFalse(first_assignment.is_active)
        self.assertTrue(second_assignment.is_active)
        self.assertEqual(first.state, first.State.PUBLISHED)
        self.assertEqual(second.version, 2)
        self.assertNotEqual(first.content_hash, second.content_hash)

    def test_integrity_detects_print_profile_hash_drift(self):
        revision = self._published("Integrity profile", "A5_BOTH_SIMPLEX")
        self.assertEqual(get_document_integrity_findings(), ())

        LoanDocumentPrintProfileRevision.objects.filter(pk=revision.pk).update(
            content_hash="0" * 64
        )

        self.assertEqual(
            [finding.category for finding in get_document_integrity_findings()],
            ["PRINT_PROFILE_HASH"],
        )

    def test_assignment_rejects_profile_incompatible_with_current_layout(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["copy_mode"] = "ORIGINAL_DUPLICATE"
        layout_revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name="No logical backs",
            definition=definition,
            actor=self.actor,
        )
        layout_revision = LoanDocumentLayoutService.publish(
            revision=layout_revision, actor=self.actor
        )
        LoanDocumentLayoutService.assign(
            revision=layout_revision,
            workspace=self.tenant,
            series=self.series_a,
            actor=self.actor,
        )
        profile_revision = self._published(
            "Requires logical backs", "A5_BOTH_DUPLEX"
        )

        with self.assertRaisesMessage(
            PrintProfileServiceError, "incompatible loan-ticket layout"
        ):
            LoanDocumentPrintProfileService.assign(
                revision=profile_revision,
                workspace=self.tenant,
                series=self.series_a,
                actor=self.actor,
            )

        self.assertFalse(profile_revision.assignments.filter(is_active=True).exists())
