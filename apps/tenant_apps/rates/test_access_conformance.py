from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.tenant_apps.rates.access import (
    assert_rate_action_permission,
    assert_rate_workspace_access,
)


class RateAccessConformanceTests(SimpleTestCase):
    def setUp(self):
        self.workspace = SimpleNamespace(id=11)
        self.user = SimpleNamespace(is_authenticated=True)
        self.request = SimpleNamespace(user=self.user, workspace=self.workspace)

    @patch("apps.tenant_apps.rates.access.resolve_request_workspace")
    @patch("apps.tenant_apps.rates.access.resolve_workspace_access")
    def test_non_member_fails_closed(self, resolve_access, resolve_workspace):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = SimpleNamespace(
            membership=None,
            platform_override=False,
        )

        with self.assertRaisesMessage(PermissionDenied, "Not a workspace member"):
            assert_rate_workspace_access(self.request)

    @patch("apps.tenant_apps.rates.access.resolve_request_workspace")
    @patch("apps.tenant_apps.rates.access.resolve_workspace_access")
    def test_member_action_uses_stable_workspace_access_code(
        self, resolve_access, resolve_workspace
    ):
        resolve_workspace.return_value = self.workspace
        checked = []
        access = SimpleNamespace(
            membership=object(),
            platform_override=False,
            can=lambda action: checked.append(action) or action == "data.view",
        )
        resolve_access.return_value = access

        result = assert_rate_action_permission(self.request, "view")

        self.assertIs(result, self.workspace)
        self.assertIs(self.request.rate_workspace_access, access)
        self.assertEqual(checked, ["data.view"])

    @patch("apps.tenant_apps.rates.access.resolve_request_workspace")
    @patch("apps.tenant_apps.rates.access.resolve_workspace_access")
    def test_missing_action_is_denied(self, resolve_access, resolve_workspace):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = SimpleNamespace(
            membership=object(),
            platform_override=False,
            can=lambda _action: False,
        )

        with self.assertRaisesMessage(PermissionDenied, "data.delete"):
            assert_rate_action_permission(self.request, "delete")

    @patch("apps.tenant_apps.rates.access.resolve_request_workspace")
    @patch("apps.tenant_apps.rates.access.resolve_workspace_access")
    def test_platform_override_uses_workspace_access_result(
        self, resolve_access, resolve_workspace
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = SimpleNamespace(
            membership=None,
            platform_override=True,
            can=lambda _action: True,
        )

        self.assertIs(assert_rate_action_permission(self.request, "edit"), self.workspace)
        resolve_access.assert_called_once_with(actor=self.user, workspace=self.workspace)
