"""Typed legacy Django mail settings, shared by web and operator processes."""

from django.core.exceptions import ImproperlyConfigured


def email_settings(env):
    values = {
        "EMAIL_BACKEND": env(
            "EMAIL_BACKEND", default="django.core.mail.backends.locmem.EmailBackend"
        ),
        "EMAIL_HOST": env("EMAIL_HOST", default="localhost"),
        "EMAIL_PORT": env.int("EMAIL_PORT", default=587),
        "EMAIL_USE_TLS": env.bool("EMAIL_USE_TLS", default=True),
        "EMAIL_USE_SSL": env.bool("EMAIL_USE_SSL", default=False),
        "EMAIL_TIMEOUT": env.int("EMAIL_TIMEOUT", default=15),
        "EMAIL_HOST_USER": env("EMAIL_HOST_USER", default=""),
        "EMAIL_HOST_PASSWORD": env("EMAIL_HOST_PASSWORD", default=""),
        "DEFAULT_FROM_EMAIL": env(
            "DEFAULT_FROM_EMAIL", default="Rokkad <notifications@notify.rokkad.com>"
        ),
        "BILLING_EMAIL_SENDER": env(
            "BILLING_EMAIL_SENDER", default="Rokkad Billing <billing@notify.rokkad.com>"
        ),
        "PLATFORM_EMAIL_REPLY_TO": env("PLATFORM_EMAIL_REPLY_TO", default=""),
        "BILLING_EMAIL_REPLY_TO": env("BILLING_EMAIL_REPLY_TO", default=""),
    }
    values["SERVER_EMAIL"] = env("SERVER_EMAIL", default=values["DEFAULT_FROM_EMAIL"])
    if values["EMAIL_USE_TLS"] and values["EMAIL_USE_SSL"]:
        raise ImproperlyConfigured("EMAIL_USE_TLS and EMAIL_USE_SSL are mutually exclusive.")
    if not 1 <= values["EMAIL_PORT"] <= 65535:
        raise ImproperlyConfigured("EMAIL_PORT must be between 1 and 65535.")
    if not 1 <= values["EMAIL_TIMEOUT"] <= 120:
        raise ImproperlyConfigured("EMAIL_TIMEOUT must be between 1 and 120 seconds.")
    return values
