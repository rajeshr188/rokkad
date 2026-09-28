"""Non-secret, offline inspection. Configuration is never delivery evidence."""

from email.utils import parseaddr

from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


SMTP_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
CAPTURE_BACKENDS = frozenset(
    f"django.core.mail.backends.{name}.EmailBackend"
    for name in ("console", "dummy", "locmem", "filebased")
)


def _address_valid(value):
    if not isinstance(value, str) or "\r" in value or "\n" in value:
        return False
    try:
        address = parseaddr(value)[1]
        validate_email(address)
        return address.rsplit("@", 1)[-1] not in {"localhost", "example.com"}
    except (ValidationError, ValueError):
        return False


def assess_email_configuration():
    blockers = []
    if hasattr(settings, "MAILERS"):
        source = "MAILERS.default"
        config = settings.MAILERS.get("default", {})
        backend = config.get("BACKEND", SMTP_BACKEND)
        options = config.get("OPTIONS", {})
        port = options.get("port", 465 if options.get("use_ssl") else 587 if options.get("use_tls") else 25)
        tls, ssl = options.get("use_tls", False), options.get("use_ssl", False)
        timeout, host = options.get("timeout"), options.get("host", "")
        if "default" not in settings.MAILERS:
            blockers.append("MAILERS has no default mailer.")
    else:
        source = "EMAIL_BACKEND"
        backend = settings.EMAIL_BACKEND
        port = settings.EMAIL_PORT
        tls, ssl = settings.EMAIL_USE_TLS, settings.EMAIL_USE_SSL
        timeout, host = settings.EMAIL_TIMEOUT, settings.EMAIL_HOST

    capture = backend in CAPTURE_BACKENDS
    if capture:
        blockers.append("Mail is captured or discarded locally; no external delivery occurs.")
    elif backend != SMTP_BACKEND:
        blockers.append("This backend requires its own reviewed provider readiness checks.")
    if backend == SMTP_BACKEND:
        if type(port) is not int or not 1 <= port <= 65535:
            blockers.append("SMTP port must be an integer between 1 and 65535.")
        if type(tls) is not bool or type(ssl) is not bool or (tls and ssl):
            blockers.append("SMTP TLS/SSL must be booleans and cannot both be enabled.")
        elif not tls and not ssl:
            blockers.append("External SMTP requires TLS or SSL.")
        if type(timeout) not in (int, float) or not 0 < timeout <= 120:
            blockers.append("SMTP requires a finite timeout of at most 120 seconds.")
        if not host or str(host).lower() in {"localhost", "127.0.0.1", "::1"}:
            blockers.append("SMTP points to a local or missing server.")
    for name in ("DEFAULT_FROM_EMAIL", "SERVER_EMAIL", "BILLING_EMAIL_SENDER", "PLATFORM_EMAIL_REPLY_TO", "BILLING_EMAIL_REPLY_TO"):
        if not _address_valid(getattr(settings, name, "")):
            blockers.append(f"{name} requires a real single email address.")
    return {
        "configuration_source": source,
        "backend": backend,
        "capture_only": capture,
        "configuration_valid_for_external_mail": not blockers,
        "delivery_verified": False,
        "blockers": blockers,
        "unverified": [
            "Provider account approval, sender verification and sending limits",
            "DNS SPF, DKIM and DMARC alignment",
            "Monitored reply inboxes and end-to-end receipt",
            "Durable retries and authenticated delivery/bounce/complaint processing",
        ],
    }
