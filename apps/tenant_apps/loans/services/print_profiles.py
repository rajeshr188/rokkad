"""Versioned print-profile persistence and deterministic scope resolution."""

from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from django_tenants.utils import get_public_schema_name, schema_context

from apps.orgs.audit import AuditLog
from apps.tenant_apps.loans.documents import (
    PrintProfileDefinition,
    PrintProfileValidator,
    built_in_print_profile,
)
from apps.tenant_apps.loans.models import (
    LoanDocumentPrintProfile,
    LoanDocumentPrintProfileAssignment,
    LoanDocumentPrintProfileRevision,
    current_tenant_workspace_id,
)


class PrintProfileServiceError(ValueError):
    pass


@dataclass(frozen=True)
class ResolvedPrintProfile:
    source_scope: str
    definition: PrintProfileDefinition
    revision: LoanDocumentPrintProfileRevision | None = None

    @property
    def content_hash(self):
        return self.definition.content_hash

    @property
    def is_built_in(self):
        return self.revision is None


def _require_workspace(workspace_id):
    active = current_tenant_workspace_id()
    if active is None:
        raise PrintProfileServiceError(
            "Print profile operations require an active tenant schema."
        )
    if active != workspace_id:
        raise PrintProfileServiceError("Print profile belongs to another workspace.")


class LoanDocumentPrintProfileService:
    @classmethod
    @transaction.atomic
    def create_profile(
        cls, *, workspace, document_type, name, definition, actor=None, request=None
    ):
        _require_workspace(workspace.pk)
        parsed = PrintProfileValidator.load(definition)
        if parsed.document_type != document_type or parsed.name != str(name).strip():
            raise PrintProfileServiceError(
                "Print profile definition identity does not match the profile."
            )
        profile = LoanDocumentPrintProfile.objects.create(
            workspace=workspace,
            document_type=document_type,
            name=parsed.name,
            created_by=actor,
        )
        revision = LoanDocumentPrintProfileRevision.objects.create(
            profile=profile,
            version=1,
            definition=parsed.canonical_dict(),
            content_hash=parsed.content_hash,
            validation_result={"valid": True},
            validated_at=timezone.now(),
            created_by=actor,
        )
        cls._audit(profile, actor, request, "created", {
            "revision_id": revision.pk, "hash": parsed.content_hash,
        })
        return revision

    @classmethod
    @transaction.atomic
    def clone_revision(cls, *, revision, actor=None, request=None):
        profile = LoanDocumentPrintProfile.objects.select_for_update().get(
            pk=revision.profile_id
        )
        _require_workspace(profile.workspace_id)
        latest = profile.revisions.order_by("-version").first()
        clone = LoanDocumentPrintProfileRevision.objects.create(
            profile=profile,
            version=(latest.version if latest else 0) + 1,
            definition=revision.definition,
            content_hash=revision.content_hash,
            validation_result=revision.validation_result,
            validated_at=revision.validated_at,
            created_by=actor,
        )
        cls._audit(profile, actor, request, "cloned", {
            "from": revision.pk, "to": clone.pk,
        })
        return clone

    @classmethod
    @transaction.atomic
    def update_draft(cls, *, revision, definition, actor=None, request=None):
        revision = LoanDocumentPrintProfileRevision.objects.select_for_update().select_related(
            "profile"
        ).get(pk=revision.pk)
        _require_workspace(revision.profile.workspace_id)
        if revision.state != revision.State.DRAFT:
            raise PrintProfileServiceError("Only draft print profile revisions can be edited.")
        parsed = PrintProfileValidator.load(definition)
        if (
            parsed.document_type != revision.profile.document_type
            or parsed.name != revision.profile.name
        ):
            raise PrintProfileServiceError(
                "Print profile definition identity does not match the profile."
            )
        revision.definition = parsed.canonical_dict()
        revision.content_hash = parsed.content_hash
        revision.validation_result = {"valid": True}
        revision.validated_at = timezone.now()
        revision.save(update_fields=(
            "definition", "content_hash", "validation_result", "validated_at"
        ))
        cls._audit(revision.profile, actor, request, "draft_updated", {
            "revision_id": revision.pk, "hash": parsed.content_hash,
        })
        return revision

    @classmethod
    @transaction.atomic
    def publish(cls, *, revision, actor=None, request=None):
        revision = LoanDocumentPrintProfileRevision.objects.select_for_update().select_related(
            "profile"
        ).get(pk=revision.pk)
        _require_workspace(revision.profile.workspace_id)
        if revision.state != revision.State.DRAFT:
            raise PrintProfileServiceError("Only draft print profile revisions can be published.")
        parsed = PrintProfileValidator.load(revision.definition)
        if (
            parsed.document_type != revision.profile.document_type
            or parsed.name != revision.profile.name
        ):
            raise PrintProfileServiceError(
                "Print profile definition identity does not match the profile."
            )
        revision.definition = parsed.canonical_dict()
        revision.content_hash = parsed.content_hash
        revision.validation_result = {"valid": True}
        revision.validated_at = revision.validated_at or timezone.now()
        revision.state = revision.State.PUBLISHED
        revision.published_at = timezone.now()
        revision.save()
        cls._audit(revision.profile, actor, request, "published", {
            "revision_id": revision.pk, "hash": parsed.content_hash,
        })
        return revision

    @classmethod
    @transaction.atomic
    def retire(cls, *, revision, actor=None, request=None):
        revision = LoanDocumentPrintProfileRevision.objects.select_for_update().select_related(
            "profile"
        ).get(pk=revision.pk)
        _require_workspace(revision.profile.workspace_id)
        if revision.state != revision.State.PUBLISHED:
            raise PrintProfileServiceError("Only published print profile revisions can be retired.")
        revision.state = revision.State.RETIRED
        revision.retired_at = timezone.now()
        revision.save(update_fields=("state", "retired_at"))
        revision.assignments.filter(is_active=True).update(is_active=False)
        cls._audit(revision.profile, actor, request, "retired", {
            "revision_id": revision.pk,
        })
        return revision

    @classmethod
    @transaction.atomic
    def assign(
        cls, *, revision, workspace, series=None, actor=None, request=None
    ):
        _require_workspace(workspace.pk)
        if series is not None and series.license.workspace_id != workspace.pk:
            raise PrintProfileServiceError("Series belongs to another workspace.")
        revision = LoanDocumentPrintProfileRevision.objects.select_for_update().select_related(
            "profile"
        ).get(pk=revision.pk)
        if revision.state != revision.State.PUBLISHED:
            raise PrintProfileServiceError("Only published print profile revisions can be assigned.")
        if revision.profile.workspace_id != workspace.pk:
            raise PrintProfileServiceError("Print profile belongs to another workspace.")
        definition = PrintProfileValidator.load(revision.definition)
        if definition.content_hash != revision.content_hash:
            raise PrintProfileServiceError(
                "Published print profile hash does not match its definition."
            )
        if revision.profile.document_type == "loan_ticket" and not {
            "ORIGINAL_FRONT", "DUPLICATE_FRONT"
        }.issubset(definition.included_surfaces):
            raise PrintProfileServiceError(
                "The pilot loan-ticket profile must include Original and Duplicate fronts."
            )
        scope = LoanDocumentPrintProfileAssignment.objects.select_for_update().filter(
            workspace=workspace,
            document_type=revision.profile.document_type,
            series=series,
            is_active=True,
        )
        replaced = list(scope.values_list("pk", flat=True))
        scope.update(is_active=False)
        assignment = LoanDocumentPrintProfileAssignment.objects.create(
            workspace=workspace,
            document_type=revision.profile.document_type,
            revision=revision,
            series=series,
            created_by=actor,
        )
        cls._audit(revision.profile, actor, request, "assigned", {
            "assignment_id": assignment.pk,
            "replaced": replaced,
            "series_id": getattr(series, "pk", None),
        })
        return assignment

    @staticmethod
    def resolve(*, workspace, document_type, series=None):
        _require_workspace(workspace.pk)
        base = LoanDocumentPrintProfileAssignment.objects.filter(
            workspace=workspace,
            document_type=document_type,
            is_active=True,
            revision__state=LoanDocumentPrintProfileRevision.State.PUBLISHED,
        ).select_related("revision", "revision__profile")
        assignment = base.filter(series=series).first() if series is not None else None
        source_scope = "SERIES"
        if assignment is None:
            assignment = base.filter(series__isnull=True).first()
            source_scope = "WORKSPACE"
        if assignment is None:
            if document_type != "loan_ticket":
                return None
            definition = built_in_print_profile()
            return ResolvedPrintProfile("BUILT_IN", definition)
        definition = PrintProfileValidator.load(assignment.revision.definition)
        if definition.content_hash != assignment.revision.content_hash:
            raise PrintProfileServiceError(
                "Published print profile hash does not match its definition."
            )
        return ResolvedPrintProfile(source_scope, definition, assignment.revision)

    @staticmethod
    def _audit(profile, actor, request, verb, data):
        with schema_context(get_public_schema_name()):
            AuditLog.log(
                "SETTINGS_UPDATE",
                user=actor,
                company=profile.workspace,
                description=f"Loan document print profile {verb}: {profile.name}.",
                data={
                    "entity": "loan_document_print_profile",
                    "profile_id": profile.pk,
                    "event": verb,
                    **data,
                },
                request=request,
                success=True,
            )


__all__ = [
    "LoanDocumentPrintProfileService",
    "PrintProfileServiceError",
    "ResolvedPrintProfile",
]
