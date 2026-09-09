"""Stored grants must be revocable and isolated by Workspace."""
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase, SimpleTestCase

from apps.orgs.access import normalize_action, resolve_workspace_access
from apps.orgs.models import Company, Membership, Role
from apps.orgs.permissions import get_effective_permissions


class RolePermissionSemanticsTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="role-semantics-member")
        self.owner = get_user_model().objects.create_user(username="role-semantics-owner")
        owner_role, _ = Role.objects.get_or_create(name="Owner")
        self.role = Role.objects.create(name="ReviewDelegate")
        self.workspaces = []
        for index in range(2):
            workspace = Company.objects.create(schema_name=f"role-review-{index}",
                name=f"Role review {index}", owner=self.owner, creator=self.owner)
            Membership.objects.create(user=self.owner, company=workspace, role=owner_role)
            Membership.objects.create(user=self.actor, company=workspace, role=self.role)
            self.workspaces.append(workspace)
        self.permission, _ = Permission.objects.get_or_create(
            content_type=ContentType.objects.get_for_model(Company), codename="loan_repay",
            defaults={"name": "Repay loans"})

    def edit(self, workspace, role, codes):
        from apps.orgs.models import WorkspaceRole
        from apps.orgs.services.workspace_roles import update_workspace_role
        from apps.tenancy.context import workspace_context
        with workspace_context(workspace.pk):
            profile = WorkspaceRole.objects.get(workspace=workspace, role=role)
            return update_workspace_role(workspace=workspace, role_id=role.pk,
                permission_codes=codes, revision=profile.revision, actor=self.owner)

    def test_local_grants_do_not_change_another_workspace(self):
        first, second = self.workspaces
        self.edit(first, self.role, ["loan_repay"])
        self.assertTrue(resolve_workspace_access(actor=self.actor, workspace=first).can("loan.repay"))
        self.assertFalse(resolve_workspace_access(actor=self.actor, workspace=second).can("loan.repay"))
        self.role.permissions.add(self.permission)
        self.assertFalse(resolve_workspace_access(actor=self.actor, workspace=second).can("loan.repay"))
        self.edit(first, self.role, [])
        self.assertFalse(resolve_workspace_access(actor=self.actor, workspace=first).can("loan.repay"))

    def test_removing_admin_grant_revokes_default_and_helpers_agree(self):
        from apps.orgs.services.workspace_roles import stored_role_codes
        admin = Role.objects.get(name="Admin")
        Membership.objects.filter(user=self.actor).update(role=admin)
        first, second = self.workspaces
        self.edit(first, admin, stored_role_codes(first.pk, admin.pk) - {"loan_repay"})
        self.assertFalse(resolve_workspace_access(actor=self.actor, workspace=first).can("loan.repay"))
        self.assertTrue(resolve_workspace_access(actor=self.actor, workspace=second).can("loan.repay"))
        for workspace in self.workspaces:
            access = resolve_workspace_access(actor=self.actor, workspace=workspace)
            self.assertEqual(access.actions, frozenset(
                normalize_action(code) for code in get_effective_permissions(self.actor, workspace)))

    def test_owner_and_nonowner_edits_and_stale_revision_are_protected(self):
        from apps.orgs.services.workspace_roles import update_workspace_role
        from django.core.exceptions import PermissionDenied, ValidationError
        first = self.workspaces[0]
        with self.assertRaises(PermissionDenied):
            update_workspace_role(workspace=first, role_id=self.role.pk,
                permission_codes=[], revision=1, actor=self.actor)
        self.edit(first, self.role, ["data_view"])
        with self.assertRaises(ValidationError):
            update_workspace_role(workspace=first, role_id=self.role.pk,
                permission_codes=[], revision=1, actor=self.owner)
        with self.assertRaises(PermissionDenied):
            self.edit(first, Role.objects.get(name="Owner"), [])
        with self.assertRaises(ValidationError):
            self.edit(first, self.role, ["workspace_transfer"])

    def test_role_change_and_removal_only_change_target_membership(self):
        for workspace in self.workspaces:
            self.edit(workspace, self.role, ["loan_repay"])
        first, second = self.workspaces
        viewer = Role.objects.get(name="Viewer")
        Membership.objects.filter(user=self.actor, company=first).update(role=viewer)
        self.assertFalse(resolve_workspace_access(actor=self.actor, workspace=first).can("loan.repay"))
        self.assertTrue(resolve_workspace_access(actor=self.actor, workspace=second).can("loan.repay"))
        Membership.objects.filter(user=self.actor, company=second).delete()
        self.assertFalse(resolve_workspace_access(actor=self.actor, workspace=second).actions)

    def test_capability_based_invitation_does_not_trust_custom_role_name(self):
        from apps.orgs.services.role_policy import actor_can_grant_role
        from apps.orgs.services.workspace_roles import ensure_workspace_role
        first = self.workspaces[0]
        self.edit(first, self.role, ["team_invite", "data_view", "workspace_settings"])
        dangerous = Role.objects.create(name="Harmless sounding")
        ensure_workspace_role(first.pk, dangerous.pk)
        self.edit(first, dangerous, ["workspace_settings"])
        self.assertFalse(actor_can_grant_role(actor=self.actor, workspace=first, role=dangerous))
        viewer = Role.objects.get(name="Viewer")
        self.edit(first, viewer, ["data_view"])
        self.assertTrue(actor_can_grant_role(actor=self.actor, workspace=first, role=viewer))
        self.edit(first, viewer, ["data_view", "loan_repay"])
        self.assertFalse(actor_can_grant_role(actor=self.actor, workspace=first, role=viewer))

    def test_editor_renders_and_rejects_non_owner(self):
        from django.test import RequestFactory, override_settings
        from django.urls import reverse
        from django.core.exceptions import PermissionDenied
        from apps.orgs.views import workspace_role_permissions
        first = self.workspaces[0]
        url = reverse("workspace_role_permissions_edit", kwargs={"workspace_id": first.pk, "role_id": self.role.pk})
        request = RequestFactory().get(url)
        request.user = self.owner
        request.workspace = first
        request.session = {}
        with override_settings(STORAGES={"default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
                                       "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}):
            response = workspace_role_permissions(request, workspace_id=first.pk, role_id=self.role.pk)
        self.assertContains(response, "Save permissions")
        self.assertContains(response, "ReviewDelegate")
        from django.contrib.messages.storage.fallback import FallbackStorage
        post = RequestFactory().post(url, {"revision": 1, "actions": ["data.view"]})
        post.user, post.workspace, post.session = self.owner, first, {}
        post._messages = FallbackStorage(post)
        response = workspace_role_permissions(post, workspace_id=first.pk, role_id=self.role.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(resolve_workspace_access(actor=self.actor, workspace=first).can("data.view"))
        self.assertFalse(resolve_workspace_access(actor=self.actor, workspace=self.workspaces[1]).can("data.view"))
        request.user = self.actor
        with self.assertRaises(PermissionDenied):
            workspace_role_permissions(request, workspace_id=first.pk, role_id=self.role.pk)


class BillingManagerCompatibilityTests(SimpleTestCase):
    def test_billing_helper_retains_owner_and_membership_boundary(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        from apps.subscriptions.models import Subscription
        workspace = Company(pk=1, owner_id=7)
        subscription = Subscription(company=workspace)
        access = SimpleNamespace(platform_override=False, membership=object())
        with patch("apps.orgs.access.resolve_workspace_access", return_value=access):
            self.assertTrue(subscription.is_billing_manager(SimpleNamespace(pk=7)))
            self.assertFalse(subscription.is_billing_manager(SimpleNamespace(pk=8)))
            access.membership = None
            self.assertFalse(subscription.is_billing_manager(SimpleNamespace(pk=7)))
            access.platform_override = True
            self.assertTrue(subscription.is_billing_manager(SimpleNamespace(pk=8)))
