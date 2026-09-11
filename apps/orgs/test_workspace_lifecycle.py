import inspect
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from apps.orgs.forms import ArchiveWorkspaceForm
from apps.orgs import views
from apps.orgs.services import control_plane
from apps.orgs.models import Company
from apps.orgs.middleware_v2 import SecureWorkspaceMiddleware
from apps.tenancy.context import workspace_context
from apps.tenant_apps.rates.models import RateSource


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

        with patch("apps.orgs.web.access_helpers._assert_workspace_access", return_value=access), \
                patch("apps.orgs.web.access_helpers.is_platform_admin", return_value=True):
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

        with patch("apps.orgs.web.workspace_lifecycle.get_object_or_404", return_value=self.workspace), \
                patch("apps.orgs.web.workspace_lifecycle._assert_workspace_access"), \
                patch("apps.orgs.web.workspace_lifecycle._assert_owner_access"), \
                patch("apps.orgs.web.workspace_lifecycle.control_plane.archive_workspace") as archive, \
                patch("apps.orgs.web.workspace_lifecycle.render", return_value=MagicMock()) as render:
            view(request, workspace_id=9)

        archive.assert_not_called()
        form = render.call_args.args[2]["form"]
        self.assertIn("confirmation_name", form.errors)

    def test_archive_authorizes_against_url_workspace_not_request_workspace(self):
        self.owner.is_authenticated = True
        request = self.factory.get("/orgs/workspace/9/delete/")
        request.user = self.owner
        request.workspace = None

        with patch("apps.orgs.web.workspace_lifecycle.get_object_or_404", return_value=self.workspace), \
                patch("apps.orgs.web.workspace_lifecycle._assert_workspace_access") as access, \
                patch("apps.orgs.web.workspace_lifecycle._assert_owner_access") as owner_access, \
                patch("apps.orgs.web.workspace_lifecycle.render", return_value=MagicMock()) as render:
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

        with patch("apps.orgs.web.workspace_lifecycle.get_object_or_404", return_value=self.workspace), \
                patch("apps.orgs.web.workspace_lifecycle.is_platform_admin", return_value=False), \
                patch("apps.orgs.web.workspace_lifecycle.control_plane.restore_workspace") as restore, \
                patch("apps.orgs.web.workspace_lifecycle.messages.success"), \
                patch("apps.orgs.web.workspace_lifecycle.redirect", return_value=MagicMock()):
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

        with patch("apps.orgs.web.workspace_lifecycle.get_object_or_404", return_value=self.workspace), \
                patch("apps.orgs.web.workspace_lifecycle.is_platform_admin", return_value=False), \
                patch("apps.orgs.web.workspace_lifecycle.control_plane.restore_workspace") as restore:
            with self.assertRaises(PermissionDenied):
                view(request, workspace_id=9)

        restore.assert_not_called()


class WorkspaceLifecycleMiddlewareTests(SimpleTestCase):
    def setUp(self):
        self.middleware = SecureWorkspaceMiddleware(lambda request: None)
        self.platform = SimpleNamespace(id=1, email="platform@example.com")
        self.workspace = SimpleNamespace(
            id=9,
            name="JCL Finance",
            schema_name="jcl-finance",
            owner_id=7,
            slug="jcl-finance",
            lifecycle_state=Company.LifecycleState.SUSPENDED,
        )
        self.platform_access = SimpleNamespace(
            actor=self.platform,
            platform_override=True,
            membership=None,
            can=lambda _permission: True,
        )

    def test_platform_override_does_not_bypass_suspended_business_boundary(self):
        request = SimpleNamespace(path="/w/jcl-finance/loans/")
        with patch(
            "apps.orgs.middleware_v2.resolve_workspace_access",
            return_value=self.platform_access,
        ):
            result = self.middleware._validate_workspace_access(
                self.platform, self.workspace, request
            )

        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "WORKSPACE_LIFECYCLE_DENIED")

    def test_platform_can_use_suspended_recovery_surface(self):
        request = SimpleNamespace(path="/w/jcl-finance/settings/billing/")
        with patch(
            "apps.orgs.middleware_v2.resolve_workspace_access",
            return_value=self.platform_access,
        ):
            result = self.middleware._validate_workspace_access(
                self.platform, self.workspace, request
            )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "SUPERUSER")

    def test_archived_owner_can_reach_explicit_export_surface(self):
        owner = SimpleNamespace(id=7, email="owner@example.com")
        membership = SimpleNamespace(role=SimpleNamespace(name="Owner"))
        access = SimpleNamespace(
            actor=owner,
            platform_override=False,
            membership=membership,
            can=lambda _permission: True,
        )
        self.workspace.lifecycle_state = Company.LifecycleState.ARCHIVED
        request = SimpleNamespace(path="/w/jcl-finance/data-tools/export/")
        with patch(
            "apps.orgs.middleware_v2.resolve_workspace_access", return_value=access
        ):
            result = self.middleware._validate_workspace_access(
                owner, self.workspace, request
            )

        self.assertTrue(result["allowed"])
        self.assertEqual(result["reason"], "AUTHORIZED")


class WorkspaceLifecycleServiceTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.owner = users.objects.create_user(username="owner", password="test")
        self.platform = users.objects.create_superuser(
            username="platform", email="platform@example.com", password="test"
        )
        self.other = users.objects.create_user(username="other", password="test")
        self.workspace = Company.all_objects.create(
            name="JCL Finance",
            schema_name="jcl-finance",
            owner=self.owner,
            creator=self.owner,
        )

    def transition(self, target, actor, reason="Phase 3 test"):
        self.workspace = control_plane.transition_workspace_lifecycle(
            workspace=self.workspace,
            target_state=target,
            actor=actor,
            reason=reason,
        )
        return self.workspace

    def test_owner_can_archive_and_reactivate_same_workspace(self):
        workspace_id = self.workspace.pk
        self.transition(Company.LifecycleState.ARCHIVED, self.owner)
        self.assertFalse(Company.objects.filter(pk=workspace_id).exists())
        self.assertTrue(Company.all_objects.filter(pk=workspace_id).exists())

        self.transition(Company.LifecycleState.ACTIVE, self.owner)
        self.assertEqual(self.workspace.pk, workspace_id)
        self.assertTrue(Company.objects.filter(pk=workspace_id).exists())

    def test_archive_and_suspension_preserve_business_row_ownership(self):
        with workspace_context(self.workspace.pk):
            source = RateSource.objects.create(
                workspace=self.workspace,
                name="Lifecycle Evidence",
                location="Vault",
            )
        evidence = (source.pk, source.workspace_id, source.name, source.location)

        self.transition(Company.LifecycleState.SUSPENDED, self.platform)
        with workspace_context(self.workspace.pk):
            suspended = RateSource.objects.get(pk=source.pk)
            self.assertEqual(
                (suspended.pk, suspended.workspace_id, suspended.name, suspended.location),
                evidence,
            )

        self.transition(Company.LifecycleState.ACTIVE, self.platform)
        self.transition(Company.LifecycleState.ARCHIVED, self.owner)
        with workspace_context(self.workspace.pk):
            archived = RateSource.objects.get(pk=source.pk)
            self.assertEqual(
                (archived.pk, archived.workspace_id, archived.name, archived.location),
                evidence,
            )

    def test_platform_can_suspend_and_clear_suspension(self):
        self.transition(Company.LifecycleState.SUSPENDED, self.platform)
        self.transition(Company.LifecycleState.ACTIVE, self.platform)
        self.assertEqual(self.workspace.lifecycle_state, Company.LifecycleState.ACTIVE)

    def test_owner_cannot_suspend_workspace(self):
        with self.assertRaises(PermissionDenied):
            self.transition(Company.LifecycleState.SUSPENDED, self.owner)

    def test_platform_can_schedule_and_cancel_deletion(self):
        self.transition(Company.LifecycleState.ARCHIVED, self.owner)
        self.transition(Company.LifecycleState.DELETION_PENDING, self.platform)
        self.transition(Company.LifecycleState.ARCHIVED, self.platform)
        self.assertEqual(self.workspace.lifecycle_state, Company.LifecycleState.ARCHIVED)

    def test_invalid_transition_and_blank_reason_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.transition(Company.LifecycleState.DELETION_PENDING, self.platform)
        with self.assertRaises(ValidationError):
            self.transition(Company.LifecycleState.ARCHIVED, self.owner, reason=" ")

    def test_ordinary_model_delete_is_disabled(self):
        with self.assertRaisesMessage(ValueError, "privileged retention workflow"):
            self.workspace.delete()
