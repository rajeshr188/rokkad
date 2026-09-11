"""Shared asset loading for authorized document preview views."""

from apps.tenant_apps.loans.documents import DocumentAsset


def _revision_assets(revision):
    values = []
    for asset in revision.assets.all():
        asset.file.open("rb")
        content = asset.file.read()
        asset.file.close()
        values.append(DocumentAsset(asset.key, asset.kind, asset.mime_type, content, asset.workspace_id, asset.sha256, asset.width, asset.height, asset.page_count))
    return tuple(values)
