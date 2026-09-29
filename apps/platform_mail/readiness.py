"""Offline checks for the dedicated SES path, independent of Django SMTP."""
import re
from email.utils import parseaddr
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from apps.configuration.email_readiness import _address_valid


def assess_platform_mail():
    blockers = []
    if settings.ACCOUNT_EMAIL_ENABLED:
        from .account_mail import check_link_configuration
        try:
            check_link_configuration()
        except ValidationError as exc:
            blockers.extend(exc.messages)
    region, account = settings.PLATFORM_SES_REGION, settings.PLATFORM_SES_ACCOUNT_ID
    domain = settings.PLATFORM_EMAIL_SENDER_DOMAIN
    origin = urlsplit(settings.PLATFORM_EMAIL_BASE_URL)
    if (origin.scheme != "https" or not origin.hostname or origin.username or origin.password or
            origin.path not in ("", "/") or origin.query or origin.fragment):
        blockers.append("PLATFORM_EMAIL_BASE_URL must be a canonical HTTPS origin.")
    if not re.fullmatch(r"[a-z]{2}-[a-z]+-\d", region) or not re.fullmatch(r"\d{12}", account):
        blockers.append("Configure the SES region and 12-digit AWS account ID.")
    for name in ("DEFAULT_FROM_EMAIL", "BILLING_EMAIL_SENDER", "PLATFORM_EMAIL_REPLY_TO", "BILLING_EMAIL_REPLY_TO"):
        value = getattr(settings, name, "")
        if not _address_valid(value):
            blockers.append(f"{name} requires one real email address.")
        elif name.endswith("SENDER") or name == "DEFAULT_FROM_EMAIL":
            if parseaddr(value)[1].rsplit("@", 1)[-1].lower() != domain:
                blockers.append(f"{name} must use the configured verified SES domain.")
    if not settings.PLATFORM_SES_ACCESS_KEY_ID or not settings.PLATFORM_SES_SECRET_ACCESS_KEY:
        blockers.append("Dedicated SES runtime credentials are missing.")
    if not settings.PLATFORM_SES_CONFIGURATION_SET:
        blockers.append("A configured SES event configuration set is required.")
    topic_prefix = f"arn:aws:sns:{region}:{account}:"
    if not settings.PLATFORM_SES_TOPIC_ARN.startswith(topic_prefix) or not settings.PLATFORM_SES_TOPIC_ARN[len(topic_prefix):]:
        blockers.append("Configure the exact regional SNS topic ARN.")
    queue = urlsplit(settings.PLATFORM_SES_EVENTS_QUEUE_URL)
    if (queue.scheme != "https" or queue.netloc != f"sqs.{region}.amazonaws.com" or
            not re.fullmatch(rf"/{re.escape(account)}/[A-Za-z0-9_-]+", queue.path) or queue.query or queue.fragment):
        blockers.append("Configure the exact private regional SQS queue URL.")
    return {"sending_enabled": settings.PLATFORM_EMAIL_ENABLED,
            "account_email_enabled": settings.ACCOUNT_EMAIL_ENABLED,
            "configuration_ready": not blockers, "delivery_verified": False, "blockers": blockers,
            "unverified": ["IAM/topic/queue policies and redrive", "SES domain, production access and quota",
                           "Active worker and feedback consumer", "Controlled delivery, bounce and reply tests"]}
