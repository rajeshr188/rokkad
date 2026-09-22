"""Explicit private R2 opt-in for the new production deployment."""
import re

from botocore.config import Config
from django.core.exceptions import ImproperlyConfigured

from .prod import *  # noqa: F403

# This prefix is a durable deployment identity, not a release tag. Changing it
# requires copying/verifying existing objects before switching application reads.
_location = env("ROKKAD_PRODUCTION_MEDIA_LOCATION")  # noqa: F405
if not re.fullmatch(r"media/application/production/[a-z0-9][a-z0-9_-]{0,62}", _location):
    raise ImproperlyConfigured("ROKKAD_PRODUCTION_MEDIA_LOCATION must select media/application/production/<deployment-id>.")
if not re.fullmatch(r"https://[a-f0-9]{32}\.r2\.cloudflarestorage\.com", CLOUDFLARE_R2_BUCKET_ENDPOINT):  # noqa: F405
    raise ImproperlyConfigured("Production media requires an explicit HTTPS R2 S3 endpoint.")
for _name in ("CLOUDFLARE_R2_BUCKET", "CLOUDFLARE_R2_ACCESS_KEY", "CLOUDFLARE_R2_SECRET_KEY"):
    if not globals()[_name].strip():
        raise ImproperlyConfigured(f"{_name} must be nonempty for production media.")

STORAGES = {**STORAGES, "default": {  # noqa: F405
    "BACKEND": "helpers.cloudflare.storages.MediaFileStorage",
    "OPTIONS": {
        **CLOUDFLARE_R2_CONFIG_OPTIONS,  # noqa: F405
        "location": _location, "region_name": "auto", "addressing_style": "path",
        "custom_domain": None, "file_overwrite": False, "querystring_expire": 60,
        "object_parameters": {"CacheControl": "private, no-store"},
        "client_config": Config(signature_version="s3v4", connect_timeout=5, read_timeout=15,
            retries={"mode": "standard", "total_max_attempts": 2}, max_pool_connections=32, s3={"addressing_style": "path"},
            request_checksum_calculation="when_required", response_checksum_validation="when_required"),
    },
}}

# Intended topology: a private loopback application port behind our HTTPS proxy.
# Enable trust only after that proxy overwrites X-Forwarded-Proto itself.
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
if env.bool("ROKKAD_TRUST_HTTPS_PROXY", default=False):  # noqa: F405
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
