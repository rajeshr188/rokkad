"""Application service for configurable official document issuance."""

from dataclasses import dataclass
import hashlib
from types import SimpleNamespace

from django.core.exceptions import PermissionDenied
from django.db import transaction
from .action_access import require_loan_action

from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer,
    DocumentAsset,
    DocumentLayoutValidator,
    legacy_print_profile,
)
from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
from apps.tenant_apps.loans.services.documents import PawnLoanDocumentService
from apps.tenant_apps.loans.services.print_profiles import (
    LoanDocumentPrintProfileService,
    ResolvedPrintProfile,
)


@dataclass(frozen=True)
class ConfigurableDocumentIssueResult:
    issue: object | None
    use_fixed_renderer: bool = False


def issue_configurable_document(
    *, workspace, payload, loan, source_type, source_id, source_fingerprint,
    actor=None, request=None, fixed_recovery=False, legacy_profile_recovery=False,
) -> ConfigurableDocumentIssueResult:
    """Resolve, render, and persist an official issue, or request fixed fallback."""

    if workspace.pk != loan.workspace_id:
        raise PermissionDenied("Document workspace does not match the loan.")
    require_loan_action(loan, actor, "data.view")
    if fixed_recovery or legacy_profile_recovery:
        require_loan_action(loan, actor, "workspace.settings.manage")

    if fixed_recovery:
        LoanDocumentLayoutService.audit_fixed_recovery(
            workspace=workspace, source_type=source_type, source_id=source_id,
            actor=actor, request=request,
        )
        return ConfigurableDocumentIssueResult(None, use_fixed_renderer=True)
    existing = LoanDocumentLayoutService.find_official_issue(
        workspace=workspace, document_type=payload.document_type,
        source_type=source_type, source_id=source_id,
        source_fingerprint=source_fingerprint,
    )
    if existing is not None:
        return ConfigurableDocumentIssueResult(existing)
    revision = LoanDocumentLayoutService.resolve(
        workspace=workspace, document_type=payload.document_type,
        license=loan.license, series=loan.series,
    )
    if revision is None:
        result = PawnLoanDocumentService.render_payload(payload)
        rendered = SimpleNamespace(
            pdf=result.pdf, renderer_version="fixed-pawn-v1",
            payload_hash=hashlib.sha256(repr(payload).encode()).hexdigest(),
            layout_hash="", asset_hashes={},
        )
        issue = LoanDocumentLayoutService.issue(
            workspace=workspace, document_type=payload.document_type,
            source_type=source_type, source_id=source_id,
            source_fingerprint=source_fingerprint,
            payload_schema_version=payload.schema_version, render_result=rendered,
            filename=payload.file_name, actor=actor,
        )
        return ConfigurableDocumentIssueResult(issue)
    layout = DocumentLayoutValidator.load(revision.definition)
    if layout.schema_version >= 4 and payload.document_type == "loan_ticket":
        return _issue_precision_ticket(
            workspace=workspace, loan=loan, revision=revision, layout=layout,
            source_type=source_type, source_id=source_id, source_fingerprint=source_fingerprint,
            actor=actor, request=request, legacy_profile_recovery=legacy_profile_recovery,
        )
    print_profile = None
    assets = _revision_assets(revision)
    if payload.document_type == "loan_ticket":
        if legacy_profile_recovery:
            LoanDocumentLayoutService.audit_legacy_profile_recovery(
                workspace=workspace, source_type=source_type, source_id=source_id,
                actor=actor, request=request,
            )
            print_profile = ResolvedPrintProfile(
                source_scope="LEGACY_LAYOUT", definition=legacy_print_profile(layout),
            )
            rendered = ConfigurableDocumentRenderer.render(payload, layout, assets=assets)
        else:
            print_profile = LoanDocumentPrintProfileService.resolve(
                workspace=workspace, document_type=payload.document_type,
                series=loan.series,
            )
            rendered = ConfigurableDocumentRenderer.render_with_print_profile(
                payload, layout, print_profile.definition, assets=assets,
            )
    else:
        rendered = ConfigurableDocumentRenderer.render(payload, layout, assets=assets)
    issue = LoanDocumentLayoutService.issue(
        workspace=workspace, document_type=payload.document_type,
        source_type=source_type, source_id=source_id,
        source_fingerprint=source_fingerprint,
        payload_schema_version=payload.schema_version, render_result=rendered,
        filename=payload.file_name, actor=actor, revision=revision,
        print_profile=print_profile,
    )
    return ConfigurableDocumentIssueResult(issue)


@transaction.atomic
def _issue_precision_ticket(*, workspace, loan, revision, layout, source_type, source_id, source_fingerprint, actor, request, legacy_profile_recovery):
    from apps.tenant_apps.loans.models import PawnLoan
    from .ticket_documents import prepare_ticket_document

    if legacy_profile_recovery:
        raise ValueError("Precision tickets require a print profile; legacy recovery is unavailable.")
    # Serialize first issue before reading mutable Party facts or private media.
    loan = PawnLoan.objects.select_for_update().get(pk=loan.pk, workspace=workspace)
    existing = LoanDocumentLayoutService.find_official_issue(
        workspace=workspace, document_type="loan_ticket", source_type=source_type,
        source_id=source_id, source_fingerprint=source_fingerprint,
    )
    if existing:
        return ConfigurableDocumentIssueResult(existing)
    prepared = prepare_ticket_document(
        loan=loan, layout=layout, actor=actor,
        address_id=request.GET.get("address") if request else None,
    )
    if prepared.source_snapshot["approval_fingerprint"] != source_fingerprint:
        raise ValueError("Loan approval changed. Refresh before issuing the ticket.")
    profile = LoanDocumentPrintProfileService.resolve(workspace=workspace, document_type="loan_ticket", series=loan.series)
    result = ConfigurableDocumentRenderer.render_with_print_profile(
        prepared.payload, layout, profile.definition,
        assets=_revision_assets(revision) + prepared.assets,
    )
    issue = LoanDocumentLayoutService.issue(
        workspace=workspace, document_type="loan_ticket", source_type=source_type,
        source_id=source_id, source_fingerprint=source_fingerprint,
        payload_schema_version=2, render_result=result, filename=prepared.payload.file_name,
        actor=actor, revision=revision, print_profile=profile, source_snapshot=prepared.source_snapshot,
    )
    return ConfigurableDocumentIssueResult(issue)


def _revision_assets(revision):
    values = []
    for asset in revision.assets.all():
        asset.file.open("rb")
        try:
            content = asset.file.read()
        finally:
            asset.file.close()
        values.append(DocumentAsset(
            asset.key, asset.kind, asset.mime_type, content, asset.workspace_id,
            asset.sha256, asset.width, asset.height, asset.page_count,
        ))
    return tuple(values)


__all__ = ["ConfigurableDocumentIssueResult", "issue_configurable_document"]
