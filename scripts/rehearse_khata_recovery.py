"""Local fictional full-database/media and native Khata recovery rehearsal.

Creates new databases only. Never accepts a source database or customer workspace.
Leaves evidence and disposable databases available for inspection; no DROP command.
"""
import argparse
from datetime import datetime, timezone as utc
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest
from unittest.mock import patch
import uuid
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, help="Alphanumeric suffix for new fictional databases")
    args = parser.parse_args()
    if not args.run_id.isascii() or not args.run_id.isalnum() or len(args.run_id) > 20:
        parser.error("Use an alphanumeric run ID of at most 20 characters.")
    names = ["test_rokkad_khata_drill_" + args.run_id + ending for ending in ("_source", "_full", "_native")]
    evidence = ROOT / ".tmp" / ("khata-recovery-" + args.run_id)
    evidence.mkdir(parents=True, exist_ok=False)
    os.environ["DJANGO_SETTINGS_MODULE"] = "django_project.settings.migration"
    os.environ["DB_MIGRATION_NAME"] = names[0]
    os.environ["BILLING_PROVIDER_MODE"] = "test"
    # No external delivery/provider configuration is used by the fixture services.
    import django
    django.setup()
    import psycopg2
    from psycopg2 import sql
    from django.conf import settings
    from django.core.management import call_command
    from django.db import connection, transaction
    from django.test import override_settings
    from django.contrib.auth import get_user_model
    from apps.orgs.models import Company
    from apps.tenancy.context import workspace_context
    from apps.tenant_apps.loans.models import KhataAccount, KhataDocumentIssue
    from apps.tenant_apps.loans.services import khata_recovery as recovery, khata_documents as documents
    from apps.tenant_apps.loans.services.khata_labels import issue_labels
    from apps.tenant_apps.loans.services.khata_readiness import assess_readiness
    from apps.tenant_apps.loans.services import khata_accounts as drafts
    from apps.tenant_apps.loans.tests.test_khata_corrections import CorrectionFixture
    from apps.tenant_apps.loans.tests.test_khata_foundation import draft_args

    config = connection.settings_dict.copy()
    if config["HOST"] not in ("localhost", "127.0.0.1", "::1"):
        raise ValueError("This rehearsal only permits a local PostgreSQL server.")
    parameters = dict(host=config["HOST"], port=config["PORT"], user=config["USER"], password=config["PASSWORD"])
    admin = psycopg2.connect(dbname="postgres", **parameters)
    try:
        admin.autocommit = True
        with admin.cursor() as cursor:
            cursor.execute("SELECT rolsuper FROM pg_roles WHERE rolname=current_user")
            if not cursor.fetchone()[0]:
                raise ValueError("Full fictional table fingerprinting requires a local superuser connection.")
            cursor.execute("SELECT datname FROM pg_database WHERE datname=ANY(%s)", [names])
            if cursor.fetchall():
                raise ValueError("One of the disposable names exists; choose a new run ID. Never overwrite.")
            for name in names:
                cursor.execute(sql.SQL("CREATE DATABASE {} TEMPLATE template0").format(sql.Identifier(name)))
    finally:
        admin.close()

    def switch(name):
        if name not in names:
            raise ValueError("Only this run's new fictional databases may be selected.")
        connection.close()
        connection.settings_dict["NAME"] = name
        settings.DATABASES["default"]["NAME"] = name
        os.environ["DB_MIGRATION_NAME"] = name

    def fingerprints():
        result = {}
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(sql.SQL("SELECT to_jsonb(t)::text FROM public.{} t ORDER BY to_jsonb(t)::text").format(sql.Identifier(table)))
                rows = cursor.fetchall()
                digest = hashlib.sha256()
                for row in rows:
                    data = row[0].encode()
                    digest.update(len(data).to_bytes(8, "big")); digest.update(data)
                result[table] = dict(rows=len(rows), sha256=digest.hexdigest())
        return result

    def inventory(root):
        return {p.relative_to(root).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p))
                for p in sorted(root.rglob("*")) if p.is_file()}

    def sequences():
        with connection.cursor() as cursor:
            cursor.execute("SELECT sequencename, start_value, min_value, max_value, increment_by, cycle, last_value "
                           "FROM pg_sequences WHERE schemaname='public' ORDER BY sequencename")
            return cursor.fetchall()

    def native_sequences_preserved(before):
        # Native recovery intentionally advances Khata PK sequences monotonically.
        # An unused sequence may become called at 1; ordinary sequences stay exact.
        with connection.cursor() as cursor:
            khata_sequences = set()
            for model in recovery._models():
                cursor.execute("SELECT pg_get_serial_sequence(%s, %s)", [model._meta.db_table, model._meta.pk.column])
                khata_sequences.add(cursor.fetchone()[0].split(".")[-1])
        after = {row[0]: row for row in sequences()}
        if set(after) != {row[0] for row in before}:
            return False
        for row in before:
            new = after[row[0]]
            if row[0] not in khata_sequences:
                if new != row:
                    return False
            elif new[1:-1] != row[1:-1] or (row[-1] is not None and (new[-1] is None or new[-1] < row[-1])):
                return False
        return True

    pg_env = {**os.environ, "PGHOST": str(config["HOST"]), "PGPORT": str(config["PORT"]),
              "PGUSER": config["USER"], "PGPASSWORD": config["PASSWORD"]}
    def pg(program, arguments):
        executable = shutil.which(program)
        if not executable:
            raise ValueError(f"Install PostgreSQL's {program} utility before the rehearsal.")
        with (evidence / (program + ".log")).open("ab") as log:
            subprocess.run([executable, *arguments], env=pg_env, check=True, stdout=log, stderr=log)

    stores = {"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}
    source_media = evidence / "source-media"
    with override_settings(STORAGES=stores, MEDIA_ROOT=source_media,
                          EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
                          BILLING_PROVIDER_MODE="test"):
        with (evidence / "migration.log").open("w", encoding="utf-8") as log:
            call_command("migrate", interactive=False, stdout=log, stderr=log)
        class Fixture(CorrectionFixture, unittest.TestCase):
            pass
        fixture = Fixture()
        try:
            fixture.setUp()
            Company.objects.filter(pk=fixture.workspace.pk).update(name="Khata test pilot " + args.run_id)
            workspace_id, actor_id = fixture.workspace.pk, fixture.actor.pk
            active = fixture.account
            fixture.photo(fixture.first)
            incoming = fixture.replacement("100")
            fixture.exchange([fixture.first], [incoming])  # Old item remains physically held, reserved OUT.
            issue_labels(**fixture.args(), request_key=uuid.uuid4(), origin="https://rokkad.com", mode="ALL")
            documents.issue_document(**fixture.args(), request_key=uuid.uuid4())
            # A distinct annual agreement in the same new test workspace.
            fixture.account = drafts.create_draft(**draft_args(fixture.workspace, fixture.actor, fixture.borrower, fixture.series))
            fixture.open("ANNUAL")
            annual = fixture.account
            # A settled account with corrected receipt and completed physical return.
            fixture.account = drafts.create_draft(**draft_args(fixture.workspace, fixture.actor, fixture.borrower, fixture.series))
            fixture.open()
            with workspace_context(workspace_id):
                closing_item = fixture.account.collateral.first()
            with fixture.later(1):
                fixture.quote()
                receipt = fixture.pay("100000")
                fixture.correct(receipt)
                fixture.pay("100000")
                settlement = fixture.settle()
                fixture.handover(closing_item, settlement)
                documents.issue_document(**fixture.args(), request_key=uuid.uuid4(), source_operation_id=settlement.pk)
        finally:
            fixture.doCleanups()

        # All capture/reconciliation uses the same fictional November date.
        with patch("django.utils.timezone.now", return_value=datetime(2026, 11, 10, 12, tzinfo=utc.utc)):
            workspace = Company.objects.get(pk=workspace_id)
            actor = get_user_model().objects.get(pk=actor_id)
            archive = recovery.export_archive(workspace=workspace, actor=actor)
            native_path = evidence / "native.zip"
            native_path.write_bytes(archive)
            archive_sha = sha(native_path)
            original_manifest = recovery._read(archive, archive_sha)[0]
            original = fingerprints()
            original_sequences = sequences()
            media = inventory(source_media)
            media_backup = evidence / "private-media.zip"
            with ZipFile(media_backup, "x", ZIP_DEFLATED) as saved_media:
                for key in media:
                    saved_media.write(source_media / key, key)
            if inventory(source_media) != media:
                raise ValueError("Source media changed during capture.")
            connection.close()  # No writers; only this process has the new fictional database.
            dump = evidence / "database.dump"
            pg("pg_dump", ["--format=custom", "--file", str(dump), "--dbname", names[0]])
            if original != fingerprints():
                raise ValueError("Source changed while capturing the database backup.")

            for target in names[1:]:
                switch(target)
                pg("pg_restore", ["--exit-on-error", "--dbname", target, str(dump)])
                if fingerprints() != original or sequences() != original_sequences:
                    raise ValueError("Full restored public-table fingerprints or sequence states differ.")

            full_media = evidence / "full-media"
            with ZipFile(media_backup) as saved_media:
                if set(saved_media.namelist()) != set(media):
                    raise ValueError("Private-media archive inventory differs.")
                for key in media:
                    path = (full_media / key).resolve()
                    if not path.is_relative_to(full_media.resolve()):
                        raise ValueError("Private-media archive contains an unsafe path.")
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(saved_media.read(key))
            if inventory(full_media) != media:
                raise ValueError("Reconstructed private media differs from the full backup.")
            switch(names[1])
            with override_settings(MEDIA_ROOT=full_media):
                recovered = recovery.export_archive(workspace=workspace, actor=actor)
                if recovery._read(recovered, hashlib.sha256(recovered).hexdigest())[0] != original_manifest:
                    raise ValueError("Full database/media recovery did not preserve native evidence.")

            switch(names[2])
            # Simulate the documented empty Khata destination on this disposable copy ONLY.
            with transaction.atomic(), connection.cursor() as cursor:
                for model in recovery._models():
                    cursor.execute(sql.SQL("ALTER TABLE {} DISABLE TRIGGER USER").format(sql.Identifier(model._meta.db_table)))
                for model in reversed(recovery._models()):
                    cursor.execute(sql.SQL("DELETE FROM {}").format(sql.Identifier(model._meta.db_table)))
                connection.check_constraints()
                for model in recovery._models():
                    cursor.execute(sql.SQL("ALTER TABLE {} ENABLE TRIGGER USER").format(sql.Identifier(model._meta.db_table)))
            native_media = evidence / "native-media"
            with override_settings(MEDIA_ROOT=native_media):
                preview = recovery.restore_archive(workspace=workspace, actor=actor, content=archive, expected_sha256=archive_sha)
                with workspace_context(workspace_id):
                    if preview["committed"] or KhataAccount.objects.exists() or inventory(native_media):
                        raise ValueError("Native preview left rows or media behind.")
                committed = recovery.restore_archive(workspace=workspace, actor=actor, content=archive, expected_sha256=archive_sha, commit=True)
                if (not committed["committed"] or fingerprints() != original
                        or not native_sequences_preserved(original_sequences) or inventory(native_media) != media):
                    raise ValueError("Native committed recovery did not preserve original rows/media.")
                role = "khata_drill_" + args.run_id
                with connection.cursor() as cursor:
                    cursor.execute(sql.SQL("CREATE ROLE {} NOLOGIN NOSUPERUSER NOBYPASSRLS").format(sql.Identifier(role)))
                    cursor.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(role)))
                    cursor.execute(sql.SQL("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {}").format(sql.Identifier(role)))
                    cursor.execute(sql.SQL("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(sql.Identifier(role)))
                    cursor.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(role)))
                try:
                    if KhataAccount.objects.count() != 0:
                        raise ValueError("Restricted connection leaks Khata rows without Workspace context.")
                    report = assess_readiness(workspace=workspace, actor=actor)
                    if not report["software_ready"]:
                        raise ValueError("Restored restricted-runtime readiness failed: " + json.dumps(report))
                    with workspace_context(workspace_id):
                        for issue in KhataDocumentIssue.objects.all():
                            documents.document_bytes(workspace=workspace, actor=actor, account_id=issue.account_id, issue_id=issue.pk)
                    fixture.account = active
                    fixture.quote()
                    operation = fixture.payout("1000")
                    with workspace_context(workspace_id):
                        if KhataAccount.objects.get(pk=annual.pk).operations.filter(kind="WITHDRAW").count() != 1:
                            raise ValueError("Post-restore servicing changed another account.")
                finally:
                    with connection.cursor() as cursor:
                        cursor.execute("RESET ROLE")

    result = dict(format="khata-fictional-recovery-drill/1", databases=names, workspace_slug=workspace.slug,
        workspace_id=workspace_id, actor_id=actor_id, fictional_as_of="2026-11-10",
        public_tables=len(original), public_rows=sum(r["rows"] for r in original.values()),
        media_files=len(media), media_bytes=sum(r["bytes"] for r in media.values()),
        sequences=len(original_sequences), dump_sha256=sha(dump), media_archive_sha256=sha(media_backup),
        native_sha256=archive_sha, full_database_media_restore=True,
        native_preview_rollback=True, native_commit_exact=True, restricted_runtime_ready=report["software_ready"],
        full_sequences_exact=True, native_sequences_monotonic=True, ordinary_sequences_unchanged=True,
        no_context_rows=0, post_restore_withdrawal_id=operation.pk, production_touched=False,
        image_verified=False, physical_printer_verified=False, readiness=report)
    (evidence / "tables.json").write_text(json.dumps(original, indent=2) + "\n", encoding="utf-8")
    (evidence / "media.json").write_text(json.dumps(media, indent=2) + "\n", encoding="utf-8")
    (evidence / "report.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "readiness"}, indent=2))
    connection.close()


if __name__ == "__main__":
    run()
