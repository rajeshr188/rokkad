"""Current photographs on new recorded entry, bound to review and atomic admission."""
import hashlib
import logging

from django.db import transaction

from .collateral_media import validate_collateral_photo, _append_collateral_photo

logger = logging.getLogger(__name__)


def validate_manifest(rows):
    if not isinstance(rows, list) or len(rows) > 100:
        raise ValueError("Photograph selections exceed the supported item count.")
    seen = set()
    for row in rows:
        if (not isinstance(row, dict) or set(row) != {"item", "name", "sha256", "byte_size", "mime_type"}
                or type(row["item"]) is not int or not 1 <= row["item"] <= 100 or row["item"] in seen
                or not isinstance(row["name"], str) or not 1 <= len(row["name"]) <= 255
                or type(row["byte_size"]) is not int or not 1 <= row["byte_size"] <= 10 * 1024 * 1024
                or not isinstance(row["sha256"], str) or len(row["sha256"]) != 64
                or any(c not in "0123456789abcdef" for c in row["sha256"])
                or row["mime_type"] not in ("image/jpeg", "image/png")):
            raise ValueError("Photograph selections are malformed or refer to duplicate items.")
        seen.add(row["item"])
    return rows


def _data_with_photos(data, photos):
    rows = []
    for position, upload in photos:
        mime = validate_collateral_photo(upload)
        offset = upload.tell()
        digest = hashlib.sha256()
        for chunk in upload.chunks():
            digest.update(chunk)
        upload.seek(offset)
        rows.append(dict(item=position, name=upload.name[:255], sha256=digest.hexdigest(),
            byte_size=upload.size, mime_type=mime))
    result = dict(data)
    result.pop("entry_photos", None)  # Only files supplied to this command can establish selections.
    if rows:
        result["entry_photos"] = validate_manifest(rows)
    return result


def preview_recorded_entry(*, data, photos=(), **kwargs):
    from .recorded_history import preview_recorded_history
    return preview_recorded_history(data=_data_with_photos(data, photos), **kwargs)


def admit_recorded_entry(*, data, photos=(), **kwargs):
    from .recorded_history import admit_recorded_history
    photos = tuple(photos)
    data = _data_with_photos(data, photos)
    stored = []
    try:
        with transaction.atomic():
            loan, created = admit_recorded_history(data=data, **kwargs)
            if created:
                items = list(loan.collateral_items.order_by("pk"))
                for position, upload in photos:
                    if not 1 <= position <= len(items):
                        raise ValueError("A photograph could not be matched to its recorded collateral item.")
                    photo = _append_collateral_photo(items[position - 1].pk, upload=upload, actor=kwargs["actor"])
                    stored.append((photo.file.storage, photo.file.name))
            return loan, created
    except Exception:
        for storage, name in stored:
            try:
                storage.delete(name)
            except Exception as exc:
                logger.error("Rolled-back recorded-entry photo cleanup failed: %s (%s).", name, type(exc).__name__)
        raise
