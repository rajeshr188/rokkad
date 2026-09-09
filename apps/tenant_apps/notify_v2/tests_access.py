from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.tenant_apps.notify_v2.access import (
    NOTIFY_V2_ACTION_PERMISSIONS,
    NOTIFY_V2_ADMIN_ACTION,
    assert_notify_v2_action_permission,
    assert_notify_v2_permission,
    assert_notify_v2_workspace_access,
    notify_v2_admin_required,
)


class NotifyV2AccessTests(SimpleTestCase):
    def setUp(self):
        self.user = SimpleNamespace(is_authenticated=True, pk=7)
        self.workspace = SimpleNamespace(pk=3)
        self.request = SimpleNamespace(user=self.user)

    def _access(self, *, membership=object(), platform_override=False, allowed=()):
        return SimpleNamespace(
            membership=membership,
            platform_override=platform_override,
            can=MagicMock(side_effect=lambda action: action in allowed),
        )

    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace", return_value=None)
    def test_missing_workspace_fails_closed(self, _resolve_workspace):
        with self.assertRaisesMessage(PermissionDenied, "No tenant workspace selected"):
            assert_notify_v2_workspace_access(self.request)

    @patch(
        "apps.tenant_apps.notify_v2.access.resolve_request_workspace",
        side_effect=AttributeError("invalid"),
    )
    def test_invalid_workspace_context_fails_closed(self, _resolve_workspace):
        with self.assertRaisesMessage(PermissionDenied, "Invalid tenant workspace context"):
            assert_notify_v2_workspace_access(self.request)

    @patch("apps.tenant_apps.notify_v2.access.resolve_workspace_access")
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_nonmember_is_denied(self, resolve_workspace, resolve_access):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = self._access(membership=None)

        with self.assertRaisesMessage(PermissionDenied, "Not a workspace member"):
            assert_notify_v2_workspace_access(self.request)

    @patch("apps.tenant_apps.notify_v2.access.resolve_workspace_access")
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_member_access_is_resolved_once_and_cached(
        self, resolve_workspace, resolve_access
    ):
        access = self._access()
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = access

        result = assert_notify_v2_workspace_access(self.request)

        self.assertIs(result, self.workspace)
        self.assertIs(self.request.notify_v2_workspace_access, access)
        resolve_access.assert_called_once_with(actor=self.user, workspace=self.workspace)

    @patch("apps.tenant_apps.notify_v2.access.resolve_workspace_access")
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_permission_supports_any_and_all_semantics(
        self, resolve_workspace, resolve_access
    ):
        access = self._access(allowed={"data.view"})
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = access

        self.assertIs(
            assert_notify_v2_permission(self.request, "data.view", "data.edit"),
            self.workspace,
        )
        with self.assertRaises(PermissionDenied):
            assert_notify_v2_permission(
                self.request, "data.view", "data.edit", require_all=True
            )

    @patch("apps.tenant_apps.notify_v2.access.resolve_workspace_access")
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_workflow_actions_use_stable_data_actions(
        self, resolve_workspace, resolve_access
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = self._access(allowed={"data.view"})

        self.assertEqual(NOTIFY_V2_ACTION_PERMISSIONS["view"], ("data.view",))
        self.assertEqual(NOTIFY_V2_ACTION_PERMISSIONS["send"], ("data.edit",))
        self.assertIs(
            assert_notify_v2_action_permission(self.request, "view"), self.workspace
        )
        with self.assertRaises(PermissionDenied):
            assert_notify_v2_action_permission(self.request, "send")

    def test_unknown_action_fails_closed(self):
        with self.assertRaisesMessage(ValueError, "Unknown Notify v2 action"):
            assert_notify_v2_action_permission(self.request, "unknown")

    @patch("apps.tenant_apps.notify_v2.access.resolve_workspace_access")
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_provider_setup_requires_workspace_settings_action(
        self, resolve_workspace, resolve_access
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = self._access(allowed={"data.edit"})
        protected = notify_v2_admin_required(lambda request: "allowed")

        with self.assertRaisesMessage(PermissionDenied, "provider setup"):
            protected(self.request)

        resolve_access.return_value = self._access(allowed={NOTIFY_V2_ADMIN_ACTION})
        self.assertEqual(protected(self.request), "allowed")
        self.assertIs(self.request.notify_v2_workspace, self.workspace)

    @patch("apps.tenant_apps.notify_v2.access.resolve_workspace_access")
    @patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace")
    def test_platform_override_uses_workspace_access_actions(
        self, resolve_workspace, resolve_access
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = self._access(
            membership=None,
            platform_override=True,
            allowed={NOTIFY_V2_ADMIN_ACTION},
        )
        protected = notify_v2_admin_required(lambda request: "allowed")

        self.assertEqual(protected(self.request), "allowed")


class NotifyBulkDownloadAccessTests(SimpleTestCase):
    def test_bulk_download_requires_view_and_export_before_loading_files(self):
        from django.test import RequestFactory
        from apps.orgs.access import WorkspaceAccess
        from apps.tenant_apps.notify_v2.views import batch_download_artifacts
        user = SimpleNamespace(is_authenticated=True)
        workspace = SimpleNamespace(pk=1, slug="test")
        request = RequestFactory().get("/notify/batch/1/download/")
        request.user = user
        request.workspace = workspace
        with patch("apps.tenant_apps.notify_v2.access.resolve_request_workspace", return_value=workspace), patch(
            "apps.tenant_apps.notify_v2.access.resolve_workspace_access"
        ) as resolve, patch("apps.tenant_apps.notify_v2.views.get_object_or_404") as lookup:
            for actions in ({"data.view"}, {"data.export"}, set()):
                resolve.return_value = WorkspaceAccess(user, workspace, object(), False, frozenset(actions))
                with self.assertRaises(PermissionDenied):
                    batch_download_artifacts(request, 1)
                lookup.assert_not_called()
            resolve.return_value = WorkspaceAccess(user, workspace, object(), False, frozenset({"data.view", "data.export"}))
            from django.http import Http404
            lookup.side_effect = Http404
            with self.assertRaises(Http404):
                batch_download_artifacts(request, 1)
            lookup.assert_called_once()
