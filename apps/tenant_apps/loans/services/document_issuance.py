"""Application service for configurable official document issuance."""

from dataclasses import dataclass

from apps.tenant_apps.loans.documents import (
    ConfigurableDocumentRenderer,
    DocumentAsset,
    DocumentLayoutValidator,
    legacy_print_profile,
)
from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService
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
        return ConfigurableDocumentIssueResult(None, use_fixed_renderer=True)
    layout = DocumentLayoutValidator.load(revision.definition)
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
