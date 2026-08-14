from io import StringIO
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db import connection
from django.db.models import Max
from django.test import TestCase

from apps.configuration.models import WorkspacePreferenceModel
from apps.configuration.services import PreferenceService
from apps.orgs.models import Company
from apps.orgs.registries import company_preference_registry


class MigratePreferencesToWorkspaceCommandTests(TestCase):
    def setUp(self):
        if hasattr(connection, "set_schema_to_public"):
            connection.set_schema_to_public()
        User = get_user_model()
        self.user = User.objects.create_user(
            username="pref-command-owner",
            email="pref-command-owner@example.com",
            password="pass",
        )
        next_company_id = (
            Company.all_objects.aggregate(max_id=Max("id"))["max_id"] or 0
        ) + 1
        self.workspace = Company(
            id=next_company_id,
            name="Preference Command Workspace",
            schema_name=f"pref_command_workspace_{next_company_id}",
            owner=self.user,
            creator=self.user,
        )
        self.workspace.auto_create_schema = False
        self.workspace.save()

    def tearDown(self):
        if hasattr(connection, "set_schema_to_public"):
            connection.set_schema_to_public()

    def test_dry_run_inventories_legacy_girvi_rows_without_writes(self):
        company_preference_registry.manager(instance=self.workspace)[
            "Loan__Default_Date"
        ] = "L"
        out = StringIO()

        call_command("migrate_preferences_to_workspace", "--dry-run", stdout=out)

        self.assertIn("Loan__Default_Date", out.getvalue())
        self.assertIn("loan__default_date", out.getvalue())
        self.assertIn("matched=1", out.getvalue())
        self.assertIn("written=0", out.getvalue())
        self.assertFalse(
            WorkspacePreferenceModel.objects.filter(
                instance=self.workspace,
                section="loan",
                name="default_date",
            ).exists()
        )

    def test_apply_writes_mapped_legacy_girvi_rows_to_central_preferences(self):
        manager = company_preference_registry.manager(instance=self.workspace)
        manager["Loan__Default_Date"] = "L"
        manager["Interest_Rate__gold"] = Decimal("3.50")
        out = StringIO()

        call_command("migrate_preferences_to_workspace", "--apply", stdout=out)

        self.assertEqual(
            PreferenceService.get_workspace(self.workspace, "loan__default_date"),
            "L",
        )
        self.assertEqual(
            PreferenceService.get_workspace(
                self.workspace,
                "loan__default_gold_interest_rate",
            ),
            Decimal("3.50"),
        )
        self.assertIn("written=2", out.getvalue())

    def test_apply_and_dry_run_together_are_refused(self):
        with self.assertRaises(CommandError):
            call_command("migrate_preferences_to_workspace", "--dry-run", "--apply")
