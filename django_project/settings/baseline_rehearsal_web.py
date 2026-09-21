"""Loopback browser access to an explicitly selected isolated rehearsal database."""
from copy import deepcopy

from .baseline_rehearsal import *  # noqa: F403

ALLOWED_HOSTS = ["127.0.0.1", "localhost", "[::1]"]
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SESSION_COOKIE_NAME = "rokkad_rehearsal_session"
CSRF_COOKIE_NAME = "rokkad_rehearsal_csrf"
SESSION_COOKIE_DOMAIN = None
CSRF_COOKIE_DOMAIN = None
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    "LOCATION": REHEARSAL_DATABASE_NAME,  # noqa: F405
}}
MEDIA_ROOT = BASE_DIR / "outputs" / REHEARSAL_DATABASE_NAME / "media"  # noqa: F405
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
REHEARSAL_BROWSER = True
MIDDLEWARE = [m for m in MIDDLEWARE if m != "debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
TEMPLATES = deepcopy(TEMPLATES)  # noqa: F405
TEMPLATES[0]["OPTIONS"]["context_processors"].append(
    "django_project.context_processors.rehearsal_environment"
)
