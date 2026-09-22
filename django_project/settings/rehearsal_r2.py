"""Explicit private R2 opt-in for an isolated rehearsal, never production credentials."""
import json
import os
import re
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from botocore.config import Config

from .baseline_rehearsal_web import *  # noqa: F403

_credential_path = os.environ.get("ROKKAD_REHEARSAL_R2_CREDENTIALS")
if not _credential_path:
    raise ImproperlyConfigured("Select the protected rehearsal R2 credential file explicitly.")
_credentials = json.loads(Path(_credential_path).read_text(encoding="utf-8-sig"))
if not re.fullmatch(r"https://[a-f0-9]{32}\.r2\.cloudflarestorage\.com", _credentials["endpoint_url"]):
    raise ImproperlyConfigured("Use the approved HTTPS R2 S3 endpoint.")
LEGACY_MEDIA_BUCKET = _credentials["bucket"]
LEGACY_MEDIA_LOCATION = "media/application/" + REHEARSAL_DATABASE_NAME  # noqa: F405
STORAGES["default"] = {  # noqa: F405
    "BACKEND": "helpers.cloudflare.storages.MediaFileStorage",
    "OPTIONS": {
        "access_key": _credentials["access_key_id"], "secret_key": _credentials["secret_access_key"],
        "bucket_name": LEGACY_MEDIA_BUCKET, "endpoint_url": _credentials["endpoint_url"],
        "region_name": "auto", "signature_version": "s3v4", "addressing_style": "path",
        "location": LEGACY_MEDIA_LOCATION, "default_acl": None, "custom_domain": None,
        "file_overwrite": False, "querystring_auth": True, "querystring_expire": 60,
        "object_parameters": {"CacheControl": "private, no-store"},
        "client_config": Config(signature_version="s3v4", connect_timeout=15, read_timeout=30,
            retries={"max_attempts": 3}, max_pool_connections=32, s3={"addressing_style": "path"},
            request_checksum_calculation="when_required", response_checksum_validation="when_required"),
    },
}
del _credentials
