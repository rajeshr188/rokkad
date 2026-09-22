"""Deployment configuration must fail closed independently of developer .env."""
import os
import json
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch, MagicMock

from django.core.management import CommandError
from django.test import SimpleTestCase


class ProductionSettingsTests(SimpleTestCase):
    def load_settings(self, *, module="prod", probe=None, **changes):
        env = {key: value for key, value in os.environ.items() if not key.startswith(("DB_", "DJANGO_", "CLOUDFLARE_", "ROKKAD_", "AWS_"))}
        env.update(DEBUG="False", SECRET_KEY="test-only", DJANGO_ALLOWED_HOSTS="localhost",
                   DB_NAME="unused", DB_USER="owner", DB_PASSWORD="owner-test",
                   DB_RUNTIME_USER="runtime", DB_RUNTIME_PASSWORD="runtime-test",
                   DB_HOST="localhost", DB_PORT="5432", EMAIL_HOST="localhost",
                   EMAIL_PORT="1025", EMAIL_USE_TLS="False", EMAIL_HOST_USER="unused",
                   EMAIL_HOST_PASSWORD="unused", DEFAULT_FROM_EMAIL="test@example.invalid",
                   ADMINS="Test <test@example.invalid>", CLOUDFLARE_R2_BUCKET="unused",
                   CLOUDFLARE_R2_ACCESS_KEY="unused", CLOUDFLARE_R2_SECRET_KEY="unused",
                   CLOUDFLARE_R2_BUCKET_ENDPOINT="http://localhost:9000")
        for key, value in changes.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        return subprocess.run([sys.executable, "-c", (
            "import environ; environ.Env.read_env=lambda *a, **k: None; "
            f"import django_project.settings.{module} as s; "
            + (probe or "print(s.DATABASES['default']['USER']); print(s.ALLOWED_HOSTS)")
        )], cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True)

    def test_explicit_runtime_credentials_win_over_owner_defaults(self):
        result = self.load_settings()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), ["runtime", "['localhost']"])

    def test_missing_runtime_credentials_never_fall_back_to_owner(self):
        for field in ("DB_RUNTIME_USER", "DB_RUNTIME_PASSWORD"):
            result = self.load_settings(**{field: None})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(field, result.stderr)

    def test_wildcard_or_empty_hosts_are_rejected(self):
        for value in ("*", "localhost,*", ""):
            result = self.load_settings(DJANGO_ALLOWED_HOSTS=value)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("explicit DJANGO_ALLOWED_HOSTS", result.stderr)

    def test_empty_runtime_credentials_are_rejected(self):
        for field in ("DB_RUNTIME_USER", "DB_RUNTIME_PASSWORD"):
            result = self.load_settings(**{field: ""})
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be nonempty", result.stderr)


class ProductionMediaSettingsTests(SimpleTestCase):
    def load_media(self, **changes):
        values = dict(CLOUDFLARE_R2_BUCKET_ENDPOINT="https://" + "a" * 32 + ".r2.cloudflarestorage.com",
                      ROKKAD_PRODUCTION_MEDIA_LOCATION="media/application/production/linode-rls")
        values.update(changes)
        return ProductionSettingsTests().load_settings(module="prod_r2", probe=(
            "import json; from django.conf import settings; settings.configure(**{k:getattr(s,k) for k in dir(s) if k.isupper()}); "
            "from helpers.cloudflare.storages import MediaFileStorage; "
            "b=MediaFileStorage(**s.STORAGES['default']['OPTIONS']); "
            "print(json.dumps(dict(location=b.location, acl=b.default_acl, signed=b.querystring_auth, "
            "domain=b.custom_domain, overwrite=b.file_overwrite, expiry=b.querystring_expire, "
            "cache=b.object_parameters['CacheControl'], static=s.STORAGES['staticfiles']['BACKEND'], "
            "secure=[s.SECURE_SSL_REDIRECT,s.SESSION_COOKIE_SECURE,s.CSRF_COOKIE_SECURE], "
            "proxy=getattr(s,'SECURE_PROXY_SSL_HEADER',None))))"
        ), **values)

    def test_private_backend_preserves_static_storage_and_requires_https(self):
        result = self.load_media(SECURE_SSL_REDIRECT="False", SESSION_COOKIE_SECURE="False", CSRF_COOKIE_SECURE="False")
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads(result.stdout)
        self.assertEqual(config, dict(location="media/application/production/linode-rls", acl=None,
            signed=True, domain=None, overwrite=False, expiry=60, cache="private, no-store",
            static="whitenoise.storage.CompressedManifestStaticFilesStorage", secure=[True,True,True], proxy=None))

    def test_rehearsal_preservation_or_ambiguous_prefix_is_rejected(self):
        for location in (None, "", "media/legacy/source", "media/application/rehearsal",
                         "media/application/production/../legacy", "media/application/production/app/"):
            with self.subTest(location=location):
                result = self.load_media(ROKKAD_PRODUCTION_MEDIA_LOCATION=location)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ROKKAD_PRODUCTION_MEDIA_LOCATION", result.stderr)

    def test_endpoint_and_credentials_fail_closed(self):
        for key, value in (("CLOUDFLARE_R2_BUCKET_ENDPOINT", "http://localhost:9000"),
                           ("CLOUDFLARE_R2_BUCKET_ENDPOINT", "https://example.com"),
                           ("CLOUDFLARE_R2_BUCKET", ""), ("CLOUDFLARE_R2_ACCESS_KEY", " "),
                           ("CLOUDFLARE_R2_SECRET_KEY", "")):
            with self.subTest(key=key, value=value):
                self.assertNotEqual(self.load_media(**{key:value}).returncode, 0)

    def test_proxy_trust_is_explicit(self):
        result = self.load_media(ROKKAD_TRUST_HTTPS_PROXY="True")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["proxy"], ["HTTP_X_FORWARDED_PROTO", "https"])


class StartupGateTests(SimpleTestCase):
    def test_pending_migrations_block_startup_after_runtime_checks(self):
        from scripts.start_web import check_runtime
        executor = MagicMock()
        executor.migration_plan.return_value = [object()]
        with patch("django.setup"), patch("django.core.management.call_command") as checks, patch(
            "django.db.migrations.executor.MigrationExecutor", return_value=executor
        ):
            with self.assertRaisesMessage(CommandError, "Pending migrations"):
                check_runtime()
        checks.assert_called_once_with("check", deploy=True, databases=["default"], fail_level="ERROR")

    def test_failed_runtime_check_stops_before_schema_inspection(self):
        from scripts.start_web import check_runtime
        with patch("django.setup"), patch("django.core.management.call_command", side_effect=CommandError("tenancy.E020")), patch(
            "django.db.migrations.executor.MigrationExecutor"
        ) as executor:
            with self.assertRaisesMessage(CommandError, "tenancy.E020"):
                check_runtime()
            executor.assert_not_called()
