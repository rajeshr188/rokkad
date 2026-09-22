"""Local-only template sandbox: dedicated DB/login, cookies and filesystem media."""
import json
import os
from pathlib import Path

_root = Path(__file__).resolve().parents[2]
_config = json.loads((_root / "outputs/ticket-template-sandbox/runtime.json").read_text())
_database = "rokkad_ticket_template_sandbox"
_role = "rokkad_ticket_sandbox_runtime"
if _config["database"] != _database or _config["user"] != _role:
    raise RuntimeError("This settings module only serves the isolated ticket sandbox.")
if _config["host"] not in {"localhost", "127.0.0.1", "::1"}:
    raise RuntimeError("The ticket sandbox requires loopback PostgreSQL.")
os.environ.update({
    "DEBUG": "True", "SECRET_KEY": _config["secret_key"],
    "DJANGO_ALLOWED_HOSTS": "localhost,127.0.0.1,[::1]",
    "DB_NAME": _database, "DB_USER": _role, "DB_PASSWORD": _config["password"],
    "DB_HOST": _config["host"], "DB_PORT": str(_config["port"]),
    "EMAIL_HOST": "localhost", "EMAIL_PORT": "25", "EMAIL_USE_TLS": "False",
    "EMAIL_HOST_USER": "", "EMAIL_HOST_PASSWORD": "",
    "DEFAULT_FROM_EMAIL": "sandbox@example.invalid", "ADMINS": "Sandbox <sandbox@example.invalid>",
    "GOOGLE_CLIENT_ID": "", "RAZORPAY_KEY_ID": "", "RAZORPAY_KEY_SECRET": "",
    "RAZORPAY_WEBHOOK_SECRET": "", "CACHE_URL": "locmemcache://ticket-template-sandbox",
})

from .base import *  # noqa: E402,F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
SECURE_SSL_REDIRECT = SESSION_COOKIE_SECURE = CSRF_COOKIE_SECURE = False
SESSION_COOKIE_NAME = "rokkad_ticket_sandbox_session"
CSRF_COOKIE_NAME = "rokkad_ticket_sandbox_csrf"
SESSION_COOKIE_DOMAIN = CSRF_COOKIE_DOMAIN = None
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
MEDIA_ROOT = _root / "outputs/ticket-template-sandbox/media"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
MIDDLEWARE = [m for m in MIDDLEWARE if m != "debug_toolbar.middleware.DebugToolbarMiddleware"]  # noqa: F405
SILENCED_SYSTEM_CHECKS = ["debug_toolbar.W001"]
TICKET_TEMPLATE_SANDBOX = True
TEMPLATES[0]["OPTIONS"]["context_processors"].append(  # noqa: F405
    "django_project.context_processors.rehearsal_environment"
)
