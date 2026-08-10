import uuid
from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import SimpleTestCase
from django_tenants.test.cases import TenantTestCase

from apps.orgs.models import Membership, Role
from apps.tenant_apps.loans.documents import (
    BUILT_IN_PRINT_PROFILE_COMPOSITIONS,
    PrintProfileValidationError,
    PrintProfileValidator,
    built_in_print_profile,
)
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries
from apps.tenant_apps.loans.services import (
    LoanDocumentPrintProfileService,
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


class PrintProfilePersistenceTests(TenantTestCase):
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
        connection.set_tenant(self.tenant)
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
