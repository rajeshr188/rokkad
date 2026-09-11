"""Operator entry points establish their own context under restricted SQL roles."""
from io import StringIO
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command, CommandError
from django.db import connection, transaction
from django.test import TransactionTestCase

from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id, workspace_context
from apps.tenant_apps.loans.models import LoanProduct
from apps.tenant_apps.loans.services.product_catalog import LoanProductCatalogError


class OperatorCommandTests(TransactionTestCase):
    commands = ("seed_default_loan_products", "check_loan_document_integrity", "dispatch_pawn_loan_notices")

    def setUp(self):
        owner = get_user_model().objects.create_user(username="command-owner")
        self.first = Company.objects.create(name="Command first", schema_name="command-first", owner=owner, creator=owner)
        self.second = Company.objects.create(name="Command second", schema_name="command-second", owner=owner, creator=owner)
        self.role = "command_test_" + uuid.uuid4().hex
        self.quoted_role = connection.ops.quote_name(self.role)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE ROLE {self.quoted_role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            cursor.execute(f"GRANT USAGE ON SCHEMA public TO {self.quoted_role}")
            cursor.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {self.quoted_role}")
            cursor.execute(f"GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO {self.quoted_role}")

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute("RESET ROLE")
            cursor.execute(f"DROP OWNED BY {self.quoted_role}")
            cursor.execute(f"DROP ROLE {self.quoted_role}")
        super().tearDown()

    def run_command(self, name, **options):
        output = StringIO()
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET LOCAL ROLE {self.quoted_role}")
            try:
                call_command(name, stdout=output, **options)
            finally:
                self.assertIsNone(current_workspace_id())
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_setting('app.workspace_id', true)")
                    self.assertIn(cursor.fetchone()[0], (None, ""))
        return output.getvalue()

    def test_missing_invalid_unknown_and_conflicting_ids_are_rejected(self):
        for command in self.commands:
            with self.assertRaises(CommandError):
                self.run_command(command)
            for pk in (0, -1, self.second.pk + 999):
                with self.assertRaises(CommandError):
                    self.run_command(command, workspace_id=pk)
            with workspace_context(self.first.pk):
                with self.assertRaisesMessage(CommandError, "conflicts"):
                    call_command(command, workspace_id=self.second.pk, stdout=StringIO())
                self.assertEqual(current_workspace_id(), self.first.pk)

    def test_lifecycle_blocks_writes_but_allows_read_only_recovery(self):
        for state in ("SUSPENDED", "ARCHIVED", "DELETION_PENDING"):
            Company.all_objects.filter(pk=self.first.pk).update(lifecycle_state=state)
            for command in (self.commands[0], self.commands[2]):
                with self.assertRaisesMessage(CommandError, "ACTIVE"):
                    self.run_command(command, workspace_id=self.first.pk)
            self.assertIn("findings: 0", self.run_command(self.commands[1], workspace_id=self.first.pk))
        self.assertEqual(LoanProduct.objects.count(), 0)

    def test_seed_is_scoped_idempotent_and_failure_rolls_back(self):
        for _ in range(2):
            self.run_command(self.commands[0], workspace_id=self.first.pk)
        self.assertEqual(LoanProduct.objects.filter(workspace=self.first).count(), 4)
        self.assertFalse(LoanProduct.objects.filter(workspace=self.second).exists())
        from apps.tenant_apps.loans.services.product_catalog import _seed_default_loan_products
        def fail_after_seed():
            _seed_default_loan_products()
            raise LoanProductCatalogError("Test failure")
        with patch("apps.tenant_apps.loans.management.commands.seed_default_loan_products._seed_default_loan_products", side_effect=fail_after_seed):
            with self.assertRaisesMessage(CommandError, "Test failure"):
                self.run_command(self.commands[0], workspace_id=self.second.pk)
        self.assertFalse(LoanProduct.objects.filter(workspace=self.second).exists())

    def test_dispatch_validates_input_and_sets_context_without_sending(self):
        target = "apps.tenant_apps.loans.management.commands.dispatch_pawn_loan_notices.dispatch_due_pawn_loan_notices"
        def dispatch(**kwargs):
            self.assertEqual(current_workspace_id(), self.first.pk)
            self.assertIsNotNone(kwargs["as_of"].tzinfo)
            return SimpleNamespace(due_count=0, sent_count=0, failed_count=0)
        with patch(target, side_effect=dispatch) as handler:
            for options in ({"limit": 0}, {"limit": 1001}, {"as_of": "bad"}, {"as_of": "2026-99-99T10:00:00"}):
                with self.assertRaises(CommandError):
                    self.run_command(self.commands[2], workspace_id=self.first.pk, **options)
            handler.assert_not_called()
            self.run_command(self.commands[2], workspace_id=self.first.pk, as_of="2026-09-09T10:00:00")
            handler.assert_called_once()
        with patch(target, side_effect=ValueError("Dispatch failed")):
            with self.assertRaisesMessage(ValueError, "Dispatch failed"):
                self.run_command(self.commands[2], workspace_id=self.first.pk)

    def test_integrity_findings_fail_after_context_is_cleared(self):
        finding = SimpleNamespace(category="TEST", object_type="issue", object_id=1, message="Test finding")
        with patch("apps.tenant_apps.loans.management.commands.check_loan_document_integrity.get_document_integrity_findings", return_value=[finding]):
            with self.assertRaisesMessage(CommandError, "integrity check failed"):
                self.run_command(self.commands[1], workspace_id=self.first.pk, fail_on_findings=True)

    def test_fresh_process_commands_use_explicit_context_and_restricted_sql(self):
        env = os.environ.copy()
        env.update(DJANGO_SETTINGS_MODULE="django_project.settings.test",
                   DB_MIGRATION_NAME=connection.settings_dict["NAME"],
                   DB_MIGRATION_USER=connection.settings_dict["USER"],
                   DB_MIGRATION_PASSWORD=connection.settings_dict["PASSWORD"],
                   DB_HOST=connection.settings_dict["HOST"], DB_PORT=str(connection.settings_dict["PORT"]),
                   COMMAND_TEST_ROLE=self.role, COMMAND_TEST_WORKSPACE=str(self.first.pk))
        script = '''
import os, django
django.setup()
from django.core.management import call_command
from django.db import connection
from apps.tenancy.context import current_workspace_id
from unittest.mock import patch
with connection.cursor() as cursor:
    cursor.execute('SET ROLE ' + connection.ops.quote_name(os.environ['COMMAND_TEST_ROLE']))
    cursor.execute('SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user')
    assert cursor.fetchone() == (False, False)
with patch('apps.tenant_apps.loans.services.pawn_notices.deliver_pawn_notice_job', side_effect=AssertionError('No deliveries allowed')):
    for command in ('seed_default_loan_products', 'check_loan_document_integrity', 'dispatch_pawn_loan_notices'):
        assert current_workspace_id() is None
        call_command(command, workspace_id=int(os.environ['COMMAND_TEST_WORKSPACE']))
        assert current_workspace_id() is None
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('app.workspace_id', true)")
            assert cursor.fetchone()[0] in (None, '')
'''
        result = subprocess.run([sys.executable, "-c", script], env=env,
                                cwd=Path(__file__).resolve().parents[4],
                                capture_output=True, text=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("due=0, sent=0, failed=0", result.stdout)
        self.assertEqual(LoanProduct.objects.filter(workspace=self.first).count(), 4)
        self.assertFalse(LoanProduct.objects.filter(workspace=self.second).exists())
