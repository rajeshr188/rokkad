"""Compose-only localhost settings; runtime credentials are still mandatory."""
from .prod import *  # noqa: F403

DEBUG = True
BILLING_ALLOW_TRIAL_START = True
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
STORAGES["staticfiles"] = {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}  # noqa: F405
