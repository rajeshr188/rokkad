"""Deployment configuration must fail closed independently of developer .env."""
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch, MagicMock

from django.core.management import CommandError
from django.test import SimpleTestCase


class ProductionSettingsTests(SimpleTestCase):
    def load_settings(self, **changes):
        env = {key: value for key, value in os.environ.items() if not key.startswith(("DB_", "DJANGO_", "CLOUDFLARE_"))}
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
            "import django_project.settings.prod as s; "
            "print(s.DATABASES['default']['USER']); print(s.ALLOWED_HOSTS)"
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
