import hashlib
import uuid
from datetime import date
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.db import connection
from django_tenants.test.cases import TenantTestCase

from apps.tenant_apps.loans.documents import (
    DocumentLayoutValidator,
    built_in_print_profile,
    legacy_print_profile,
    starter_layout,
)
from apps.tenant_apps.loans.documents.integrity import get_document_integrity_findings
from apps.tenant_apps.loans.documents.packs import export_layout_pack, import_layout_pack
from apps.tenant_apps.loans.models import (
    LoanDocumentIssue,
    LoanDocumentLayoutRevision,
    LoanLicense,
    LoanSeries,
)
from apps.tenant_apps.loans.services import (
    DocumentLayoutServiceError,
    LoanDocumentLayoutService,
    LoanDocumentPrintProfileService,
)
from apps.tenant_apps.loans.services.print_profiles import ResolvedPrintProfile


class LoanDocumentLayoutPersistenceTests(TenantTestCase):
    test_schema_name = f"loan_docs_{uuid.uuid4().hex[:8]}"
    test_domain = f"{test_schema_name}.test.com"

    @classmethod
    def get_test_schema_name(cls):
        return cls.test_schema_name

    @classmethod
    def get_test_tenant_domain(cls):
        return cls.test_domain

    @classmethod
    def setup_tenant(cls, tenant):
        from django.contrib.auth import get_user_model

        owner, _ = get_user_model().objects.get_or_create(
            username=f"loan-doc-owner-{uuid.uuid4().hex[:8]}",
            defaults={"email": "loan-doc-owner@example.com"},
        )
        tenant.name = f"Loan document workspace {uuid.uuid4().hex[:8]}"
        tenant.owner = owner
        tenant.creator = owner

    def setUp(self):
        super().setUp()
        connection.set_tenant(self.tenant)
        self.actor = self.tenant.owner
        self.license = LoanLicense.objects.create(
            workspace=self.tenant,
            name="Document License",
            license_number=f"DOC-{uuid.uuid4().hex[:8]}",
            issued_on=date(2026, 1, 1),
            expires_on=date(2027, 1, 1),
            created_by=self.actor,
        )
        self.series = LoanSeries.objects.create(
            license=self.license, name="Document Series", code="DOC"
        )

    def _create_revision(self, *, name="Ticket Layout"):
        definition = starter_layout("loan_ticket").canonical_dict()
        return LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"{name} {uuid.uuid4().hex[:6]}",
            definition=definition,
            actor=self.actor,
        )

    def test_publish_is_immutable_and_clone_creates_next_draft(self):
        revision = self._create_revision()
        published = LoanDocumentLayoutService.publish(
            revision=revision, actor=self.actor
        )

        self.assertEqual(published.state, LoanDocumentLayoutRevision.State.PUBLISHED)
        self.assertTrue(published.published_at)
        published.definition = {**published.definition, "name": "Changed after publish"}
        with self.assertRaisesMessage(ValidationError, "immutable"):
            published.save()

        clone = LoanDocumentLayoutService.clone_revision(
            revision=published, actor=self.actor
        )
        self.assertEqual(clone.version, 2)
        self.assertEqual(clone.state, LoanDocumentLayoutRevision.State.DRAFT)
        self.assertEqual(clone.content_hash, revision.content_hash)

    def test_publish_fails_when_layout_asset_is_missing(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["blocks"].insert(
            1, {"type": "image", "asset_key": "business.logo"}
        )
        revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Missing asset {uuid.uuid4().hex[:6]}",
            definition=definition,
            actor=self.actor,
        )

        with self.assertRaisesMessage(DocumentLayoutServiceError, "assets are missing"):
            LoanDocumentLayoutService.publish(revision=revision, actor=self.actor)

    def test_assignment_resolution_is_series_then_license_then_workspace(self):
        workspace_revision = LoanDocumentLayoutService.publish(
            revision=self._create_revision(name="Workspace"), actor=self.actor
        )
        license_revision = LoanDocumentLayoutService.publish(
            revision=self._create_revision(name="License"), actor=self.actor
        )
        series_revision = LoanDocumentLayoutService.publish(
            revision=self._create_revision(name="Series"), actor=self.actor
        )
        LoanDocumentLayoutService.assign(
            revision=workspace_revision, workspace=self.tenant, actor=self.actor
        )
        LoanDocumentLayoutService.assign(
            revision=license_revision, workspace=self.tenant,
            license=self.license, actor=self.actor,
        )
        LoanDocumentLayoutService.assign(
            revision=series_revision, workspace=self.tenant,
            license=self.license, series=self.series, actor=self.actor,
        )

        self.assertEqual(
            LoanDocumentLayoutService.resolve(
                workspace=self.tenant, document_type="loan_ticket",
                license=self.license, series=self.series,
            ).pk,
            series_revision.pk,
        )
        self.assertEqual(
            LoanDocumentLayoutService.resolve(
                workspace=self.tenant, document_type="loan_ticket",
                license=self.license,
            ).pk,
            license_revision.pk,
        )

        replacement = LoanDocumentLayoutService.publish(
            revision=self._create_revision(name="Replacement"), actor=self.actor
        )
        LoanDocumentLayoutService.assign(
            revision=replacement, workspace=self.tenant, actor=self.actor
        )
        workspace_revision.refresh_from_db()
        self.assertEqual(
            LoanDocumentLayoutService.resolve(
                workspace=self.tenant, document_type="loan_ticket"
            ).pk,
            replacement.pk,
        )

    def test_official_issue_stores_exact_bytes_is_idempotent_and_regenerates(self):
        revision = LoanDocumentLayoutService.publish(
            revision=self._create_revision(), actor=self.actor
        )
        pdf = b"%PDF-1.4\nexact-issued-bytes\n%%EOF"
        render = SimpleNamespace(
            pdf=pdf,
            renderer_version="layout-reportlab-v1",
            payload_hash="a" * 64,
            layout_hash=revision.content_hash,
            asset_hashes=(("business.logo", "b" * 64),),
        )
        kwargs = dict(
            workspace=self.tenant,
            document_type="loan_ticket",
            source_type="PawnLoan",
            source_id="19",
            source_fingerprint="approval-fingerprint-1",
            payload_schema_version=1,
            render_result=render,
            filename="ticket-19.pdf",
            actor=self.actor,
            revision=revision,
            print_profile=ResolvedPrintProfile(
                source_scope="LEGACY_LAYOUT",
                definition=legacy_print_profile(
                    DocumentLayoutValidator.load(revision.definition)
                ),
            ),
        )

        issue = LoanDocumentLayoutService.issue(**kwargs)
        same = LoanDocumentLayoutService.issue(**kwargs)
        regenerated = LoanDocumentLayoutService.issue(**kwargs, prior_issue=issue)

        self.assertEqual(same.pk, issue.pk)
        self.assertEqual(issue.pdf_hash, hashlib.sha256(pdf).hexdigest())
        issue.artifact.open("rb")
        self.assertEqual(issue.artifact.read(), pdf)
        issue.artifact.close()
        self.assertEqual(regenerated.issue_kind, LoanDocumentIssue.Kind.REGENERATED)
        self.assertEqual(regenerated.prior_issue_id, issue.pk)
        self.assertEqual(issue.print_profile_source_scope, "LEGACY_LAYOUT")
        self.assertEqual(issue.print_profile_name, "Legacy embedded Legacy Original")
        self.assertEqual(issue.print_profile_version, 1)
        self.assertEqual(
            issue.print_profile_hash,
            kwargs["print_profile"].definition.content_hash,
        )
        issue.pdf_hash = "c" * 64
        with self.assertRaisesMessage(ValidationError, "immutable"):
            issue.save()

    def test_retire_deactivates_assignments_and_cannot_be_reassigned(self):
        revision = LoanDocumentLayoutService.publish(
            revision=self._create_revision(), actor=self.actor
        )
        assignment = LoanDocumentLayoutService.assign(
            revision=revision, workspace=self.tenant, actor=self.actor
        )
        LoanDocumentLayoutService.retire(revision=revision, actor=self.actor)
        assignment.refresh_from_db()
        self.assertFalse(assignment.is_active)
        with self.assertRaisesMessage(DocumentLayoutServiceError, "Only published"):
            LoanDocumentLayoutService.assign(
                revision=revision, workspace=self.tenant, actor=self.actor
            )

    def test_sanitized_pack_import_is_always_a_new_draft(self):
        source = self._create_revision(name="Pack source")

        content = export_layout_pack(source)
        imported = import_layout_pack(
            workspace=self.tenant, content=content, actor=self.actor,
            name=f"Imported {uuid.uuid4().hex[:6]}",
        )

        self.assertTrue(content.startswith(b"PK"))
        self.assertEqual(imported.state, LoanDocumentLayoutRevision.State.DRAFT)
        self.assertNotEqual(imported.layout_id, source.layout_id)
        self.assertEqual(imported.content_hash, source.content_hash)
        self.assertFalse(imported.assignments.exists())

    def test_integrity_selector_detects_canonical_layout_hash_drift(self):
        revision = self._create_revision(name="Integrity")
        self.assertEqual(get_document_integrity_findings(), ())

        LoanDocumentLayoutRevision.objects.filter(pk=revision.pk).update(
            content_hash="0" * 64
        )
        findings = get_document_integrity_findings()

        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "LAYOUT_HASH")

    def test_integrity_selector_requires_both_ticket_copies_for_pilot_assignment(self):
        single = LoanDocumentLayoutService.publish(
            revision=self._create_revision(name="Single copy"), actor=self.actor
        )
        LoanDocumentLayoutService.assign(
            revision=single, workspace=self.tenant, actor=self.actor
        )

        findings = get_document_integrity_findings()

        self.assertEqual(
            [finding.category for finding in findings],
            ["PILOT_TICKET_COPY_BUNDLE"],
        )

        definition = starter_layout("loan_ticket").canonical_dict()
        definition["copy_mode"] = "ORIGINAL_DUPLICATE"
        dual = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Dual copy {uuid.uuid4().hex[:6]}",
            definition=definition,
            actor=self.actor,
        )
        dual = LoanDocumentLayoutService.publish(revision=dual, actor=self.actor)
        LoanDocumentLayoutService.assign(
            revision=dual, workspace=self.tenant, actor=self.actor
        )

        self.assertEqual(get_document_integrity_findings(), ())

    def test_integrity_selector_requires_both_signature_roles_on_each_ticket_copy(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["copy_mode"] = "ORIGINAL_DUPLICATE"
        definition["blocks"] = [
            block for block in definition["blocks"] if block["type"] != "signature"
        ]
        unsigned = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Unsigned ticket {uuid.uuid4().hex[:6]}",
            definition=definition,
            actor=self.actor,
        )
        unsigned = LoanDocumentLayoutService.publish(
            revision=unsigned,
            actor=self.actor,
        )
        LoanDocumentLayoutService.assign(
            revision=unsigned,
            workspace=self.tenant,
            actor=self.actor,
        )

        findings = get_document_integrity_findings()

        self.assertEqual(
            [finding.category for finding in findings],
            ["PILOT_TICKET_SIGNATURES"],
        )

    def test_integrity_selector_requires_release_signatures(self):
        definition = starter_layout("release_memo").canonical_dict()
        definition["blocks"] = [
            block for block in definition["blocks"] if block["type"] != "signature"
        ]
        unsigned = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="release_memo",
            name=f"Unsigned release {uuid.uuid4().hex[:6]}",
            definition=definition,
            actor=self.actor,
        )
        unsigned = LoanDocumentLayoutService.publish(
            revision=unsigned,
            actor=self.actor,
        )
        LoanDocumentLayoutService.assign(
            revision=unsigned,
            workspace=self.tenant,
            actor=self.actor,
        )

        findings = get_document_integrity_findings()

        self.assertEqual(
            [finding.category for finding in findings],
            ["PILOT_RELEASE_SIGNATURES"],
        )

    def test_integrity_selector_rejects_incompatible_resolved_profile_pair(self):
        definition = starter_layout("loan_ticket").canonical_dict()
        definition["copy_mode"] = "ORIGINAL_DUPLICATE"
        layout_revision = LoanDocumentLayoutService.create_layout(
            workspace=self.tenant,
            document_type="loan_ticket",
            name=f"Pair layout {uuid.uuid4().hex[:6]}",
            definition=definition,
            actor=self.actor,
        )
        layout_revision = LoanDocumentLayoutService.publish(
            revision=layout_revision, actor=self.actor
        )
        LoanDocumentLayoutService.assign(
            revision=layout_revision,
            workspace=self.tenant,
            series=self.series,
            actor=self.actor,
        )
        profile_definition = built_in_print_profile(
            "A5_BOTH_DUPLEX"
        ).canonical_dict()
        profile_definition["name"] = "Missing backs"
        profile_revision = LoanDocumentPrintProfileService.create_profile(
            workspace=self.tenant,
            document_type="loan_ticket",
            name="Missing backs",
            definition=profile_definition,
            actor=self.actor,
        )
        profile_revision = LoanDocumentPrintProfileService.publish(
            revision=profile_revision, actor=self.actor
        )
        LoanDocumentPrintProfileService.assign(
            revision=profile_revision,
            workspace=self.tenant,
            series=self.series,
            actor=self.actor,
        )

        self.assertIn(
            "PRINT_PROFILE_LAYOUT_PAIR",
            [finding.category for finding in get_document_integrity_findings()],
        )
