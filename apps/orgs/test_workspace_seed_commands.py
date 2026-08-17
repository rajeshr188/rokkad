from io import StringIO
from types import SimpleNamespace
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.orgs.management.commands.seed_all_workspaces import Command as SeedAll
from apps.orgs.management.commands.seed_workspace_defaults import (
    Command as SeedDefaults,
)


class WorkspaceSeedCommandContextTests(SimpleTestCase):
    @patch("apps.orgs.management.commands.seed_workspace_defaults.transaction.atomic")
    @patch("apps.orgs.management.commands.seed_workspace_defaults.workspace_context")
    @patch("apps.orgs.management.commands.seed_workspace_defaults.Company.all_objects.get")
    def test_workspace_defaults_opens_its_explicit_context(
        self, get_workspace, context, atomic
    ):
        get_workspace.return_value = SimpleNamespace(pk=17)
        command = SeedDefaults(stdout=StringIO())

        command.handle(
            workspace_id=17,
            dry_run=False,
            skip_rates=True,
            skip_party=True,
            skip_notify_v2=True,
        )

        get_workspace.assert_called_once_with(pk=17)
        context.assert_called_once_with(17)
        atomic.assert_called_once_with()

    @patch("apps.orgs.management.commands.seed_all_workspaces.call_command")
    @patch("apps.orgs.management.commands.seed_all_workspaces.Company.objects.values_list")
    def test_all_workspaces_passes_each_explicit_id_to_scoped_command(
        self, values_list, call_command
    ):
        values_list.return_value = [17, 23]
        command = SeedAll(stdout=StringIO(), stderr=StringIO())

        command.handle(dry_run=False, continue_on_error=False, skip_rates=True)

        values_list.assert_called_once_with("pk", flat=True)
        self.assertEqual(call_command.call_count, 2)
        call_command.assert_any_call(
            "seed_workspace_defaults", workspace_id=17, skip_rates=True
        )
        call_command.assert_any_call(
            "seed_workspace_defaults", workspace_id=23, skip_rates=True
        )
