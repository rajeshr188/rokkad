import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse

from apps.orgs.forms import ArchiveWorkspaceForm
from apps.orgs import views
from apps.orgs.services import control_plane


class ArchiveWorkspaceFormTests(SimpleTestCase):
    def setUp(self):
        self.workspace = SimpleNamespace(name="JCL Finance")

    def test_requires_exact_workspace_name(self):
        form = ArchiveWorkspaceForm(
            {"confirmation_name": "jcl finance"},
            workspace=self.workspace,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("exactly as shown", form.errors["confirmation_name"][0])

    def test_accepts_exact_workspace_name(self):
        form = ArchiveWorkspaceForm(
            {"confirmation_name": "JCL Finance"},
            workspace=self.workspace,
        )

        self.assertTrue(form.is_valid())


class WorkspaceLifecycleViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.owner = SimpleNamespace(pk=7)
        self.workspace = SimpleNamespace(
            id=9,
            name="JCL Finance",
            owner=self.owner,
            schema_name="jcl_finance",
        )

    def test_lifecycle_routes_are_available(self):
        self.assertEqual(reverse("archived_workspaces"), "/orgs/workspace/archived/")
        self.assertEqual(
            reverse("workspace_restore", kwargs={"workspace_id": 9}),
            "/orgs/workspace/9/restore/",
        )

    def test_owner_access_accepts_platform_admin_role_label(self):
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=True))
        access = {"role_name": "Superuser"}

        with patch("apps.orgs.views._assert_workspace_access", return_value=access), \
                patch("apps.orgs.views.is_platform_admin", return_value=True):
            result = views._assert_owner_access(
                request,
                self.workspace,
                allow_platform_admin=True,
            )

        self.assertIs(result, access)

    def test_archive_rejects_incorrect_confirmation_without_mutating(self):
        request = self.factory.post(
            "/workspace/9/settings/archive/",
            {"confirmation_name": "wrong"},
        )
        request.user = self.owner
        view = inspect.unwrap(views.workspace_delete)

        with patch("apps.orgs.views.get_object_or_404", return_value=self.workspace), \
                patch("apps.orgs.views._assert_workspace_access"), \
                patch("apps.orgs.views._assert_owner_access"), \
                patch("apps.orgs.views.control_plane.archive_workspace") as archive, \
                patch("apps.orgs.views.render", return_value=MagicMock()) as render:
            view(request, workspace_id=9)

        archive.assert_not_called()
        form = render.call_args.args[2]["form"]
        self.assertIn("confirmation_name", form.errors)

    def test_archive_authorizes_against_url_workspace_not_request_tenant(self):
        public_tenant = SimpleNamespace(schema_name="public")
        self.owner.is_authenticated = True
        request = self.factory.get("/orgs/workspace/9/delete/")
        request.user = self.owner
        request.tenant = public_tenant

        with patch("apps.orgs.views.get_object_or_404", return_value=self.workspace), \
                patch("apps.orgs.views._assert_workspace_access") as access, \
                patch("apps.orgs.views._assert_owner_access") as owner_access, \
                patch("apps.orgs.views.render", return_value=MagicMock()) as render:
            views.workspace_delete(request, workspace_id=9)

        access.assert_called_once_with(
            request,
            self.workspace,
            required_permissions={"workspace_delete"},
            allow_platform_admin=True,
        )
        owner_access.assert_called_once_with(
            request,
            self.workspace,
            allow_platform_admin=True,
        )
        render.assert_called_once()

    def test_restore_allows_owner_and_uses_control_plane(self):
        request = self.factory.post("/orgs/workspace/9/restore/")
        request.user = self.owner
        view = inspect.unwrap(views.workspace_restore)

        with patch("apps.orgs.views.get_object_or_404", return_value=self.workspace), \
                patch("apps.orgs.views.is_platform_admin", return_value=False), \
                patch("apps.orgs.views.control_plane.restore_workspace") as restore, \
                patch("apps.orgs.views.messages.success"), \
                patch("apps.orgs.views.redirect", return_value=MagicMock()):
            view(request, workspace_id=9)

        restore.assert_called_once_with(
            company=self.workspace,
            actor=self.owner,
            request=request,
        )

    def test_restore_rejects_non_owner(self):
        request = self.factory.post("/orgs/workspace/9/restore/")
        request.user = SimpleNamespace(pk=8)
        view = inspect.unwrap(views.workspace_restore)

        with patch("apps.orgs.views.get_object_or_404", return_value=self.workspace), \
                patch("apps.orgs.views.is_platform_admin", return_value=False), \
                patch("apps.orgs.views.control_plane.restore_workspace") as restore:
            with self.assertRaises(PermissionDenied):
                view(request, workspace_id=9)

        restore.assert_not_called()


class WorkspaceLifecycleServiceTests(SimpleTestCase):
    def test_archive_uses_soft_archive_and_never_hard_delete(self):
        company = MagicMock(name="company")
        company.name = "JCL Finance"
        actor = SimpleNamespace(pk=7)
        request = SimpleNamespace()

        with patch(
            "apps.orgs.services.control_plane._control_plane_transaction"
        ) as public_context, patch(
            "apps.orgs.services.control_plane.AuditLog.log"
        ):
            public_context.return_value.__enter__.return_value = None
            control_plane.archive_workspace(
                company=company,
                actor=actor,
                request=request,
            )

        company.archive.assert_called_once_with()
        company.hard_delete.assert_not_called()

    def test_restore_reactivates_same_workspace(self):
        company = MagicMock(name="company")
        company.name = "JCL Finance"
        actor = SimpleNamespace(pk=7)
        request = SimpleNamespace()

        with patch(
            "apps.orgs.services.control_plane._control_plane_transaction"
        ) as public_context, patch(
            "apps.orgs.services.control_plane.AuditLog.log"
        ):
            public_context.return_value.__enter__.return_value = None
            restored = control_plane.restore_workspace(
                company=company,
                actor=actor,
                request=request,
            )

        company.restore.assert_called_once_with()
        self.assertIs(restored, company)
