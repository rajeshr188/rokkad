import os
from pathlib import Path
import subprocess
import tempfile
import uuid

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django_tenants.utils import get_public_schema_name, schema_context, schema_exists

from apps.tenant_apps.accounting.diagnostics import accounting_integrity_findings


class Command(BaseCommand):
    help = "Dump one tenant schema, restore it under a temporary name, verify it, and remove it."

    def add_arguments(self, parser):
        parser.add_argument("--schema", required=True)

    def handle(self, *args, **options):
        source = options["schema"].strip()
        if source == get_public_schema_name() or not schema_exists(source):
            raise CommandError("A valid non-public source schema is required.")
        target = f"accounting_recovery_{uuid.uuid4().hex[:12]}"
        if schema_exists(target):
            raise CommandError("Generated recovery schema already exists.")
        db = settings.DATABASES["default"]
        env = os.environ.copy()
        env["PGPASSWORD"] = db["PASSWORD"]
        descriptor, temp_name = tempfile.mkstemp(prefix="accounting_recovery_", suffix=".sql")
        os.close(descriptor)
        dump_path = Path(temp_name)
        restored_path = dump_path.with_suffix(".restored.sql")
        common = ["-h", db["HOST"], "-p", str(db["PORT"]), "-U", db["USER"], "-d", db["NAME"]]
        try:
            subprocess.run(
                ["pg_dump", *common, "--schema", source, "--no-owner", "--no-privileges", "--file", str(dump_path)],
                check=True, env=env, capture_output=True, text=True,
            )
            restored_path.write_text(dump_path.read_text(encoding="utf-8").replace(source, target), encoding="utf-8")
            subprocess.run(
                ["psql", *common, "--set", "ON_ERROR_STOP=1", "--file", str(restored_path)],
                check=True, env=env, capture_output=True, text=True,
            )
            with schema_context(source):
                source_counts = self._accounting_counts()
            with schema_context(target):
                target_counts = self._accounting_counts()
                findings = accounting_integrity_findings()
            if source_counts != target_counts or findings:
                raise CommandError("Restored accounting schema failed count or integrity verification.")
            self.stdout.write(self.style.SUCCESS(
                f"Recovery rehearsal passed: {source} -> {target}; {len(source_counts)} accounting tables verified."
            ))
        except FileNotFoundError as exc:
            raise CommandError("PostgreSQL pg_dump/psql tools are required.") from exc
        except subprocess.CalledProcessError as exc:
            raise CommandError((exc.stderr or str(exc))[-2000:]) from exc
        finally:
            if schema_exists(target):
                with connection.cursor() as cursor:
                    cursor.execute(f"DROP SCHEMA {connection.ops.quote_name(target)} CASCADE")
            dump_path.unlink(missing_ok=True)
            restored_path.unlink(missing_ok=True)

    @staticmethod
    def _accounting_counts():
        with connection.cursor() as cursor:
            tables = [name for name in connection.introspection.table_names(cursor) if name.startswith("standalone_accounting_")]
            counts = {}
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {connection.ops.quote_name(table)}")
                counts[table] = cursor.fetchone()[0]
            return counts
