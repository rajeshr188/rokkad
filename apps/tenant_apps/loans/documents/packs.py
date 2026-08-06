"""Sanitized, non-executable layout-pack export and draft-only import."""

import io
import json
import zipfile
from pathlib import Path
from django.db import transaction

from apps.tenant_apps.loans.documents.layouts import DocumentLayoutValidator
from apps.tenant_apps.loans.services.document_layouts import LoanDocumentLayoutService


class LayoutPackError(ValueError):
    pass


PACK_VERSION = 1
MAX_PACK_BYTES = 20 * 1024 * 1024
MAX_FILES = 20


def export_layout_pack(revision):
    manifest = {
        "pack_version": PACK_VERSION,
        "document_type": revision.layout.document_type,
        "name": revision.layout.name,
        "definition": revision.definition,
        "assets": [],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index, asset in enumerate(revision.assets.order_by("key")):
            asset.file.open("rb"); content = asset.file.read(); asset.file.close()
            suffix = ".pdf" if asset.mime_type == "application/pdf" else ".png" if asset.mime_type == "image/png" else ".jpg"
            path = f"assets/{index:02d}{suffix}"
            archive.writestr(path, content)
            manifest["assets"].append({"key": asset.key, "kind": asset.kind, "path": path, "sha256": asset.sha256})
        archive.writestr("manifest.json", json.dumps(manifest, sort_keys=True, separators=(",", ":")))
    value = buffer.getvalue()
    if len(value) > MAX_PACK_BYTES:
        raise LayoutPackError("Exported layout pack exceeds the size limit.")
    return value


@transaction.atomic
def import_layout_pack(*, workspace, content, actor=None, request=None, name=None):
    if not isinstance(content, bytes) or not content or len(content) > MAX_PACK_BYTES:
        raise LayoutPackError("Layout pack is empty or exceeds the size limit.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(content), "r")
    except zipfile.BadZipFile as exc:
        raise LayoutPackError("Layout pack is not a valid ZIP archive.") from exc
    with archive:
        names = archive.namelist()
        if len(names) > MAX_FILES or "manifest.json" not in names:
            raise LayoutPackError("Layout pack structure is invalid.")
        if sum(item.file_size for item in archive.infolist()) > MAX_PACK_BYTES:
            raise LayoutPackError("Layout pack expands beyond the size limit.")
        for path in names:
            pure = Path(path)
            if pure.is_absolute() or ".." in pure.parts or path.startswith(("/", "\\")):
                raise LayoutPackError("Layout pack contains an unsafe path.")
        try:
            manifest = json.loads(archive.read("manifest.json"))
        except (KeyError, ValueError, UnicodeDecodeError) as exc:
            raise LayoutPackError("Layout pack manifest is invalid.") from exc
        if set(manifest) != {"pack_version", "document_type", "name", "definition", "assets"} or manifest.get("pack_version") != PACK_VERSION:
            raise LayoutPackError("Layout pack manifest version or properties are invalid.")
        parsed = DocumentLayoutValidator.load(manifest["definition"])
        if parsed.document_type != manifest["document_type"]:
            raise LayoutPackError("Layout pack document type is inconsistent.")
        assets = manifest.get("assets")
        if not isinstance(assets, list) or len(assets) > MAX_FILES - 1:
            raise LayoutPackError("Layout pack asset list is invalid.")
        loaded = []
        for item in assets:
            if not isinstance(item, dict) or set(item) != {"key", "kind", "path", "sha256"} or item["path"] not in names:
                raise LayoutPackError("Layout pack asset entry is invalid.")
            value = archive.read(item["path"])
            import hashlib
            if hashlib.sha256(value).hexdigest() != item["sha256"]:
                raise LayoutPackError("Layout pack asset hash mismatch.")
            loaded.append((item, value))
    revision = LoanDocumentLayoutService.create_layout(
        workspace=workspace, document_type=parsed.document_type,
        name=(name or f"{manifest['name']} (Imported)")[:100],
        definition=parsed.canonical_dict(), actor=actor, request=request,
    )
    for item, value in loaded:
        LoanDocumentLayoutService.add_asset(
            revision=revision, key=item["key"], kind=item["kind"], content=value,
            filename=Path(item["path"]).name, actor=actor,
        )
    return revision


__all__ = ["LayoutPackError", "export_layout_pack", "import_layout_pack"]
