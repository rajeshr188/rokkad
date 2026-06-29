from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.tenant_apps.product.access import (
    PRODUCT_ACTION_PERMISSIONS,
    assert_product_action_permission,
    assert_product_permission,
    assert_product_workspace_access,
    can_administer_product_data,
)


class ProductAccessHelperTests(SimpleTestCase):
    def _request(self, *, user=None):
        if user is None:
            user = SimpleNamespace(is_authenticated=True, is_superuser=False)
        return SimpleNamespace(user=user)

    def _workspace(self, *, owner=None):
        return SimpleNamespace(owner=owner, schema_name="tenant1")

    @patch("apps.tenant_apps.product.access.resolve_request_workspace", return_value=None)
    def test_workspace_access_fails_closed_without_workspace(self, _mock_resolve):
        with self.assertRaisesMessage(PermissionDenied, "No tenant workspace selected"):
            assert_product_workspace_access(self._request())

    @patch(
        "apps.tenant_apps.product.access.resolve_request_workspace",
        side_effect=AttributeError("bad tenant"),
    )
    def test_workspace_access_fails_closed_for_invalid_context(self, _mock_resolve):
        with self.assertRaisesMessage(PermissionDenied, "Invalid tenant workspace context"):
            assert_product_workspace_access(self._request())

    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_workspace_owner_is_allowed(self, mock_resolve):
        user = SimpleNamespace(is_authenticated=True, is_superuser=False)
        workspace = self._workspace(owner=user)
        mock_resolve.return_value = workspace

        self.assertIs(assert_product_workspace_access(self._request(user=user)), workspace)

    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_platform_admin_is_allowed(self, mock_resolve):
        admin = SimpleNamespace(is_authenticated=True, is_superuser=True)
        workspace = self._workspace()
        mock_resolve.return_value = workspace

        self.assertIs(assert_product_workspace_access(self._request(user=admin)), workspace)

    @patch("apps.tenant_apps.product.access.get_workspace_role_name", return_value=None)
    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_non_member_is_denied(self, mock_resolve, _mock_role):
        mock_resolve.return_value = self._workspace()

        with self.assertRaisesMessage(PermissionDenied, "Not a workspace member"):
            assert_product_workspace_access(self._request())

    @patch("apps.tenant_apps.product.access.get_workspace_role_name", return_value="Member")
    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_workspace_member_is_allowed(self, mock_resolve, _mock_role):
        workspace = self._workspace()
        mock_resolve.return_value = workspace

        self.assertIs(assert_product_workspace_access(self._request()), workspace)

    @patch(
        "apps.tenant_apps.product.access.get_effective_permissions",
        return_value={"data_create"},
    )
    @patch("apps.tenant_apps.product.access.get_workspace_role_name", return_value="Member")
    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_permission_allows_required_generic_data_permission(
        self,
        mock_resolve,
        _mock_role,
        _mock_permissions,
    ):
        workspace = self._workspace()
        mock_resolve.return_value = workspace

        self.assertIs(assert_product_permission(self._request(), "data_create"), workspace)

    @patch(
        "apps.tenant_apps.product.access.get_effective_permissions",
        return_value={"data_view"},
    )
    @patch("apps.tenant_apps.product.access.get_workspace_role_name", return_value="Viewer")
    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_permission_denies_missing_permission(
        self,
        mock_resolve,
        _mock_role,
        _mock_permissions,
    ):
        mock_resolve.return_value = self._workspace()

        with self.assertRaisesMessage(
            PermissionDenied,
            "Missing workspace permission(s): data_delete",
        ):
            assert_product_permission(self._request(), "data_delete")

    @patch(
        "apps.tenant_apps.product.access.get_effective_permissions",
        return_value={"data_export"},
    )
    @patch("apps.tenant_apps.product.access.get_workspace_role_name", return_value="Member")
    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_action_permission_uses_product_permission_map(
        self,
        mock_resolve,
        _mock_role,
        _mock_permissions,
    ):
        workspace = self._workspace()
        mock_resolve.return_value = workspace

        self.assertEqual(PRODUCT_ACTION_PERMISSIONS["export"], ("data_export",))
        self.assertIs(assert_product_action_permission(self._request(), "export"), workspace)

    def test_unknown_product_action_fails_fast(self):
        with self.assertRaisesMessage(ValueError, "Unknown Product action 'archive'"):
            assert_product_action_permission(self._request(), "archive")

    @patch("apps.tenant_apps.product.access.get_workspace_role_name", return_value="Admin")
    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_admin_role_can_administer_product_data(self, mock_resolve, _mock_role):
        mock_resolve.return_value = self._workspace()

        self.assertTrue(can_administer_product_data(self._request()))

    @patch("apps.tenant_apps.product.access.get_workspace_role_name", return_value="Viewer")
    @patch("apps.tenant_apps.product.access.resolve_request_workspace")
    def test_viewer_role_cannot_administer_product_data(self, mock_resolve, _mock_role):
        mock_resolve.return_value = self._workspace()

        self.assertFalse(can_administer_product_data(self._request()))
