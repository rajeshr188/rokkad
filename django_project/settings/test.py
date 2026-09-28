"""Owner-backed test database setup; RLS tests assume restricted roles explicitly."""

from .migration import *  # noqa: F403

# Tests must never inherit payment credentials/mode from a developer's .env.
BILLING_PROVIDER_MODE = "test"
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
