from unittest.mock import patch

from django.core.checks import Error
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class SeedRLSSmokeWorkspacesCommandTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_refuses_non_development_settings(self):
        with self.assertRaisesMessage(CommandError, "requires DEBUG=True"):
            call_command("seed_rls_smoke_workspaces")

    @override_settings(DEBUG=True)
    @patch(
        "apps.orgs.management.commands.seed_rls_smoke_workspaces."
        "check_restricted_runtime_role",
        return_value=[Error("unsafe role")],
    )
    def test_refuses_an_unsafe_runtime_role(self, _check_role):
        with self.assertRaisesMessage(CommandError, "unsafe role"):
            call_command("seed_rls_smoke_workspaces")
