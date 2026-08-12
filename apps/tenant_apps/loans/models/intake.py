"""Historical migration support for the removed collateral-intake models."""

import uuid


def intake_photo_upload_to(instance, filename):
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"loans/intake/{instance.item.batch.public_id}/{uuid.uuid4().hex}.{suffix}"
