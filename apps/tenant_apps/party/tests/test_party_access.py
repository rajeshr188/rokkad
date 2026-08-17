from types import SimpleNamespace
from unittest.mock import patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.tenant_apps.party.access import (
    PARTY_ACTION_PERMISSIONS,
    PARTY_ADMIN_ACTION,
    assert_party_action_permission,
    assert_party_permission,
    assert_party_workspace_access,
    can_administer_party_data,
)


class PartyAccessHelperTests(SimpleTestCase):
    def setUp(self):
        self.workspace = SimpleNamespace(id=13)
        self.user = SimpleNamespace(is_authenticated=True)
        self.request = SimpleNamespace(user=self.user, workspace=self.workspace)

    @patch("apps.tenant_apps.party.access.resolve_request_workspace", return_value=None)
    def test_workspace_access_fails_closed_without_workspace(self, _resolve):
        with self.assertRaisesMessage(PermissionDenied, "No tenant workspace selected"):
            assert_party_workspace_access(self.request)

    @patch(
        "apps.tenant_apps.party.access.resolve_request_workspace",
        side_effect=AttributeError("bad context"),
    )
    def test_workspace_access_fails_closed_for_invalid_context(self, _resolve):
        with self.assertRaisesMessage(PermissionDenied, "Invalid tenant workspace context"):
            assert_party_workspace_access(self.request)

    @patch("apps.tenant_apps.party.access.resolve_request_workspace")
    @patch("apps.tenant_apps.party.access.resolve_workspace_access")
    def test_non_member_is_denied(self, resolve_access, resolve_workspace):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = SimpleNamespace(
            membership=None,
            platform_override=False,
        )

        with self.assertRaisesMessage(PermissionDenied, "Not a workspace member"):
            assert_party_workspace_access(self.request)

    @patch("apps.tenant_apps.party.access.resolve_request_workspace")
    @patch("apps.tenant_apps.party.access.resolve_workspace_access")
    def test_member_access_is_resolved_once(self, resolve_access, resolve_workspace):
        resolve_workspace.return_value = self.workspace
        access = SimpleNamespace(membership=object(), platform_override=False)
        resolve_access.return_value = access

        self.assertIs(assert_party_workspace_access(self.request), self.workspace)
        self.assertIs(self.request.party_workspace_access, access)
        resolve_access.assert_called_once_with(actor=self.user, workspace=self.workspace)

    @patch("apps.tenant_apps.party.access.resolve_request_workspace")
    @patch("apps.tenant_apps.party.access.resolve_workspace_access")
    def test_permission_supports_any_and_all_semantics(
        self, resolve_access, resolve_workspace
    ):
        resolve_workspace.return_value = self.workspace
        granted = {"contact.create", "data.create"}
        resolve_access.return_value = SimpleNamespace(
            membership=object(),
            platform_override=False,
            can=lambda action: action in granted,
        )

        self.assertIs(
            assert_party_permission(
                self.request, "contact.create", "missing.action", require_all=False
            ),
            self.workspace,
        )
        self.assertIs(
            assert_party_permission(
                self.request, "contact.create", "data.create", require_all=True
            ),
            self.workspace,
        )

    @patch("apps.tenant_apps.party.access.resolve_request_workspace")
    @patch("apps.tenant_apps.party.access.resolve_workspace_access")
    def test_action_map_uses_stable_codes_and_denies_missing_action(
        self, resolve_access, resolve_workspace
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = SimpleNamespace(
            membership=object(),
            platform_override=False,
            can=lambda _action: False,
        )

        self.assertEqual(
            PARTY_ACTION_PERMISSIONS["export"],
            ("contact.export", "data.export"),
        )
        with self.assertRaisesMessage(PermissionDenied, "contact.export, data.export"):
            assert_party_action_permission(self.request, "export")

    def test_unknown_party_action_fails_fast(self):
        with self.assertRaisesMessage(ValueError, "Unknown Party action 'archive'"):
            assert_party_action_permission(self.request, "archive")

    @patch("apps.tenant_apps.party.access.resolve_request_workspace")
    @patch("apps.tenant_apps.party.access.resolve_workspace_access")
    def test_administration_uses_stable_workspace_action(
        self, resolve_access, resolve_workspace
    ):
        resolve_workspace.return_value = self.workspace
        checked = []
        resolve_access.return_value = SimpleNamespace(
            membership=object(),
            platform_override=False,
            can=lambda action: checked.append(action) or True,
        )

        self.assertTrue(can_administer_party_data(self.request))
        self.assertEqual(PARTY_ADMIN_ACTION, "workspace.settings.manage")
        self.assertEqual(checked, ["workspace.settings.manage"])

    @patch("apps.tenant_apps.party.access.resolve_request_workspace")
    @patch("apps.tenant_apps.party.access.resolve_workspace_access")
    def test_platform_override_flows_through_workspace_access(
        self, resolve_access, resolve_workspace
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = SimpleNamespace(
            membership=None,
            platform_override=True,
            can=lambda _action: True,
        )

        self.assertIs(assert_party_action_permission(self.request, "view"), self.workspace)
