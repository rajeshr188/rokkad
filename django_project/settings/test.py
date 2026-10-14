"""Owner-backed test database setup; RLS tests assume restricted roles explicitly."""

from .migration import *  # noqa: F403

# Tests must never inherit payment credentials/mode from a developer's .env.
BILLING_PROVIDER_MODE = "test"
BILLING_TAX_RATE = "18"  # Fictional arithmetic fixture, never production policy.
BILLING_SELLER_NAME = ""
BILLING_SELLER_ADDRESS = ""
BILLING_SELLER_TAX_STATUS = ""
RAZORPAY_KEY_ID = "rzp_test_fixture"
RAZORPAY_KEY_SECRET = "fixture-secret"
RAZORPAY_WEBHOOK_SECRET = "fixture-webhook-secret"


CACHES = {
    **CACHES,  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "rokkad-tests",
    },
}

# Do not inherit platform WhatsApp reception or credentials from a local .env.
PLATFORM_WHATSAPP_INBOUND_ENABLED = False
PLATFORM_WHATSAPP_PHONE_ID = ""
PLATFORM_WHATSAPP_WABA_ID = ""
PLATFORM_WHATSAPP_APP_SECRET = ""
PLATFORM_WHATSAPP_VERIFY_TOKEN = ""
PLATFORM_WHATSAPP_SENDER_NUMBER = ""
PLATFORM_WHATSAPP_BASE_URL = ""

# PW-03 tests never inherit a chargeable platform sender.
PLATFORM_WHATSAPP_DISPATCH_ENABLED = False
PLATFORM_WHATSAPP_ACCESS_TOKEN = ""
PLATFORM_WHATSAPP_API_VERSION = ""
PLATFORM_WHATSAPP_TEMPLATES = {}

PLATFORM_WHATSAPP_INTENTS_ENABLED = False
PLATFORM_WHATSAPP_PILOT = {}

PLATFORM_WHATSAPP_RETENTION_REFERENCE = ""
PLATFORM_WHATSAPP_SUPPORT_MONITOR = ""
