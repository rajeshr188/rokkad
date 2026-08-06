"""Validated, tenant-bound binary assets for configurable loan documents."""

import hashlib
import io
import re
from dataclasses import dataclass

import fitz
from PIL import Image as PillowImage


class DocumentAssetError(ValueError):
    pass


ASSET_KEY_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")


@dataclass(frozen=True)
class DocumentAsset:
    key: str
    kind: str
    mime_type: str
    content: bytes
    workspace_id: int
    sha256: str
    width: int | None = None
    height: int | None = None
    page_count: int | None = None


class DocumentAssetValidator:
    MAX_IMAGE_BYTES = 5 * 1024 * 1024
    MAX_PDF_BYTES = 10 * 1024 * 1024
    MAX_IMAGE_PIXELS = 20_000_000
    MAX_PDF_PAGES = 4

    @classmethod
    def validate(cls, *, key, kind, content, workspace_id):
        if not ASSET_KEY_RE.fullmatch(str(key or "")):
            raise DocumentAssetError("Asset key must be a safe lowercase identifier.")
        if kind not in {"IMAGE", "BACKGROUND"}:
            raise DocumentAssetError("Unsupported document asset kind.")
        if not isinstance(content, bytes) or not content:
            raise DocumentAssetError("Document asset content must be non-empty bytes.")
        if not isinstance(workspace_id, int) or workspace_id <= 0:
            raise DocumentAssetError("A valid workspace owns every document asset.")
        sha = hashlib.sha256(content).hexdigest()
        if content.startswith(b"%PDF-"):
            if kind != "BACKGROUND":
                raise DocumentAssetError("PDF assets may only be used as backgrounds.")
            if len(content) > cls.MAX_PDF_BYTES:
                raise DocumentAssetError("PDF background exceeds the size limit.")
            try:
                pdf = fitz.open(stream=content, filetype="pdf")
                pages = len(pdf)
                if not 1 <= pages <= cls.MAX_PDF_PAGES:
                    raise DocumentAssetError("PDF background page count is outside the supported limit.")
                pdf.close()
            except DocumentAssetError:
                raise
            except Exception as exc:
                raise DocumentAssetError("PDF background is corrupt or unreadable.") from exc
            return DocumentAsset(key, kind, "application/pdf", content, workspace_id, sha, page_count=pages)
        if len(content) > cls.MAX_IMAGE_BYTES:
            raise DocumentAssetError("Image asset exceeds the size limit.")
        try:
            image = PillowImage.open(io.BytesIO(content))
            image.verify()
            image = PillowImage.open(io.BytesIO(content))
            width, height = image.size
            mime = PillowImage.MIME.get(image.format)
        except Exception as exc:
            raise DocumentAssetError("Image asset is corrupt or unsupported.") from exc
        if mime not in {"image/png", "image/jpeg"}:
            raise DocumentAssetError("Only PNG and JPEG assets are supported.")
        if width <= 0 or height <= 0 or width * height > cls.MAX_IMAGE_PIXELS:
            raise DocumentAssetError("Image dimensions exceed the supported limit.")
        return DocumentAsset(key, kind, mime, content, workspace_id, sha, width, height)


def validate_asset_set(assets, *, workspace_id):
    result = {}
    for asset in assets or ():
        if not isinstance(asset, DocumentAsset):
            raise DocumentAssetError("Renderer assets must be validated DocumentAsset values.")
        if asset.workspace_id != workspace_id:
            raise DocumentAssetError("Document asset belongs to another workspace.")
        if asset.key in result:
            raise DocumentAssetError(f"Duplicate document asset key: {asset.key}.")
        result[asset.key] = asset
    return result


__all__ = ["DocumentAsset", "DocumentAssetError", "DocumentAssetValidator", "validate_asset_set"]
