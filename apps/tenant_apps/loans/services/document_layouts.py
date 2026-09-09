"""Atomic publication, assignment, asset, and official issue workflows."""

import hashlib
from pathlib import Path

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from .action_access import require_setup_administration
from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans.documents import DocumentAssetValidator, DocumentLayoutValidator
from apps.tenant_apps.loans.models import (
    LoanDocumentAsset,
    LoanDocumentIssue,
    LoanDocumentLayout,
    LoanDocumentLayoutAssignment,
    LoanDocumentLayoutRevision,
    current_tenant_workspace_id,
)


class DocumentLayoutServiceError(ValueError):
    pass


def _require_workspace(workspace_id):
    active = current_tenant_workspace_id()
    if active is None:
        raise DocumentLayoutServiceError("Document layout operations require an active Workspace context.")
    if active != workspace_id:
        raise DocumentLayoutServiceError("Document layout object belongs to another workspace.")


class LoanDocumentLayoutService:
    @staticmethod
    def audit_fixed_recovery(*, workspace, source_type, source_id, actor=None, request=None):
        _require_workspace(workspace.pk)
        AuditLog.log(
            "DATA_EXPORT", user=actor, company=workspace,
            description=f"Used fixed document recovery for {source_type}:{source_id}.",
            data={"entity": "loan_document_fixed_recovery", "source_type": source_type, "source_id": str(source_id)},
            request=request, success=True,
        )

    @staticmethod
    def audit_legacy_profile_recovery(
        *, workspace, source_type, source_id, actor=None, request=None
    ):
        _require_workspace(workspace.pk)
        AuditLog.log(
                "DATA_EXPORT", user=actor, company=workspace,
                description=(
                    f"Used legacy print-profile compatibility rendering for "
                    f"{source_type}:{source_id}."
                ),
                data={
                    "entity": "loan_document_legacy_profile_recovery",
                    "source_type": source_type,
                    "source_id": str(source_id),
                },
                request=request, success=True,
        )

    @staticmethod
    def find_official_issue(
        *, workspace, document_type, source_type, source_id, source_fingerprint
    ):
        _require_workspace(workspace.pk)
        return LoanDocumentIssue.objects.filter(
            workspace=workspace,
            document_type=document_type,
            source_type=source_type,
            source_id=str(source_id),
            source_fingerprint=source_fingerprint,
            issue_kind=LoanDocumentIssue.Kind.OFFICIAL,
        ).first()

    @classmethod
    @transaction.atomic
    def create_layout(cls, *, workspace, document_type, name, definition, actor=None, request=None):
        _require_workspace(workspace.pk)
        require_setup_administration(workspace.pk, actor)
        parsed = DocumentLayoutValidator.load(definition)
        if parsed.document_type != document_type:
            raise DocumentLayoutServiceError("Definition document type does not match the layout.")
        layout = LoanDocumentLayout.objects.create(workspace=workspace, document_type=document_type, name=name, created_by=actor)
        revision = LoanDocumentLayoutRevision.objects.create(
            layout=layout, version=1, definition=parsed.canonical_dict(),
            content_hash=parsed.content_hash, validation_result={"valid": True},
            validated_at=timezone.now(), created_by=actor,
        )
        cls._audit(layout, actor, request, "created", {"revision_id": revision.pk, "hash": parsed.content_hash})
        return revision

    @classmethod
    @transaction.atomic
    def clone_revision(cls, *, revision, actor=None, request=None):
        locked_layout = LoanDocumentLayout.objects.select_for_update().get(pk=revision.layout_id)
        _require_workspace(locked_layout.workspace_id)
        require_setup_administration(revision.layout.workspace_id, actor)
        latest = locked_layout.revisions.order_by("-version").first()
        clone = LoanDocumentLayoutRevision.objects.create(
            layout=locked_layout, version=(latest.version if latest else 0) + 1,
            definition=revision.definition, content_hash=revision.content_hash,
            validation_result=revision.validation_result, validated_at=revision.validated_at,
            created_by=actor,
        )
        for asset in revision.assets.all():
            asset.file.open("rb")
            content = asset.file.read()
            asset.file.close()
            cls.add_asset(revision=clone, key=asset.key, kind=asset.kind, content=content,
                          filename=Path(asset.file.name).name, actor=actor)
        cls._audit(locked_layout, actor, request, "cloned", {"from": revision.pk, "to": clone.pk})
        return clone

    @classmethod
    @transaction.atomic
    def update_draft(cls, *, revision, definition, actor=None, request=None):
        revision = LoanDocumentLayoutRevision.objects.select_for_update().select_related("layout").get(pk=revision.pk)
        _require_workspace(revision.layout.workspace_id)
        require_setup_administration(revision.layout.workspace_id, actor)
        if revision.state != revision.State.DRAFT:
            raise DocumentLayoutServiceError("Only draft revisions can be edited.")
        current = DocumentLayoutValidator.load(revision.definition)
        parsed = DocumentLayoutValidator.load(definition)
        if current.schema_version >= 3 and parsed.schema_version < 3:
            raise DocumentLayoutServiceError(
                "New logical-surface layouts cannot be downgraded to a legacy physical-composition schema."
            )
        if parsed.document_type != revision.layout.document_type:
            raise DocumentLayoutServiceError("Definition document type does not match the layout.")
        revision.definition = parsed.canonical_dict()
        revision.content_hash = parsed.content_hash
        revision.validation_result = {"valid": True}
        revision.validated_at = timezone.now()
        revision.save(update_fields=("definition", "content_hash", "validation_result", "validated_at"))
        cls._audit(revision.layout, actor, request, "draft_updated", {"revision_id": revision.pk, "hash": parsed.content_hash})
        return revision

    @classmethod
    @transaction.atomic
    def add_asset(cls, *, revision, key, kind, content, filename, actor=None):
        revision = LoanDocumentLayoutRevision.objects.select_for_update().select_related("layout").get(pk=revision.pk)
        _require_workspace(revision.layout.workspace_id)
        require_setup_administration(revision.layout.workspace_id, actor)
        if revision.state != revision.State.DRAFT:
            raise DocumentLayoutServiceError("Assets can be added only to draft revisions.")
        value = DocumentAssetValidator.validate(key=key, kind=kind, content=content, workspace_id=revision.layout.workspace_id)
        asset = LoanDocumentAsset(
            revision=revision, workspace=revision.layout.workspace, key=value.key, kind=value.kind,
            mime_type=value.mime_type, sha256=value.sha256, byte_size=len(value.content),
            width=value.width, height=value.height, page_count=value.page_count, created_by=actor,
        )
        asset.file.save(Path(filename).name, ContentFile(value.content), save=False)
        asset.save()
        cls._audit(revision.layout, actor, None, "asset_added", {
            "revision_id": revision.pk, "asset_id": asset.pk,
            "asset_key": asset.key, "asset_hash": asset.sha256,
        })
        return asset

    @classmethod
    @transaction.atomic
    def publish(cls, *, revision, actor=None, request=None):
        revision = LoanDocumentLayoutRevision.objects.select_for_update().select_related("layout").get(pk=revision.pk)
        _require_workspace(revision.layout.workspace_id)
        require_setup_administration(revision.layout.workspace_id, actor)
        if revision.state != revision.State.DRAFT:
            raise DocumentLayoutServiceError("Only draft revisions can be published.")
        parsed = DocumentLayoutValidator.load(revision.definition)
        available = set(revision.assets.values_list("key", flat=True))
        required = {block.asset_key for block in parsed.all_blocks() if block.asset_key}
        required.update(parsed.background_asset_keys())
        missing = required - available
        if missing:
            raise DocumentLayoutServiceError(f"Layout assets are missing: {', '.join(sorted(missing))}.")
        revision.definition = parsed.canonical_dict()
        revision.content_hash = parsed.content_hash
        revision.validation_result = {"valid": True, "asset_keys": sorted(required)}
        revision.validated_at = revision.validated_at or timezone.now()
        revision.state = revision.State.PUBLISHED
        revision.published_at = timezone.now()
        revision.save()
        cls._audit(revision.layout, actor, request, "published", {"revision_id": revision.pk, "hash": parsed.content_hash})
        return revision

    @classmethod
    @transaction.atomic
    def retire(cls, *, revision, actor=None, request=None):
        revision = LoanDocumentLayoutRevision.objects.select_for_update().select_related("layout").get(pk=revision.pk)
        _require_workspace(revision.layout.workspace_id)
        require_setup_administration(revision.layout.workspace_id, actor)
        if revision.state != revision.State.PUBLISHED:
            raise DocumentLayoutServiceError("Only published revisions can be retired.")
        revision.state = revision.State.RETIRED
        revision.retired_at = timezone.now()
        revision.save(update_fields=("state", "retired_at"))
        revision.assignments.filter(is_active=True).update(is_active=False)
        cls._audit(revision.layout, actor, request, "retired", {"revision_id": revision.pk})
        return revision

    @classmethod
    @transaction.atomic
    def assign(cls, *, revision, workspace, license=None, series=None, actor=None, request=None):
        _require_workspace(workspace.pk)
        require_setup_administration(workspace.pk, actor)
        if series is not None:
            if license is not None and series.license_id != license.pk:
                raise DocumentLayoutServiceError("Series does not belong to the selected license.")
            license = series.license
        revision = LoanDocumentLayoutRevision.objects.select_for_update().select_related("layout").get(pk=revision.pk)
        if revision.state != revision.State.PUBLISHED:
            raise DocumentLayoutServiceError("Only published revisions can be assigned.")
        scope = LoanDocumentLayoutAssignment.objects.select_for_update().filter(
            workspace=workspace, document_type=revision.layout.document_type,
            license=license, series=series, is_active=True,
        )
        old_ids = list(scope.values_list("pk", flat=True))
        scope.update(is_active=False)
        assignment = LoanDocumentLayoutAssignment.objects.create(
            workspace=workspace, document_type=revision.layout.document_type,
            revision=revision, license=license, series=series, created_by=actor,
        )
        cls._audit(revision.layout, actor, request, "assigned", {"assignment_id": assignment.pk, "replaced": old_ids,
                   "license_id": getattr(license, "pk", None), "series_id": getattr(series, "pk", None)})
        return assignment

    @staticmethod
    def resolve(*, workspace, document_type, license=None, series=None):
        _require_workspace(workspace.pk)
        base = LoanDocumentLayoutAssignment.objects.filter(
            workspace=workspace, document_type=document_type, is_active=True,
            revision__state=LoanDocumentLayoutRevision.State.PUBLISHED,
        ).select_related("revision", "revision__layout")
        if series is not None:
            match = base.filter(series=series).first()
            if match: return match.revision
        if license is not None:
            match = base.filter(series__isnull=True, license=license).first()
            if match: return match.revision
        match = base.filter(series__isnull=True, license__isnull=True).first()
        return match.revision if match else None

    @classmethod
    @transaction.atomic
    def issue(cls, *, workspace, document_type, source_type, source_id, source_fingerprint,
              payload_schema_version, render_result, filename, actor=None, revision=None,
              prior_issue=None, print_profile=None):
        _require_workspace(workspace.pk)
        existing = LoanDocumentIssue.objects.select_for_update().filter(
            workspace=workspace, document_type=document_type, source_type=source_type,
            source_id=str(source_id), source_fingerprint=source_fingerprint,
            issue_kind=LoanDocumentIssue.Kind.OFFICIAL,
        ).first()
        if prior_issue is None and existing:
            return existing
        if prior_issue is not None and prior_issue.workspace_id != workspace.pk:
            raise DocumentLayoutServiceError("Prior issue belongs to another workspace.")
        pdf_hash = hashlib.sha256(render_result.pdf).hexdigest()
        profile_revision = print_profile.revision if print_profile else None
        profile_definition = print_profile.definition if print_profile else None
        issue = LoanDocumentIssue(
            workspace=workspace, document_type=document_type,
            issue_kind=LoanDocumentIssue.Kind.REGENERATED if prior_issue else LoanDocumentIssue.Kind.OFFICIAL,
            source_type=source_type, source_id=str(source_id), source_fingerprint=source_fingerprint,
            revision=revision, fixed_renderer_version="" if revision else render_result.renderer_version,
            print_profile_revision=profile_revision,
            print_profile_name=profile_definition.name if profile_definition else "",
            print_profile_version=(
                profile_revision.version if profile_revision else
                (profile_definition.schema_version if profile_definition else None)
            ),
            print_profile_hash=print_profile.content_hash if print_profile else "",
            print_profile_source_scope=print_profile.source_scope if print_profile else "",
            payload_schema_version=payload_schema_version, payload_hash=render_result.payload_hash,
            layout_hash=render_result.layout_hash, asset_hashes=dict(render_result.asset_hashes),
            pdf_hash=pdf_hash, prior_issue=prior_issue, issued_by=actor,
        )
        issue.artifact.save(Path(filename).name, ContentFile(render_result.pdf), save=False)
        issue.save()
        AuditLog.log(
                "DATA_CREATE", user=actor, company=workspace,
                description=f"Issued {document_type} for {source_type}:{source_id}.",
                data={"entity": "loan_document_issue", "issue_id": issue.pk,
                      "issue_kind": issue.issue_kind, "pdf_hash": pdf_hash,
                      "print_profile_hash": issue.print_profile_hash,
                      "print_profile_source_scope": issue.print_profile_source_scope,
                      "prior_issue_id": issue.prior_issue_id}, success=True,
        )
        return issue

    @staticmethod
    def _audit(layout, actor, request, verb, data):
        AuditLog.log("SETTINGS_UPDATE", user=actor, company=layout.workspace,
                     description=f"Loan document layout {verb}: {layout.name}.",
                     data={"entity": "loan_document_layout", "layout_id": layout.pk, "event": verb, **data},
                     request=request, success=True)


__all__ = ["DocumentLayoutServiceError", "LoanDocumentLayoutService"]
