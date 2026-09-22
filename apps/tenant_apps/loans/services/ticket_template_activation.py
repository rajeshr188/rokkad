"""Publish and assign a ticket layout/profile pair in one transaction."""

from django.db import transaction

from apps.orgs.models import Company
from apps.tenant_apps.loans.documents import ConfigurableDocumentRenderer, DocumentLayoutValidator, PrintProfileValidator
from apps.tenant_apps.loans.models import (
    LoanDocumentLayoutAssignment, LoanDocumentLayoutRevision,
    LoanDocumentPrintProfileAssignment, LoanDocumentPrintProfileRevision, LoanSeries,
)
from .action_access import require_setup_administration
from .document_layouts import DocumentLayoutServiceError, LoanDocumentLayoutService
from .print_profiles import LoanDocumentPrintProfileService


@transaction.atomic
def use_ticket_template(*, workspace, revision, profile_revision, actor,
                        layout_hash, profile_hash, series=None, request=None):
    """Keep existing scope precedence, audit events and immutable publications."""
    require_setup_administration(workspace.pk, actor)
    # Serialize paired activations, including a scope with no previous assignment.
    Company.objects.select_for_update().get(pk=workspace.pk)
    revision = LoanDocumentLayoutRevision.objects.select_for_update().select_related("layout").get(
        pk=revision.pk, workspace=workspace)
    profile_revision = LoanDocumentPrintProfileRevision.objects.select_for_update().select_related("profile").get(
        pk=profile_revision.pk, workspace=workspace)
    if series is not None:
        series = LoanSeries.objects.select_related("license").get(pk=series.pk, workspace=workspace)
    if revision.layout.document_type != "loan_ticket" or profile_revision.profile.document_type != "loan_ticket":
        raise DocumentLayoutServiceError("Choose a loan-ticket template and print profile.")
    if revision.state not in {"DRAFT", "PUBLISHED"} or profile_revision.state not in {"DRAFT", "PUBLISHED"}:
        raise DocumentLayoutServiceError("Retired revisions cannot be used. Choose a current revision.")
    layout = DocumentLayoutValidator.load(revision.definition)
    profile = PrintProfileValidator.load(profile_revision.definition)
    if layout_hash != revision.content_hash or layout.content_hash != layout_hash or profile_hash != profile_revision.content_hash or profile.content_hash != profile_hash:
        raise DocumentLayoutServiceError("The template or paper settings changed. Review the selection again.")
    if layout.schema_version < 3:
        raise DocumentLayoutServiceError("Use separate assignment controls for legacy layouts.")
    ConfigurableDocumentRenderer.assert_print_profile_compatible(layout, profile)
    if revision.state == "DRAFT":
        revision = LoanDocumentLayoutService.publish(revision=revision, actor=actor, request=request)
    if profile_revision.state == "DRAFT":
        profile_revision = LoanDocumentPrintProfileService.publish(revision=profile_revision, actor=actor, request=request)

    layout_scope = LoanDocumentLayoutAssignment.objects.filter(
        workspace=workspace, document_type="loan_ticket", is_active=True,
        series=series, license=series.license if series else None)
    profile_scope = LoanDocumentPrintProfileAssignment.objects.filter(
        workspace=workspace, document_type="loan_ticket", is_active=True, series=series)
    if not layout_scope.filter(revision=revision).exists():
        LoanDocumentLayoutService.assign(revision=revision, workspace=workspace, series=series, actor=actor, request=request)
    if not profile_scope.filter(revision=profile_revision).exists():
        LoanDocumentPrintProfileService.assign(revision=profile_revision, workspace=workspace, series=series, actor=actor, request=request)

    # A workspace change can also affect a series whose profile override remains
    # in force. Validate both directions, not just the newly selected pair.
    candidates = (series,) if series else LoanSeries.objects.filter(workspace=workspace).select_related("license")
    for candidate in candidates:
        effective_layout = LoanDocumentLayoutService.resolve(
            workspace=workspace, document_type="loan_ticket", license=candidate.license, series=candidate)
        effective_profile = LoanDocumentPrintProfileService.resolve(
            workspace=workspace, document_type="loan_ticket", series=candidate)
        if effective_layout is not None:
            try:
                ConfigurableDocumentRenderer.assert_print_profile_compatible(
                    DocumentLayoutValidator.load(effective_layout.definition), effective_profile.definition)
            except ValueError as exc:
                raise DocumentLayoutServiceError(f"Series {candidate.code} has an incompatible override: {exc}") from exc
    return revision
