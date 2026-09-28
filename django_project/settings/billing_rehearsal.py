"""Opt-in local Razorpay TEST checkout; never a deployment settings module."""
from .baseline_rehearsal_web import *  # noqa: F403
from scripts.billing_rehearsal_credentials import read_private_json, validate_rehearsal

_provider_credentials = read_private_json("razorpay-test.dpapi")
validate_rehearsal(REHEARSAL_DATABASE_NAME, DATABASES["default"]["HOST"], _provider_credentials)  # noqa: F405
_local_secrets = read_private_json("billing-rehearsal.dpapi")
SECRET_KEY = _local_secrets["django_secret"]
RAZORPAY_KEY_ID = _provider_credentials["key_id"]
RAZORPAY_KEY_SECRET = _provider_credentials["key_secret"]
RAZORPAY_WEBHOOK_SECRET = _local_secrets["webhook_secret"]
del _provider_credentials, _local_secrets

DEBUG = False
# Loopback review must serve current source assets, including new Checkout JS.
WHITENOISE_USE_FINDERS = True
BILLING_REHEARSAL = True
BILLING_PROVIDER_MODE = "test"
BILLING_CHECKOUT_ENABLED = True
BILLING_ALLOW_TRIAL_START = False
# Illustrative arithmetic only; production tax treatment is still under review.
BILLING_TAX_RATE = "18"
SESSION_COOKIE_NAME = "rokkad_billing_rehearsal_session"
CSRF_COOKIE_NAME = "rokkad_billing_rehearsal_csrf"
PLATFORM_EMAIL_ENABLED = False
PLATFORM_SES_ACCESS_KEY_ID = ""
PLATFORM_SES_SECRET_ACCESS_KEY = ""
# Receipt intent stays in this database; no external email or object storage.
CSRF_TRUSTED_ORIGINS = ["http://127.0.0.1:8083"]
