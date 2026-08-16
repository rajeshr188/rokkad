from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.tenant_apps.notify_v2.access import (
    assert_notify_v2_action_permission,
    assert_notify_v2_workspace_access,
)


class NotifyV2AccessTests(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(is_authenticated=True, pk=7)
        self.workspace = SimpleNamespace(owner=None, owner_id=11)
        self.request = SimpleNamespace(user=self.user)

    @patch("apps.tenant_apps.notify_v2.access.is_platform_admin", return_value=False)
    @patch("apps.tenant_apps.notify_v2.access.get_workspace_role_name", return_value="Staff")
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_workspace_member_has_workspace_access(self, resolve_workspace, _role, _admin):
        resolve_workspace.return_value = self.workspace

        result = assert_notify_v2_workspace_access(self.request)

        self.assertIs(result, self.workspace)

    @patch("apps.tenant_apps.notify_v2.access.is_platform_admin", return_value=False)
    @patch("apps.tenant_apps.notify_v2.access.get_workspace_role_name", return_value="Staff")
    @patch("apps.tenant_apps.notify_v2.access.get_effective_permissions", return_value={"data_view"})
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_view_action_uses_workspace_data_view_permission(
        self, resolve_workspace, _permissions, _role, _admin
    ):
        resolve_workspace.return_value = self.workspace

        result = assert_notify_v2_action_permission(self.request, "view")

        self.assertIs(result, self.workspace)

    @patch("apps.tenant_apps.notify_v2.access.is_platform_admin", return_value=False)
    @patch("apps.tenant_apps.notify_v2.access.get_workspace_role_name", return_value="Staff")
    @patch("apps.tenant_apps.notify_v2.access.get_effective_permissions", return_value={"data_view"})
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_send_action_requires_data_edit_permission(
        self, resolve_workspace, _permissions, _role, _admin
    ):
        resolve_workspace.return_value = self.workspace

        with self.assertRaises(PermissionDenied):
            assert_notify_v2_action_permission(self.request, "send")

    def test_unknown_action_fails_closed(self):
        with self.assertRaisesMessage(ValueError, "Unknown Notify v2 action"):
            assert_notify_v2_action_permission(self.request, "unknown")
