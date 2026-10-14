"""Offline diagnostics only: presence of credentials is not delivery acceptance."""
import hashlib
import re
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError

from .phones import normalize_phone


def configuration_fingerprint():
    values = [str(getattr(settings, "PLATFORM_WHATSAPP_" + key, "")) for key in
              ("PHONE_ID", "WABA_ID", "APP_SECRET", "VERIFY_TOKEN", "VERSION")]
    return hashlib.sha256("\0".join(values).encode()).hexdigest()


def inbound_blockers():
    problems = []
    if not getattr(settings, "PLATFORM_WHATSAPP_INBOUND_ENABLED", False):
        problems.append("inbound_disabled")
    for key in ("PHONE_ID", "WABA_ID"):
        if not re.fullmatch(r"[0-9]{1,64}", str(getattr(settings, "PLATFORM_WHATSAPP_" + key, ""))):
            problems.append(key.lower() + "_missing_or_invalid")
    for key in ("APP_SECRET", "VERIFY_TOKEN"):
        if not getattr(settings, "PLATFORM_WHATSAPP_" + key, ""):
            problems.append(key.lower() + "_missing")
    return problems


def readiness():
    problems = inbound_blockers()
    try:
        sender_number = normalize_phone(getattr(settings, "PLATFORM_WHATSAPP_SENDER_NUMBER", ""))
    except ValidationError:
        sender_number = ""
        problems.append("sender_number_missing_or_invalid")
    try:
        origin = urlsplit(getattr(settings, "PLATFORM_WHATSAPP_BASE_URL", ""))
        valid = (origin.scheme == "https" and origin.hostname and not origin.username and
                 not origin.password and origin.path in ("", "/") and not origin.query and
                 not origin.fragment and (origin.port is None or origin.port > 0))
    except ValueError:
        valid = False
    if not valid:
        problems.append("canonical_https_origin_missing_or_invalid")
    return {"mode": "preview", "can_send": False, "inbound_ready": not inbound_blockers(),
            "blockers": problems + transport_blockers(),
            "sender_number": sender_number, "callback_path": "/app/integrations/whatsapp/webhook/"}


def release_blockers():
    from .controls import pilot
    try:
        pilot()
    except ValidationError:
        return ["dated_pilot_controls_required"]
    return []


def transport_blockers():
    problems = inbound_blockers() + release_blockers()
    if not getattr(settings, "PLATFORM_WHATSAPP_DISPATCH_ENABLED", False):
        problems.append("dispatch_disabled")
    token = getattr(settings, "PLATFORM_WHATSAPP_ACCESS_TOKEN", "")
    if not isinstance(token, str) or not token.strip() or any(c.isspace() for c in token):
        problems.append("access_token_missing_or_invalid")
    if not re.fullmatch(r"v[0-9]{1,3}\.[0-9]{1,2}", getattr(settings, "PLATFORM_WHATSAPP_API_VERSION", "")):
        problems.append("api_version_missing_or_invalid")
    for key in ("RETENTION_REFERENCE", "SUPPORT_MONITOR"):
        value = getattr(settings, "PLATFORM_WHATSAPP_" + key, "")
        if not isinstance(value, str) or not value.strip() or len(value) > 200:
            problems.append(key.lower() + "_required")
    return problems


def template_mapping(purpose, revision):
    maps = getattr(settings, "PLATFORM_WHATSAPP_TEMPLATES", {})
    value = maps.get(purpose) if isinstance(maps, dict) else None
    if (not isinstance(value, dict) or set(value) != {"name", "language", "revision", "approved"}
            or value.get("approved") is not True or value.get("revision") != revision
            or value.get("language") not in {"en", "en_US", "en_GB"}
            or not isinstance(value.get("name"), str)
            or not re.fullmatch(r"[a-z0-9_]{1,128}", value["name"])):
        raise ValidationError("approved_template_mapping_required")
    return dict(value)


def transport_fingerprint():
    import json
    # Token rotation requires a VERSION bump; no token is saved in attempt evidence.
    values = {"sender": configuration_fingerprint(),
              "api_version": getattr(settings, "PLATFORM_WHATSAPP_API_VERSION", ""),
              "origin": getattr(settings, "PLATFORM_WHATSAPP_BASE_URL", ""),
              "templates": getattr(settings, "PLATFORM_WHATSAPP_TEMPLATES", {}),
              "pilot": getattr(settings, "PLATFORM_WHATSAPP_PILOT", {}),
              "retention": getattr(settings, "PLATFORM_WHATSAPP_RETENTION_REFERENCE", ""),
              "support": getattr(settings, "PLATFORM_WHATSAPP_SUPPORT_MONITOR", "")}
    return hashlib.sha256(json.dumps(values, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
