from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase

from apps.tenant_apps.loans.access import (
    LOANS_OWNER_ACTION,
    LOANS_SETUP_ACTION,
    LOANS_WORKSPACE_ACTION,
    assert_loans_owner_access,
    assert_loans_setup_access,
    assert_loans_workspace_access,
)
from apps.tenant_apps.loans.services.physical_verification import (
    PawnPhysicalVerificationError,
    _require_owner as require_physical_verification_owner,
)
from apps.tenant_apps.loans.services.storage_operations import (
    PawnStorageError,
    _require_owner as require_storage_owner,
)
from apps.tenant_apps.loans.web.pawn_custody_actions import _can_manage_storage


class LoansAccessTests(SimpleTestCase):
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

    @patch("apps.tenant_apps.loans.access.resolve_request_workspace", return_value=None)
    def test_missing_workspace_fails_closed(self, _resolve_workspace):
        with self.assertRaisesMessage(PermissionDenied, "No tenant workspace selected"):
            assert_loans_workspace_access(self.request)

    @patch("apps.tenant_apps.loans.access.resolve_workspace_access")
    @patch("apps.tenant_apps.loans.access.resolve_request_workspace")
    def test_nonmember_is_denied(self, resolve_workspace, resolve_access):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = self._access(membership=None)

        with self.assertRaisesMessage(PermissionDenied, "workspace membership"):
            assert_loans_workspace_access(self.request)

    @patch("apps.tenant_apps.loans.access.resolve_workspace_access")
    @patch("apps.tenant_apps.loans.access.resolve_request_workspace")
    def test_workspace_access_requires_data_view(
        self, resolve_workspace, resolve_access
    ):
        access = self._access(allowed={LOANS_WORKSPACE_ACTION})
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = access

        self.assertIs(assert_loans_workspace_access(self.request), self.workspace)
        self.assertIs(self.request.loans_workspace_access, access)

    @patch("apps.tenant_apps.loans.access.resolve_workspace_access")
    @patch("apps.tenant_apps.loans.access.resolve_request_workspace")
    def test_setup_requires_workspace_settings_action(
        self, resolve_workspace, resolve_access
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = self._access(allowed={LOANS_WORKSPACE_ACTION})

        with self.assertRaisesMessage(PermissionDenied, "administration access"):
            assert_loans_setup_access(self.request)

        resolve_access.return_value = self._access(allowed={LOANS_SETUP_ACTION})
        self.assertIs(assert_loans_setup_access(self.request), self.workspace)

    @patch("apps.tenant_apps.loans.access.resolve_workspace_access")
    @patch("apps.tenant_apps.loans.access.resolve_request_workspace")
    def test_owner_boundary_uses_owner_only_workspace_action(
        self, resolve_workspace, resolve_access
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = self._access(allowed={LOANS_SETUP_ACTION})

        with self.assertRaisesMessage(PermissionDenied, "workspace Owner"):
            assert_loans_owner_access(self.request)

        resolve_access.return_value = self._access(allowed={LOANS_OWNER_ACTION})
        self.assertIs(assert_loans_owner_access(self.request), self.workspace)

    @patch("apps.tenant_apps.loans.access.resolve_workspace_access")
    @patch("apps.tenant_apps.loans.access.resolve_request_workspace")
    def test_platform_override_still_requires_canonical_action(
        self, resolve_workspace, resolve_access
    ):
        resolve_workspace.return_value = self.workspace
        resolve_access.return_value = self._access(
            membership=None,
            platform_override=True,
            allowed={LOANS_OWNER_ACTION},
        )

        self.assertIs(assert_loans_owner_access(self.request), self.workspace)

    @patch("apps.tenant_apps.loans.services.storage_operations.resolve_workspace_access")
    @patch("apps.tenant_apps.loans.services.physical_verification.resolve_workspace_access")
    def test_custody_services_use_owner_only_workspace_action(
        self, resolve_verification_access, resolve_storage_access
    ):
        denied = self._access(allowed={LOANS_SETUP_ACTION})
        resolve_verification_access.return_value = denied
        resolve_storage_access.return_value = denied

        with self.assertRaises(PawnPhysicalVerificationError):
            require_physical_verification_owner(self.workspace, self.user)
        with self.assertRaises(PawnStorageError):
            require_storage_owner(self.workspace, self.user)

        allowed = self._access(allowed={LOANS_OWNER_ACTION})
        resolve_verification_access.return_value = allowed
        resolve_storage_access.return_value = allowed
        require_physical_verification_owner(self.workspace, self.user)
        require_storage_owner(self.workspace, self.user)

        resolve_verification_access.assert_called_with(
            actor=self.user, workspace=self.workspace
        )
        resolve_storage_access.assert_called_with(
            actor=self.user, workspace=self.workspace
        )

    def test_custody_web_helper_consumes_cached_workspace_access(self):
        access = self._access(allowed={LOANS_OWNER_ACTION})
        request = SimpleNamespace(loans_workspace_access=access)

        self.assertTrue(_can_manage_storage(request))
        access.can.assert_called_once_with(LOANS_OWNER_ACTION)
