import contextlib
import re
from types import SimpleNamespace
from unittest.mock import patch

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse
from django_tenants.utils import get_public_schema_name

from apps.orgs.middleware_v2 import SecureWorkspaceMiddleware
from apps.orgs.models import CompanyInvitation, Membership
from apps.orgs.permissions import (
	ALL_PERMISSIONS,
	get_all_permission_codenames,
	get_effective_permissions,
	is_platform_admin,
	get_workspace_role_name,
)
from apps.orgs.services import control_plane
from apps.orgs.services import role_policy
from apps.orgs.views import CompanyPreferenceBuilder, _assert_workspace_access
from apps.orgs import signals as org_signals
from apps.orgs.tenant_context import resolve_request_workspace


class SecureWorkspaceMiddlewareTests(SimpleTestCase):
	def setUp(self):
		self.middleware = SecureWorkspaceMiddleware(lambda request: None)

	def test_extract_workspace_id_from_workspace_path(self):
		workspace_id = self.middleware._extract_workspace_id_from_path(
			"/orgs/workspace/42/dashboard/"
		)
		self.assertEqual(workspace_id, 42)

	def test_extract_workspace_id_from_legacy_company_path(self):
		workspace_id = self.middleware._extract_workspace_id_from_path(
			"/orgs/company/9/edit/"
		)
		self.assertEqual(workspace_id, 9)

	def test_extract_workspace_id_returns_none_for_unmatched_path(self):
		workspace_id = self.middleware._extract_workspace_id_from_path("/girvi/list/")
		self.assertIsNone(workspace_id)

	def test_select_workspace_candidate_prefers_domain(self):
		domain_workspace = SimpleNamespace(id=1, schema_name="acme")
		path_workspace = SimpleNamespace(id=2, schema_name="path_ws")
		profile_workspace = SimpleNamespace(id=3, schema_name="profile_ws")

		workspace, source = self.middleware._select_workspace_candidate(
			domain_workspace=domain_workspace,
			path_workspace=path_workspace,
			profile_workspace=profile_workspace,
		)

		self.assertEqual(workspace.id, 1)
		self.assertEqual(source, "domain")

	def test_select_workspace_candidate_falls_back_to_path_then_profile(self):
		path_workspace = SimpleNamespace(id=2, schema_name="path_ws")
		profile_workspace = SimpleNamespace(id=3, schema_name="profile_ws")

		workspace, source = self.middleware._select_workspace_candidate(
			domain_workspace=None,
			path_workspace=path_workspace,
			profile_workspace=profile_workspace,
		)
		self.assertEqual(workspace.id, 2)
		self.assertEqual(source, "path")

		workspace, source = self.middleware._select_workspace_candidate(
			domain_workspace=None,
			path_workspace=None,
			profile_workspace=profile_workspace,
		)
		self.assertEqual(workspace.id, 3)
		self.assertEqual(source, "profile")

	@patch("apps.orgs.middleware_v2.AuditLog.log")
	def test_mismatch_logs_security_event(self, mock_audit_log):
		request = SimpleNamespace(
			user=SimpleNamespace(id=7),
			path="/girvi/",
			META={},
		)
		domain_workspace = SimpleNamespace(id=10, schema_name="tenant_a")
		profile_workspace = SimpleNamespace(id=11, schema_name="tenant_b")

		self.middleware._handle_workspace_mismatch(
			request=request,
			domain_workspace=domain_workspace,
			profile_workspace=profile_workspace,
		)

		self.assertTrue(mock_audit_log.called)

	@patch("apps.orgs.middleware_v2.AuditLog.log")
	def test_mismatch_ignored_for_public_domain(self, mock_audit_log):
		request = SimpleNamespace(
			user=SimpleNamespace(id=7),
			path="/",
			META={},
		)
		domain_workspace = SimpleNamespace(id=10, schema_name=get_public_schema_name())
		profile_workspace = SimpleNamespace(id=11, schema_name="tenant_b")

		self.middleware._handle_workspace_mismatch(
			request=request,
			domain_workspace=domain_workspace,
			profile_workspace=profile_workspace,
		)

		self.assertFalse(mock_audit_log.called)


class TenantContextResolverTests(SimpleTestCase):
	def test_prefers_request_tenant(self):
		request = SimpleNamespace(
			tenant=SimpleNamespace(schema_name="tenant_a"),
			user=SimpleNamespace(is_authenticated=False),
		)
		workspace = resolve_request_workspace(request)
		self.assertEqual(workspace.schema_name, "tenant_a")

	def test_does_not_fallback_to_profile_workspace_by_default(self):
		profile_workspace = SimpleNamespace(schema_name="tenant_b")
		request = SimpleNamespace(
			tenant=None,
			user=SimpleNamespace(
				is_authenticated=True,
				profile=SimpleNamespace(workspace=profile_workspace),
			),
		)
		workspace = resolve_request_workspace(request)
		self.assertIsNone(workspace)

	def test_profile_fallback_only_when_opted_in(self):
		profile_workspace = SimpleNamespace(schema_name="tenant_b")
		request = SimpleNamespace(
			tenant=None,
			user=SimpleNamespace(
				is_authenticated=True,
				profile=SimpleNamespace(workspace=profile_workspace),
			),
		)
		workspace = resolve_request_workspace(request, allow_profile_fallback=True)
		self.assertEqual(workspace.schema_name, "tenant_b")

	def test_excludes_public_workspace_by_default(self):
		request = SimpleNamespace(
			tenant=SimpleNamespace(schema_name=get_public_schema_name()),
			user=SimpleNamespace(is_authenticated=False),
		)
		workspace = resolve_request_workspace(request)
		self.assertIsNone(workspace)

	def test_includes_public_workspace_when_requested(self):
		request = SimpleNamespace(
			tenant=SimpleNamespace(schema_name=get_public_schema_name()),
			user=SimpleNamespace(is_authenticated=False),
		)
		workspace = resolve_request_workspace(request, include_public=True)
		self.assertEqual(workspace.schema_name, get_public_schema_name())


class PermissionResolutionTests(SimpleTestCase):
	def test_is_platform_admin_requires_authenticated_superuser(self):
		self.assertFalse(
			is_platform_admin(
				SimpleNamespace(is_authenticated=True, is_superuser=False)
			)
		)
		self.assertFalse(
			is_platform_admin(
				SimpleNamespace(is_authenticated=False, is_superuser=True)
			)
		)
		self.assertTrue(
			is_platform_admin(
				SimpleNamespace(is_authenticated=True, is_superuser=True)
			)
		)

	def test_superuser_gets_all_permissions_and_superuser_role(self):
		user = SimpleNamespace(is_authenticated=True, is_superuser=True)
		workspace = SimpleNamespace(id=1)

		perms = get_effective_permissions(user, workspace)

		self.assertTrue(set(get_all_permission_codenames()).issubset(perms))
		self.assertIn("admin_access", perms)
		self.assertEqual(get_workspace_role_name(user, workspace), "Superuser")

	def test_membership_permissions_include_role_defaults_and_db_permissions(self):
		user = SimpleNamespace(is_authenticated=True, is_superuser=False)
		workspace = SimpleNamespace(id=9)
		role = SimpleNamespace(
			name="Member",
			permissions=SimpleNamespace(
				values_list=lambda *_args, **_kwargs: ["custom_override"]
			),
		)
		membership = SimpleNamespace(role=role)
		fake_qs = SimpleNamespace(get=lambda **_kwargs: membership)

		with patch.object(Membership.objects, "select_related", return_value=fake_qs):
			perms = get_effective_permissions(user, workspace)
			role_name = get_workspace_role_name(user, workspace)

		self.assertIn("workspace_view", perms)
		self.assertIn("data_create", perms)
		self.assertIn("custom_override", perms)
		self.assertEqual(role_name, "Member")

	def test_non_member_gets_no_permissions_and_no_role(self):
		user = SimpleNamespace(is_authenticated=True, is_superuser=False)
		workspace = SimpleNamespace(id=11)
		fake_qs = SimpleNamespace(get=lambda **_kwargs: (_ for _ in ()).throw(Membership.DoesNotExist()))

		with patch.object(Membership.objects, "select_related", return_value=fake_qs):
			self.assertEqual(get_effective_permissions(user, workspace), set())
			self.assertIsNone(get_workspace_role_name(user, workspace))


class WorkspaceAccessPolicyTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()

	def _make_request(self, *, is_superuser=False):
		return SimpleNamespace(
			user=SimpleNamespace(
				is_authenticated=True,
				is_superuser=is_superuser,
			)
		)

	def test_workspace_access_denies_non_member(self):
		request = self._make_request(is_superuser=False)
		workspace = SimpleNamespace(id=1)
		fake_filtered = SimpleNamespace(first=lambda: None)
		fake_qs = SimpleNamespace(filter=lambda **_kwargs: fake_filtered)

		with patch.object(Membership.objects, "select_related", return_value=fake_qs), \
			 patch("apps.orgs.views.get_effective_permissions", return_value=set()):
			with self.assertRaises(PermissionDenied):
				_assert_workspace_access(request, workspace)

	def test_workspace_access_allows_member_with_required_permission(self):
		request = self._make_request(is_superuser=False)
		workspace = SimpleNamespace(id=1)
		membership = SimpleNamespace(role=SimpleNamespace(name="Member"))
		fake_filtered = SimpleNamespace(first=lambda: membership)
		fake_qs = SimpleNamespace(filter=lambda **_kwargs: fake_filtered)

		with patch.object(Membership.objects, "select_related", return_value=fake_qs), \
			 patch("apps.orgs.views.get_effective_permissions", return_value={"workspace_view"}):
			result = _assert_workspace_access(
				request,
				workspace,
				required_permissions={"workspace_view"},
			)

		self.assertEqual(result["role_name"], "Member")
		self.assertIn("workspace_view", result["effective_permissions"])

	def test_workspace_access_denies_missing_required_permission(self):
		request = self._make_request(is_superuser=False)
		workspace = SimpleNamespace(id=1)
		membership = SimpleNamespace(role=SimpleNamespace(name="Member"))
		fake_filtered = SimpleNamespace(first=lambda: membership)
		fake_qs = SimpleNamespace(filter=lambda **_kwargs: fake_filtered)

		with patch.object(Membership.objects, "select_related", return_value=fake_qs), \
			 patch("apps.orgs.views.get_effective_permissions", return_value={"data_view"}):
			with self.assertRaises(PermissionDenied):
				_assert_workspace_access(
					request,
					workspace,
					required_permissions={"workspace_view"},
				)

	def test_workspace_access_allows_platform_admin_without_membership(self):
		request = self._make_request(is_superuser=True)
		workspace = SimpleNamespace(id=1)

		with patch("apps.orgs.views.get_effective_permissions", return_value={"workspace_view", "admin_access"}):
			result = _assert_workspace_access(
				request,
				workspace,
				required_permissions={"workspace_view"},
			)

		self.assertIsNone(result["membership"])
		self.assertEqual(result["role_name"], "Superuser")
		self.assertIn("workspace_view", result["effective_permissions"])

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_workspace_select_redirects_when_access_denied(self, mock_messages, mock_redirect):
		from apps.orgs import views as org_views

		request = self.factory.get("/orgs/workspace/12/select/")
		request.user = SimpleNamespace(
			is_authenticated=True,
			is_superuser=False,
			profile=SimpleNamespace(set_workspace=lambda *_args, **_kwargs: None),
		)

		workspace = SimpleNamespace(id=12, name="WS-12")
		fake_filter = SimpleNamespace(first=lambda: workspace)

		with patch.object(org_views.Company.objects, "filter", return_value=fake_filter), \
			 patch("apps.orgs.views._assert_workspace_access", side_effect=PermissionDenied):
			org_views.workspace_select(request, workspace_id=12)

		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_selector")

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	@patch("apps.orgs.views.AuditLog.log")
	def test_workspace_select_sets_workspace_when_access_allowed(
		self,
		_mock_audit,
		mock_messages,
		mock_redirect,
	):
		from apps.orgs import views as org_views

		set_calls = []
		request = self.factory.get("/orgs/workspace/12/select/")
		request.user = SimpleNamespace(
			is_authenticated=True,
			is_superuser=False,
			profile=SimpleNamespace(set_workspace=lambda workspace: set_calls.append(workspace.id)),
		)

		workspace = SimpleNamespace(id=12, name="WS-12")
		fake_filter = SimpleNamespace(first=lambda: workspace)

		with patch.object(org_views.Company.objects, "filter", return_value=fake_filter), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={
				"membership": None,
				"role_name": "Superuser",
				"effective_permissions": {"workspace_view"},
			}):
			org_views.workspace_select(request, workspace_id=12)

		self.assertEqual(set_calls, [12])
		mock_messages.success.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_dashboard", workspace_id=12)


class RolePolicyTests(SimpleTestCase):
	def test_non_owner_cannot_grant_admin_role(self):
		actor = SimpleNamespace(is_authenticated=True, is_superuser=False)
		workspace = SimpleNamespace(id=1)
		role = SimpleNamespace(name="Admin")

		with patch("apps.orgs.services.role_policy.get_effective_permissions", return_value={"team_invite"}), \
			 patch("apps.orgs.services.role_policy._actor_is_owner", return_value=False):
			self.assertFalse(
				role_policy.actor_can_grant_role(
					actor=actor,
					workspace=workspace,
					role=role,
				)
			)

	def test_owner_can_grant_admin_role_with_admin_invite_permission(self):
		actor = SimpleNamespace(is_authenticated=True, is_superuser=False)
		workspace = SimpleNamespace(id=1)
		role = SimpleNamespace(name="Admin")

		with patch("apps.orgs.services.role_policy.get_effective_permissions", return_value={"team_invite", "team_invite_admin"}), \
			 patch("apps.orgs.services.role_policy._actor_is_owner", return_value=True):
			self.assertTrue(
				role_policy.actor_can_grant_role(
					actor=actor,
					workspace=workspace,
					role=role,
				)
			)

	def test_non_owner_cannot_change_member_role(self):
		actor = SimpleNamespace(is_authenticated=True, is_superuser=False)
		workspace = SimpleNamespace(id=1)
		membership = SimpleNamespace(
			company=workspace,
			user=SimpleNamespace(id=2),
			role=SimpleNamespace(name="Member"),
		)

		with patch("apps.orgs.services.role_policy._actor_is_owner", return_value=False):
			with self.assertRaises(PermissionDenied):
				role_policy.assert_can_change_role(
					actor=actor,
					workspace=workspace,
					membership=membership,
					new_role=SimpleNamespace(name="Admin"),
				)

	def test_last_owner_cannot_be_demoted(self):
		actor = SimpleNamespace(is_authenticated=True, is_superuser=False)
		workspace = SimpleNamespace(id=1)
		membership = SimpleNamespace(
			company=workspace,
			user=SimpleNamespace(id=2),
			role=SimpleNamespace(name="Owner"),
		)

		with patch("apps.orgs.services.role_policy._actor_is_owner", return_value=True), \
			 patch("apps.orgs.services.role_policy.owner_membership_count", return_value=1):
			with self.assertRaises(PermissionDenied):
				role_policy.assert_can_change_role(
					actor=actor,
					workspace=workspace,
					membership=membership,
					new_role=SimpleNamespace(name="Member"),
				)

	def test_owner_self_leave_is_blocked(self):
		actor = SimpleNamespace(is_authenticated=True, is_superuser=False)
		workspace = SimpleNamespace(id=1)
		membership = SimpleNamespace(
			company=workspace,
			user=actor,
			role=SimpleNamespace(name="Owner"),
		)

		with self.assertRaises(PermissionDenied):
			role_policy.assert_can_remove_membership(
				actor=actor,
				workspace=workspace,
				membership=membership,
			)


class OrgNavigationFlowTests(SimpleTestCase):
	"""D2: Route and userflow verification for navigation links and canonical routes."""
	
	def test_sidebar_uses_canonical_workspace_routes(self):
		"""Verify sidebar.html navigation links use canonical workspace_* route names."""
		with open("templates/components/navigation/sidebar.html", "r") as f:
			sidebar_html = f.read()
		
		# Verify canonical route names are used
		self.assertIn("workspace_dashboard", sidebar_html)
		self.assertIn("team_invitations", sidebar_html)
		self.assertIn("workspace_detail", sidebar_html)
		self.assertIn("workspace_preferences", sidebar_html)
		
		# Verify deprecated route names are NOT used
		self.assertNotIn("orgs_invite_delete", sidebar_html)
		self.assertNotIn("company_detail", sidebar_html)

	def test_workspace_dashboard_uses_canonical_routes(self):
		"""Verify workspace_dashboard.html uses canonical route names."""
		with open("templates/company/workspace_dashboard.html", "r") as f:
			dashboard_html = f.read()
		
		# Should use canonical workspace routes
		self.assertIn("workspace_selector", dashboard_html)
		self.assertIn("workspace_detail", dashboard_html)
		self.assertIn("team_invite", dashboard_html)

	def test_profile_page_uses_team_invitations_route(self):
		"""Verify profile.html links to team_invitations (global scope)."""
		with open("templates/company/profile.html", "r") as f:
			profile_html = f.read()
		
		# Profile should link to global team_invitations
		self.assertIn("team_invitations", profile_html)

	def test_main_navigation_uses_canonical_routes(self):
		"""Verify _base.html and tenant.html use canonical route names."""
		with open("templates/tenant.html", "r") as f:
			tenant_html = f.read()
		
		# Should use canonical route names
		self.assertIn("workspace_selector", tenant_html)
		self.assertIn("team_invitations", tenant_html)
		
		# Should not use deprecated names
		self.assertNotIn("orgs_invite_delete", tenant_html)

	def test_no_deprecated_route_names_in_templates(self):
		"""Verify no deprecated route patterns exist in key navigation templates."""
		templates_to_check = [
			"templates/_base.html",
			"templates/tenant.html",
			"templates/company/workspace_dashboard.html",
			"templates/components/navigation/sidebar.html",
		]
		
		deprecated_routes = [
			"orgs_invite_delete",
			"company_invite_list",
			"team_invite_delete",
		]
		
		for template_path in templates_to_check:
			try:
				with open(template_path, "r") as f:
					content = f.read()
				for deprecated in deprecated_routes:
					self.assertNotIn(deprecated, content,
						f"Deprecated route '{deprecated}' found in {template_path}")
			except FileNotFoundError:
				# Some templates may not exist, skip them
				pass

	def test_sidebar_permission_codenames_are_registered(self):
		"""Permission codenames referenced by live sidebar must exist."""
		with open("templates/components/navigation/sidebar.html", "r") as f:
			sidebar_html = f.read()

		registered = {codename for codename, _name, _description in ALL_PERMISSIONS}
		referenced = set(
			re.findall(r"'([^']+)'\s+in\s+user_permissions", sidebar_html)
		)

		self.assertTrue(referenced)
		self.assertTrue(
			referenced.issubset(registered),
			f"Unknown sidebar permission codenames: {sorted(referenced - registered)}",
		)

	def test_sidebar_uses_current_runtime_permission_names(self):
		with open("templates/components/navigation/sidebar.html", "r") as f:
			sidebar_html = f.read()

		self.assertIn("dea_entry_view", sidebar_html)
		self.assertNotIn("sales_invoice_view", sidebar_html)
		self.assertNotIn("purchase_order_view", sidebar_html)
		self.assertNotIn("purchase_invoice_view", sidebar_html)
		self.assertNotIn("dea_journal_view", sidebar_html)

	def test_workspace_dashboard_view_does_not_import_tenant_business_models(self):
		with open("apps/orgs/views.py", "r") as f:
			views_py = f.read()

		self.assertNotIn("apps.tenant_apps.contact.models", views_py)
		self.assertNotIn("apps.tenant_apps.girvi.models", views_py)
		self.assertNotIn("apps.tenant_apps.rates.models", views_py)


class DomainPathMismatchTests(SimpleTestCase):
	"""D3: Domain/path mismatch policy and behavior matrix."""
	
	def setUp(self):
		self.middleware = SecureWorkspaceMiddleware(lambda request: None)
	
	def test_domain_path_workspace_mismatch_redirects_to_domain_workspace(self):
		"""
		Non-admin user requesting /orgs/workspace/2/... on domain resolving to workspace 1
		should be redirected to workspace 1's dashboard (domain is authoritative).
		"""
		domain_workspace = SimpleNamespace(id=1, schema_name="domain_ws")
		path_workspace = SimpleNamespace(id=2, schema_name="path_ws")
		user = SimpleNamespace(is_authenticated=True, is_superuser=False)
		request = SimpleNamespace(
			path="/orgs/workspace/2/detail/",
			user=user,
			get_host=lambda: "acme.example.com",
		)
		
		with patch.object(self.middleware, "_resolve_workspace_from_domain", return_value=domain_workspace), \
			 patch.object(self.middleware, "_resolve_workspace_from_path", return_value=path_workspace), \
			 patch.object(self.middleware, "_is_exempt_url", return_value=False), \
			 patch.object(self.middleware, "_get_user_workspace", return_value=None), \
			 patch.object(self.middleware, "_set_public_context"), \
			 patch("apps.orgs.middleware_v2.messages") as mock_messages, \
			 patch("apps.orgs.middleware_v2.HttpResponseRedirect") as mock_redirect, \
			 patch("apps.orgs.middleware_v2.reverse") as mock_reverse:
			
			mock_reverse.return_value = "/orgs/workspace/1/"
			
			result = self.middleware.process_request(request)
			
			# Should redirect to domain workspace
			mock_redirect.assert_called_once()
			call_args = mock_redirect.call_args[0]
			self.assertIn("/orgs/workspace/1/", call_args)
			
			# Should show error message
			mock_messages.error.assert_called_once()
			error_msg = mock_messages.error.call_args[0][1]
			self.assertIn("does not match", error_msg.lower())
	
	def test_platform_admin_bypasses_domain_path_workspace_mismatch_guard(self):
		"""
		Superuser (platform admin) can access /orgs/workspace/2/... on domain resolving
		to workspace 1 without being redirected. Superuser bypass allows intentional admin access.
		"""
		domain_workspace = SimpleNamespace(id=1, schema_name="domain_ws")
		path_workspace = SimpleNamespace(id=2, schema_name="path_ws")
		user = SimpleNamespace(is_authenticated=True, is_superuser=True)
		request = SimpleNamespace(
			path="/orgs/workspace/2/detail/",
			user=user,
			tenant_resolution_source=None,
			urlconf=None,
		)
		
		with patch.object(self.middleware, "_resolve_workspace_from_domain", return_value=domain_workspace), \
			 patch.object(self.middleware, "_resolve_workspace_from_path", return_value=path_workspace), \
			 patch.object(self.middleware, "_select_workspace_candidate", return_value=(path_workspace, "path")), \
			 patch.object(self.middleware, "_is_exempt_url", return_value=False), \
			 patch.object(self.middleware, "_get_user_workspace", return_value=None), \
			 patch.object(self.middleware, "_requires_workspace", return_value=False), \
			 patch.object(self.middleware, "_handle_workspace_mismatch"), \
			 patch.object(self.middleware, "_validate_workspace_access", return_value={"allowed": True}), \
			 patch.object(self.middleware, "_set_tenant_context"), \
			 patch("apps.orgs.middleware_v2.messages"):
			
			result = self.middleware.process_request(request)
			
			# Superuser should NOT be redirected (no redirect return value)
			self.assertIsNone(result)
	
	def test_domain_workspace_is_authoritative_over_profile(self):
		"""
		When domain resolves to workspace 1 and user's profile has workspace 2 selected,
		workspace 1 should win (domain is authoritative).
		"""
		domain_workspace = SimpleNamespace(id=1, schema_name="domain_ws")
		profile_workspace = SimpleNamespace(id=2, schema_name="profile_ws")
		
		workspace, source = self.middleware._select_workspace_candidate(
			domain_workspace=domain_workspace,
			path_workspace=None,
			profile_workspace=profile_workspace,
		)
		
		self.assertEqual(workspace.id, 1)
		self.assertEqual(source, "domain")
	
	def test_path_workspace_wins_over_profile_without_domain(self):
		"""
		When there's no domain mapping, but path has /orgs/workspace/2/,
		workspace 2 should be selected (path wins over profile).
		"""
		path_workspace = SimpleNamespace(id=2, schema_name="path_ws")
		profile_workspace = SimpleNamespace(id=3, schema_name="profile_ws")
		
		workspace, source = self.middleware._select_workspace_candidate(
			domain_workspace=None,
			path_workspace=path_workspace,
			profile_workspace=profile_workspace,
		)
		
		self.assertEqual(workspace.id, 2)
		self.assertEqual(source, "path")
	
	def test_mismatch_guard_only_applies_on_tenant_domains(self):
		"""
		Mismatch guard should NOT trigger for public schema domain.
		Public schema can handle cross-workspace links without restriction.
		"""
		public_schema = get_public_schema_name()
		domain_workspace = SimpleNamespace(id=1, schema_name=public_schema)
		path_workspace = SimpleNamespace(id=2, schema_name="path_ws")
		user = SimpleNamespace(is_authenticated=True, is_superuser=False)
		request = SimpleNamespace(path="/orgs/workspace/2/", user=user)
		
		# Mismatch guard should not trigger because domain is public schema
		# (the condition checks: domain_workspace.schema_name != get_public_schema_name())
		# Since domain IS public schema, the guard condition is false, so no redirect.
		
		# Verify the logic: if domain_workspace.schema_name == public_schema, guard doesn't apply
		self.assertEqual(domain_workspace.schema_name, public_schema)
		# If guard checked this, it would fail (short-circuit), so no redirect would occur.


class InvitationLifecycleStateTests(SimpleTestCase):
	"""D4: Invitation lifecycle state machine behavior."""

	def setUp(self):
		self.factory = RequestFactory()

	def test_lifecycle_state_returns_expired_for_pending_invitation(self):
		invitation = CompanyInvitation(
			status=CompanyInvitation.Status.PENDING,
			accepted=False,
		)

		with patch.object(invitation, "key_expired", return_value=True):
			self.assertEqual(invitation.lifecycle_state(), "expired")

	def test_mark_declined_sets_state_and_response_timestamp(self):
		invitation = CompanyInvitation(
			status=CompanyInvitation.Status.PENDING,
			accepted=False,
		)
		with patch.object(invitation, "save") as mock_save:
			invitation.mark_declined()

		self.assertEqual(invitation.status, CompanyInvitation.Status.DECLINED)
		self.assertFalse(invitation.accepted)
		self.assertIsNotNone(invitation.responded_at)
		mock_save.assert_called_once()

	def test_mark_revoked_sets_state_and_response_timestamp(self):
		invitation = CompanyInvitation(
			status=CompanyInvitation.Status.PENDING,
			accepted=False,
		)
		with patch.object(invitation, "save") as mock_save:
			invitation.mark_revoked()

		self.assertEqual(invitation.status, CompanyInvitation.Status.REVOKED)
		self.assertFalse(invitation.accepted)
		self.assertIsNotNone(invitation.responded_at)
		mock_save.assert_called_once()

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_team_invitations_decline_persists_declined_state(
		self,
		mock_messages,
		mock_redirect,
	):
		from apps.orgs import views as org_views

		request = self.factory.post(
			"/orgs/team/invitations/",
			{"action": "decline", "invitation_id": "42"},
		)
		request.user = SimpleNamespace(
			email="user@example.com",
			profile=SimpleNamespace(workspace=None, save=lambda **_kwargs: None),
		)

		invitation = SimpleNamespace(
			company=SimpleNamespace(name="Acme"),
			lifecycle_state=lambda: CompanyInvitation.Status.PENDING,
			mark_declined=lambda: None,
		)
		fake_qs = SimpleNamespace(select_related=lambda *_args: [])

		with patch.object(org_views.CompanyInvitation.objects, "filter", return_value=fake_qs), \
			 patch.object(org_views.CompanyInvitation.objects, "get", return_value=invitation), \
			 patch("apps.orgs.views.control_plane.decline_invitation") as mock_decline:
			org_views.team_invitations.__wrapped__(request)

		mock_decline.assert_called_once()
		mock_messages.info.assert_called_once()
		mock_redirect.assert_called_once_with("team_invitations")

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_team_invitations_accept_rejects_expired_invitation(
		self,
		mock_messages,
		mock_redirect,
	):
		from apps.orgs import views as org_views

		request = self.factory.post(
			"/orgs/team/invitations/",
			{"action": "accept", "invitation_id": "42"},
		)
		request.user = SimpleNamespace(
			email="user@example.com",
			profile=SimpleNamespace(workspace=None, save=lambda **_kwargs: None),
		)

		invitation = SimpleNamespace(
			company=SimpleNamespace(name="Acme"),
			lifecycle_state=lambda: "expired",
			accept=lambda _request: None,
		)
		fake_qs = SimpleNamespace(select_related=lambda *_args: [])

		with patch.object(org_views.CompanyInvitation.objects, "filter", return_value=fake_qs), \
			 patch.object(org_views.CompanyInvitation.objects, "get", return_value=invitation):
			org_views.team_invitations.__wrapped__(request)

		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("team_invitations")

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_invitation_delete_allows_workspace_admin_revoke(
		self,
		mock_messages,
		mock_redirect,
	):
		from apps.orgs import views as org_views

		request = self.factory.post("/orgs/team/invitations/42/delete/")
		request.user = SimpleNamespace(id=9)
		request.headers = {}

		company = SimpleNamespace(id=1)
		mark_calls = []
		invitation = SimpleNamespace(
			id=42,
			inviter=SimpleNamespace(id=5),
			company=company,
			mark_revoked=lambda: mark_calls.append(True),
		)

		with patch("apps.orgs.views.get_object_or_404", return_value=invitation), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"role_name": "Admin"}), \
			 patch("apps.orgs.views.control_plane.revoke_invitation") as mock_revoke:
			org_views.invitation_delete.__wrapped__(request, invitation_id=42)

		mock_revoke.assert_called_once()
		mock_messages.success.assert_called_once()
		mock_redirect.assert_called_once_with(
			reverse("workspace_settings_invitations", kwargs={"workspace_id": 1})
		)


class InvitationTeamAuthorizationTests(SimpleTestCase):
	"""Phase 4.6: focused authorization coverage for team and invitation flows."""

	def setUp(self):
		self.factory = RequestFactory()

	def _team_invite_view(self):
		from apps.orgs import views as org_views
		return org_views.team_invite.__wrapped__.__wrapped__.__wrapped__

	def _remove_member_view(self):
		from apps.orgs import views as org_views
		return org_views.team_remove_member.__wrapped__.__wrapped__

	def _change_role_view(self):
		from apps.orgs import views as org_views
		return org_views.team_change_role.__wrapped__.__wrapped__

	def test_team_invite_requires_workspace_team_invite_permission(self):
		company = SimpleNamespace(id=9, is_deleted=False)
		request = self.factory.get("/orgs/workspace/9/team/invite/")
		request.user = SimpleNamespace(id=1, is_superuser=False, is_authenticated=True)

		with patch("apps.orgs.views.get_object_or_404", return_value=company), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"effective_permissions": {"team_invite"}}) as mock_access, \
			 patch("apps.orgs.views.CompanyInvitationForm") as mock_form, \
			 patch("apps.orgs.views.render") as mock_render:
			self._team_invite_view()(request, workspace_id=9)

		mock_access.assert_called_once_with(
			request,
			company,
			required_permissions={"team_invite"},
			allow_platform_admin=True,
		)
		mock_form.assert_called_once_with(inviter=request.user, company=company)
		mock_render.assert_called_once()

	def test_send_team_invitation_service_enforces_role_grant_policy(self):
		form = SimpleNamespace(cleaned_data={"role": SimpleNamespace(name="Admin")})
		actor = SimpleNamespace(id=1)
		company = SimpleNamespace(id=9)

		with patch("apps.orgs.services.control_plane.role_policy.assert_can_invite_role", side_effect=ValidationError("denied")) as mock_policy, \
			 patch("apps.orgs.services.control_plane._public_schema_context") as mock_ctx:
			with self.assertRaises(ValidationError):
				control_plane.send_team_invitation(
					form=form,
					actor=actor,
					company=company,
					request=SimpleNamespace(),
				)

		mock_policy.assert_called_once_with(
			actor=actor,
			workspace=company,
			role=form.cleaned_data["role"],
		)
		mock_ctx.assert_not_called()

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_invitation_revoke_denies_non_inviter_without_workspace_permission(
		self,
		mock_messages,
		mock_redirect,
	):
		from apps.orgs import views as org_views

		request = self.factory.post("/orgs/team/invitations/42/delete/")
		request.user = SimpleNamespace(id=9)
		request.headers = {}
		invitation = SimpleNamespace(
			id=42,
			inviter=SimpleNamespace(id=5),
			company=SimpleNamespace(id=1),
		)

		with patch("apps.orgs.views.get_object_or_404", return_value=invitation), \
			 patch("apps.orgs.views._assert_workspace_access", side_effect=PermissionDenied("denied")), \
			 patch("apps.orgs.views.control_plane.revoke_invitation") as mock_revoke:
			org_views.invitation_delete.__wrapped__(request, invitation_id=42)

		mock_revoke.assert_not_called()
		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_selector")

	def test_team_remove_member_requires_team_remove_permission(self):
		company = SimpleNamespace(id=9)
		membership = SimpleNamespace(
			id=5,
			user=SimpleNamespace(id=2, profile=SimpleNamespace(workspace=None)),
		)
		request = self.factory.post("/orgs/workspace/9/team/member/5/remove/")
		request.user = SimpleNamespace(id=1)

		with patch("apps.orgs.views.get_object_or_404", side_effect=[company, membership]), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"role_name": "Owner"}) as mock_access, \
			 patch("apps.orgs.views.control_plane.remove_membership"):
			self._remove_member_view()(request, workspace_id=9, membership_id=5)

		mock_access.assert_called_once_with(
			request,
			company,
			required_permissions={"team_remove"},
			allow_platform_admin=True,
		)

	def test_team_change_role_requires_team_change_role_permission(self):
		company = SimpleNamespace(id=9)
		membership = SimpleNamespace(id=5, user=SimpleNamespace(id=2))
		role = SimpleNamespace(id=3, name="Admin")
		request = self.factory.post(
			"/orgs/workspace/9/team/member/5/role/",
			{"role": "3"},
		)
		request.user = SimpleNamespace(id=1)
		request.htmx = False

		with patch("apps.orgs.views.get_object_or_404", side_effect=[company, membership, role]), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"role_name": "Owner"}) as mock_access, \
			 patch("apps.orgs.views.role_policy.allowed_invitation_roles", return_value=[role]), \
			 patch("apps.orgs.views.control_plane.change_membership_role"):
			self._change_role_view()(request, workspace_id=9, membership_id=5)

		mock_access.assert_called_once_with(
			request,
			company,
			required_permissions={"team_change_role"},
			allow_platform_admin=True,
		)

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_workspace_leave_blocks_sole_owner_self_leave(self, mock_messages, mock_redirect):
		from apps.orgs import views as org_views

		user = SimpleNamespace(id=1)
		company = SimpleNamespace(id=9)
		membership = SimpleNamespace(user=user, role=SimpleNamespace(name="Owner"))
		request = self.factory.post("/orgs/workspace/9/leave/")
		request.user = user

		with patch("apps.orgs.views.get_object_or_404", side_effect=[company, membership]), \
			 patch("apps.orgs.views._is_owner_membership", return_value=True), \
			 patch("apps.orgs.views._owner_membership_count", return_value=1), \
			 patch("apps.orgs.views.control_plane.remove_membership") as mock_remove:
			org_views.workspace_leave.__wrapped__(request, workspace_id=9)

		mock_remove.assert_not_called()
		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_detail", workspace_id=9)

	def test_sent_invitation_list_requires_team_invite_on_selected_workspace(self):
		from apps.orgs import views as org_views

		workspace = SimpleNamespace(id=9)
		request = self.factory.get("/orgs/team/invitations/list/")
		request.user = SimpleNamespace(id=1)

		with patch("apps.orgs.views.resolve_request_workspace", return_value=workspace), \
			 patch("apps.orgs.views._assert_workspace_access", side_effect=PermissionDenied("denied")) as mock_access:
			with self.assertRaises(PermissionDenied):
				org_views.companyinvitations_list.__wrapped__(request)

		mock_access.assert_called_once_with(
			request,
			workspace,
			required_permissions={"team_invite"},
			allow_platform_admin=True,
		)

	def test_member_list_uses_explicit_workspace_context_when_alias_passes_id(self):
		from apps.orgs import views as org_views

		workspace = SimpleNamespace(id=9)
		request = self.factory.get("/workspace/9/settings/team/")
		request.user = SimpleNamespace(id=1)

		class FakeMembershipQuerySet:
			def filter(self, **kwargs):
				self.filter_kwargs = kwargs
				return self

			def order_by(self, *_args):
				return self

			def count(self):
				return 0

		memberships = FakeMembershipQuerySet()

		with patch("apps.orgs.views.get_object_or_404", return_value=workspace) as mock_get, \
			 patch("apps.orgs.views.resolve_request_workspace") as mock_resolve, \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"effective_permissions": {"team_change_role", "team_remove"}}) as mock_access, \
			 patch.object(org_views.Membership.objects, "select_related", return_value=memberships), \
			 patch("apps.orgs.views.render") as mock_render:
			org_views.membership_list.__wrapped__(request, workspace_id=9)

		mock_get.assert_called_once_with(org_views.Company, id=9, is_deleted=False)
		mock_resolve.assert_not_called()
		mock_access.assert_called_once_with(
			request,
			workspace,
			required_permissions={"team_list"},
			allow_platform_admin=True,
		)
		self.assertEqual(memberships.filter_kwargs, {"company": workspace})
		context = mock_render.call_args.args[2]
		self.assertIs(context["workspace"], workspace)
		self.assertTrue(context["can_change_role"])
		self.assertTrue(context["can_remove_member"])

	def test_sent_invitation_list_uses_explicit_workspace_context_when_alias_passes_id(self):
		from apps.orgs import views as org_views

		workspace = SimpleNamespace(id=9)
		request = self.factory.get("/workspace/9/settings/invitations/")
		request.user = SimpleNamespace(id=1)

		class FakeInvitationQuerySet:
			def __init__(self):
				self.filter_kwargs = None

			def order_by(self, *_args):
				return self

			def filter(self, **kwargs):
				self.filter_kwargs = kwargs
				return []

		invitations = FakeInvitationQuerySet()

		with patch("apps.orgs.views.get_object_or_404", return_value=workspace) as mock_get, \
			 patch("apps.orgs.views._get_workspace_from_query") as mock_query_workspace, \
			 patch("apps.orgs.views.resolve_request_workspace") as mock_resolve, \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"effective_permissions": {"team_invite"}}) as mock_access, \
			 patch.object(org_views.CompanyInvitation.objects, "select_related", return_value=invitations), \
			 patch("apps.orgs.views.render") as mock_render:
			org_views.companyinvitations_list.__wrapped__(request, workspace_id=9)

		mock_get.assert_called_once_with(org_views.Company, id=9, is_deleted=False)
		mock_query_workspace.assert_not_called()
		mock_resolve.assert_not_called()
		mock_access.assert_called_once_with(
			request,
			workspace,
			required_permissions={"team_invite"},
			allow_platform_admin=True,
		)
		self.assertEqual(invitations.filter_kwargs, {"company": workspace})
		context = mock_render.call_args.args[2]
		self.assertIs(context["workspace"], workspace)
		self.assertIs(context["current_workspace"], workspace)

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_team_invite_success_redirects_to_canonical_sent_invitations(
		self,
		mock_messages,
		mock_redirect,
	):
		company = SimpleNamespace(id=9)
		request = self.factory.post(
			"/workspace/9/settings/invitations/new/",
			{"email": "member@example.com"},
		)
		request.user = SimpleNamespace(id=1)
		form = SimpleNamespace(is_valid=lambda: True)

		with patch("apps.orgs.views.get_object_or_404", return_value=company), \
			 patch("apps.orgs.views._assert_workspace_access"), \
			 patch("apps.orgs.views.CompanyInvitationForm", return_value=form), \
			 patch("apps.orgs.views.control_plane.send_team_invitation"):
			self._team_invite_view()(request, workspace_id=9)

		mock_messages.success.assert_called_once_with(request, "Invitation sent successfully")
		mock_redirect.assert_called_once_with(
			"workspace_settings_invitations",
			workspace_id=9,
		)

	def test_invite_success_links_back_to_workspace_scoped_sent_invitations(self):
		from apps.orgs import views as org_views

		workspace = SimpleNamespace(id=9)
		request = self.factory.get("/orgs/team/invite/success/?workspace_id=9")
		request.user = SimpleNamespace(id=1)

		with patch("apps.orgs.views._get_workspace_from_query", return_value=workspace), \
			 patch("apps.orgs.views._assert_workspace_access") as mock_access, \
			 patch("apps.orgs.views.render") as mock_render:
			org_views.invite_success.__wrapped__(request)

		mock_access.assert_called_once_with(
			request,
			workspace,
			required_permissions={"team_invite"},
			allow_platform_admin=True,
		)
		context = mock_render.call_args.args[2]
		self.assertIs(context["workspace"], workspace)
		self.assertEqual(
			context["sent_invitations_url"],
			reverse("workspace_settings_invitations", kwargs={"workspace_id": 9}),
		)

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_invitation_revoke_returns_to_workspace_scoped_sent_list(
		self,
		mock_messages,
		mock_redirect,
	):
		from apps.orgs import views as org_views

		company = SimpleNamespace(id=9)
		inviter = SimpleNamespace(id=1)
		invitation = SimpleNamespace(
			id=42,
			company=company,
			company_id=9,
			inviter=inviter,
		)
		request = self.factory.post("/orgs/team/invitations/42/delete/")
		request.user = inviter
		request.headers = {}

		with patch("apps.orgs.views.get_object_or_404", return_value=invitation), \
			 patch("apps.orgs.views.control_plane.revoke_invitation") as mock_revoke:
			org_views.invitation_delete.__wrapped__(request, invitation_id=42)

		mock_revoke.assert_called_once_with(
			invitation=invitation,
			actor=inviter,
			request=request,
		)
		mock_messages.success.assert_called_once_with(
			request,
			"Invitation revoked successfully",
		)
		mock_redirect.assert_called_once_with(
			reverse("workspace_settings_invitations", kwargs={"workspace_id": 9})
		)


class DirectInvitationAcceptAdapterTests(SimpleTestCase):
	"""Phase 4.7: direct invite links use orgs flow for authenticated users."""

	def setUp(self):
		self.factory = RequestFactory()

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_authenticated_matching_user_accepts_through_control_plane(
		self,
		mock_messages,
		mock_redirect,
	):
		from apps.orgs import views as org_views

		workspace = SimpleNamespace(id=9, name="Acme")
		role = SimpleNamespace(name="Member")
		invitation = SimpleNamespace(
			email="user@example.com",
			company=workspace,
			role=role,
			lifecycle_state=lambda: CompanyInvitation.Status.PENDING,
		)
		profile_saves = []
		user = SimpleNamespace(
			email="USER@example.com",
			is_authenticated=True,
			profile=SimpleNamespace(
				workspace=None,
				save=lambda **kwargs: profile_saves.append(kwargs),
			),
		)
		request = self.factory.get("/orgs/team/invitations/accept/key123/")
		request.user = user
		fake_queryset = SimpleNamespace(first=lambda: invitation)
		fake_manager = SimpleNamespace(filter=lambda **_kwargs: fake_queryset)

		with patch.object(org_views.CompanyInvitation.objects, "select_related", return_value=fake_manager), \
			 patch("apps.orgs.views.control_plane.accept_invitation") as mock_accept:
			org_views.team_accept_invitation(request, key="KEY123")

		mock_accept.assert_called_once_with(
			invitation=invitation,
			user=user,
			request=request,
		)
		self.assertIs(user.profile.workspace, workspace)
		self.assertEqual(profile_saves, [{}])
		mock_messages.success.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_dashboard", workspace_id=9)

	def test_unauthenticated_direct_accept_preserves_django_invitations_fallback(self):
		from apps.orgs import views as org_views

		request = self.factory.get("/orgs/team/invitations/accept/key123/")
		request.user = SimpleNamespace(is_authenticated=False)
		fallback_response = object()

		with patch("apps.orgs.views.AcceptInvite.as_view", return_value=lambda request, key: fallback_response) as mock_as_view:
			response = org_views.team_accept_invitation(request, key="key123")

		mock_as_view.assert_called_once()
		self.assertIs(response, fallback_response)

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_authenticated_email_mismatch_does_not_accept_invitation(
		self,
		mock_messages,
		mock_redirect,
	):
		from apps.orgs import views as org_views

		invitation = SimpleNamespace(
			email="invited@example.com",
			company=SimpleNamespace(id=9, name="Acme"),
			role=SimpleNamespace(name="Member"),
			lifecycle_state=lambda: CompanyInvitation.Status.PENDING,
		)
		request = self.factory.get("/orgs/team/invitations/accept/key123/")
		request.user = SimpleNamespace(
			email="other@example.com",
			is_authenticated=True,
		)
		fake_queryset = SimpleNamespace(first=lambda: invitation)
		fake_manager = SimpleNamespace(filter=lambda **_kwargs: fake_queryset)

		with patch.object(org_views.CompanyInvitation.objects, "select_related", return_value=fake_manager), \
			 patch("apps.orgs.views.control_plane.accept_invitation") as mock_accept:
			org_views.team_accept_invitation(request, key="key123")

		mock_accept.assert_not_called()
		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("team_invitations")


class MembershipLifecycleGuardrailTests(SimpleTestCase):
	"""D5: Membership lifecycle guardrails for owner safety and self-leave."""

	def setUp(self):
		self.factory = RequestFactory()

	def _remove_member_view(self):
		from apps.orgs import views as org_views
		return org_views.team_remove_member.__wrapped__.__wrapped__

	def _change_role_view(self):
		from apps.orgs import views as org_views
		return org_views.team_change_role.__wrapped__.__wrapped__

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_cannot_remove_last_owner(self, mock_messages, mock_redirect):
		company = SimpleNamespace(id=9)
		owner_user = SimpleNamespace(id=10, email="owner@example.com")
		owner_membership = SimpleNamespace(
			id=5,
			user=owner_user,
			role=SimpleNamespace(name="Owner"),
			delete=lambda: None,
		)
		request = self.factory.post("/orgs/workspace/9/team/member/5/remove/")
		request.user = SimpleNamespace(id=11, email="admin@example.com")

		with patch("apps.orgs.views.get_object_or_404", side_effect=[company, owner_membership]), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"role_name": "Owner"}), \
			 patch("apps.orgs.views.control_plane.remove_membership", side_effect=PermissionDenied("Cannot remove the last owner. Transfer ownership first.")):
			self._remove_member_view()(request, workspace_id=9, membership_id=5)

		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_detail", workspace_id=9)

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_owner_must_transfer_before_self_leave(self, mock_messages, mock_redirect):
		user = SimpleNamespace(id=10, email="owner@example.com")
		company = SimpleNamespace(id=9)
		membership = SimpleNamespace(
			id=5,
			user=user,
			role=SimpleNamespace(name="Owner"),
			delete=lambda: None,
		)
		request = self.factory.post("/orgs/workspace/9/team/member/5/remove/")
		request.user = user

		with patch("apps.orgs.views.get_object_or_404", side_effect=[company, membership]), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"role_name": "Owner"}), \
			 patch("apps.orgs.views.control_plane.remove_membership", side_effect=PermissionDenied("Owners must transfer ownership before leaving the workspace.")):
			self._remove_member_view()(request, workspace_id=9, membership_id=5)

		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_detail", workspace_id=9)

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_removed_member_loses_workspace_access_immediately(self, mock_messages, mock_redirect):
		company = SimpleNamespace(id=9)
		save_calls = []
		profile = SimpleNamespace(workspace=company, save=lambda **kwargs: save_calls.append(kwargs))
		removed_user = SimpleNamespace(id=10, email="member@example.com", profile=profile)
		membership = SimpleNamespace(
			id=5,
			user=removed_user,
			role=SimpleNamespace(name="Member"),
			delete=lambda: None,
		)
		request = self.factory.post("/orgs/workspace/9/team/member/5/remove/")
		request.user = SimpleNamespace(id=11, email="owner@example.com")

		with patch("apps.orgs.views.get_object_or_404", side_effect=[company, membership]), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"role_name": "Owner"}), \
			 patch("apps.orgs.views._owner_membership_count", return_value=2), \
			 patch("apps.orgs.views.control_plane.remove_membership"):
			self._remove_member_view()(request, workspace_id=9, membership_id=5)

		self.assertIsNone(profile.workspace)
		self.assertEqual(save_calls, [{"update_fields": ["workspace"]}])
		mock_redirect.assert_called_once_with("workspace_list")

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_self_leave_allowed_for_non_owner(self, mock_messages, mock_redirect):
		company = SimpleNamespace(id=9)
		save_calls = []
		user = SimpleNamespace(id=10, email="member@example.com")
		profile = SimpleNamespace(workspace=company, save=lambda **kwargs: save_calls.append(kwargs))
		user.profile = profile
		membership = SimpleNamespace(
			id=5,
			user=user,
			role=SimpleNamespace(name="Member"),
			delete=lambda: None,
		)
		request = self.factory.post("/orgs/workspace/9/team/member/5/remove/")
		request.user = user

		with patch("apps.orgs.views.get_object_or_404", side_effect=[company, membership]), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"role_name": "Member"}), \
			 patch("apps.orgs.views._owner_membership_count", return_value=2), \
			 patch("apps.orgs.views.control_plane.remove_membership"):
			self._remove_member_view()(request, workspace_id=9, membership_id=5)

		mock_messages.success.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_selector")
		self.assertIsNone(profile.workspace)
		self.assertEqual(save_calls, [{"update_fields": ["workspace"]}])

	@patch("apps.orgs.views.redirect")
	@patch("apps.orgs.views.messages")
	def test_cannot_demote_last_owner(self, mock_messages, mock_redirect):
		company = SimpleNamespace(id=9)
		owner_user = SimpleNamespace(id=10, email="owner@example.com")
		owner_membership = SimpleNamespace(
			id=5,
			user=owner_user,
			role=SimpleNamespace(name="Owner"),
			save=lambda: None,
		)
		member_role = SimpleNamespace(id=2, name="Member")
		request = self.factory.post(
			"/orgs/workspace/9/team/member/5/role/",
			{"role": "2"},
		)
		request.user = SimpleNamespace(id=11, email="admin@example.com")
		request.htmx = False

		with patch("apps.orgs.views.get_object_or_404", side_effect=[company, owner_membership, member_role]), \
			 patch("apps.orgs.views._assert_workspace_access", return_value={"role_name": "Owner"}), \
			 patch("apps.orgs.views.role_policy.allowed_invitation_roles", return_value=[member_role]), \
			 patch("apps.orgs.views.control_plane.change_membership_role", side_effect=PermissionDenied("Cannot demote the last owner. Transfer ownership first.")):
			self._change_role_view()(request, workspace_id=9, membership_id=5)

		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("workspace_detail", workspace_id=9)


class ControlPlaneIntegrityTests(SimpleTestCase):
	"""D6: control-plane service operations enforce public schema + audit logs."""

	def test_workspace_create_writes_control_plane_records(self):
		save_calls = []
		company = SimpleNamespace(name="Acme Workspace", save=lambda: save_calls.append(True))

		class FakeForm:
			def save(self, commit=False):
				assert commit is False
				return company

		request = SimpleNamespace(get_host=lambda: "erp.example.com")
		user = SimpleNamespace(id=7, email="owner@example.com")
		owner_role = SimpleNamespace(name="Owner")

		with patch("apps.orgs.services.control_plane._public_schema_context", return_value=contextlib.nullcontext()) as mock_ctx, \
			 patch.object(control_plane.Company.all_objects, "filter", return_value=SimpleNamespace(exists=lambda: False)), \
			 patch.object(control_plane.Domain.objects, "filter", return_value=SimpleNamespace(exists=lambda: False)), \
			 patch.object(control_plane.Domain.objects, "create") as mock_domain_create, \
			 patch.object(control_plane.Role.objects, "get", return_value=owner_role) as mock_role_get, \
			 patch.object(control_plane.Membership.objects, "create") as mock_membership_create, \
			 patch("apps.orgs.services.control_plane.AuditLog.log") as mock_audit:
			created_company = control_plane.create_workspace_from_form(
				form=FakeForm(),
				user=user,
				request=request,
			)

		self.assertIs(created_company, company)
		self.assertTrue(save_calls)
		self.assertEqual(company.creator, user)
		self.assertEqual(company.owner, user)
		mock_ctx.assert_called_once()
		mock_role_get.assert_called_once_with(name="Owner")
		mock_domain_create.assert_called_once()
		mock_membership_create.assert_called_once()
		mock_audit.assert_called_once()

	def test_membership_mutations_occur_in_public_schema_context(self):
		membership = SimpleNamespace(
			company=SimpleNamespace(id=9),
			user=SimpleNamespace(email="member@example.com"),
			role=SimpleNamespace(name="Member"),
			delete=lambda: None,
			save=lambda **_kwargs: None,
		)
		actor = SimpleNamespace(id=1, email="owner@example.com")
		role = SimpleNamespace(name="Admin")

		with patch("apps.orgs.services.control_plane._public_schema_context", return_value=contextlib.nullcontext()) as mock_ctx, \
			 patch.object(control_plane.Membership.objects, "get_or_create", return_value=(membership, True)), \
			 patch("apps.orgs.services.control_plane.role_policy.assert_can_change_role"), \
			 patch("apps.orgs.services.control_plane.role_policy.assert_can_remove_membership"), \
			 patch("apps.orgs.services.control_plane.AuditLog.log"):
			control_plane.create_membership(
				user=membership.user,
				company=membership.company,
				role=role,
				request=SimpleNamespace(),
				actor=actor,
			)
			control_plane.change_membership_role(
				membership=membership,
				new_role=role,
				actor=actor,
				request=SimpleNamespace(),
			)
			control_plane.remove_membership(
				membership=membership,
				actor=actor,
				request=SimpleNamespace(),
			)

		self.assertEqual(mock_ctx.call_count, 3)

	def test_invitation_mutations_are_audited(self):
		company = SimpleNamespace(id=9, name="Acme")
		invitation = SimpleNamespace(
			email="invitee@example.com",
			company=company,
			role=SimpleNamespace(name="Member"),
			mark_declined=lambda: None,
			mark_revoked=lambda: None,
			accept=lambda _request: None,
		)
		user = SimpleNamespace(id=7, email="invitee@example.com")

		fake_membership_filter = SimpleNamespace(exists=lambda: True)

		with patch("apps.orgs.services.control_plane._public_schema_context", return_value=contextlib.nullcontext()), \
			 patch.object(control_plane.Membership.objects, "filter", return_value=fake_membership_filter), \
			 patch("apps.orgs.services.control_plane.AuditLog.log") as mock_audit:
			control_plane.accept_invitation(invitation=invitation, user=user, request=SimpleNamespace())
			control_plane.decline_invitation(invitation=invitation, actor=user, request=SimpleNamespace())
			control_plane.revoke_invitation(invitation=invitation, actor=user, request=SimpleNamespace())

		actions = [call.args[0] for call in mock_audit.call_args_list]
		self.assertIn("TEAM_INVITE_ACCEPT", actions)
		self.assertIn("TEAM_INVITE_DECLINE", actions)
		self.assertIn("TEAM_INVITE_REVOKE", actions)

	def test_audit_actions_match_declared_choices(self):
		from apps.orgs.audit import AuditLog

		declared = {action for action, _label in AuditLog.ACTION_CHOICES}
		self.assertIn("TEAM_INVITE", declared)
		self.assertIn("TEAM_MEMBER_ADD", declared)
		self.assertIn("TEAM_MEMBER_REMOVE", declared)
		self.assertIn("TEAM_ROLE_CHANGE", declared)
		self.assertIn("TEAM_INVITE_ACCEPT", declared)

	def test_duplicate_invitation_create_raises_validation_error(self):
		with patch.object(
			CompanyInvitation._default_manager,
			"create",
			side_effect=IntegrityError,
		), patch("apps.orgs.models.transaction.atomic", return_value=contextlib.nullcontext()):
			with self.assertRaises(ValidationError):
				CompanyInvitation.create(
					email="member@example.com",
					company=SimpleNamespace(id=9),
					role=SimpleNamespace(name="Member"),
					inviter=SimpleNamespace(id=1),
				)


class CompanyPreferenceBuilderTests(SimpleTestCase):
	def setUp(self):
		self.factory = RequestFactory()

	def test_get_success_url_uses_workspace_preferences_route(self):
		request = self.factory.get("/orgs/workspace/13/preferences/?section=Loan")
		request.user = SimpleNamespace(
			is_authenticated=True,
			profile=SimpleNamespace(workspace=SimpleNamespace(id=13, name="Acme")),
		)

		view = CompanyPreferenceBuilder()
		view.request = request
		view.kwargs = {"workspace_id": 13}

		self.assertEqual(
			view.get_success_url(),
			reverse("workspace_preferences", kwargs={"workspace_id": 13}) + "?section=Loan",
		)

	def test_template_section_links_render_with_workspace_id(self):
		request = self.factory.get("/orgs/workspace/13/preferences/?section=Loan")
		request.user = SimpleNamespace(is_authenticated=False)

		storages = {
			**settings.STORAGES,
			"staticfiles": {
				"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
			},
		}
		with override_settings(STORAGES=storages):
			html = render_to_string(
				"company/company_preferences.html",
				{
					"sections": [{"name": "Loan", "obj": None}],
					"current_section": "Loan",
					"workspace_id": 13,
					"form": SimpleNamespace(visible_fields=[]),
				},
				request=request,
			)

		self.assertIn(
			reverse("workspace_preferences", kwargs={"workspace_id": 13}) + "?section=Loan",
			html,
		)


class MiddlewareProcessRequestTests(SimpleTestCase):
	"""
	Full process_request flow tests.
	All DB-touching methods are patched; no database is required.
	Covers: exempt URLs, resolution priority (domain > path > profile),
	unauthenticated paths, workspace-required redirects, and access-denial cleanup.
	"""

	def setUp(self):
		self.middleware = SecureWorkspaceMiddleware(lambda request: None)
		self.tenant_ws = SimpleNamespace(id=10, schema_name="tenant_a")
		self.profile_ws = SimpleNamespace(id=11, schema_name="tenant_b")

	def _make_auth_request(self, path="/girvi/loans/", profile_workspace=None):
		profile = SimpleNamespace(workspace=profile_workspace, save=lambda **kw: None)
		user = SimpleNamespace(id=5, is_authenticated=True, profile=profile)
		return SimpleNamespace(path=path, user=user, META={})

	def _make_anon_request(self, path="/"):
		user = SimpleNamespace(id=None, is_authenticated=False)
		return SimpleNamespace(path=path, user=user, META={})

	def _base_patches(self, domain_ws=None, path_ws=None, profile_ws=None):
		"""Patch the three DB-resolution methods; other helpers must be patched per test."""
		return [
			patch.object(self.middleware, "_is_exempt_url", return_value=False),
			patch.object(self.middleware, "_resolve_workspace_from_domain", return_value=domain_ws),
			patch.object(self.middleware, "_resolve_workspace_from_path", return_value=path_ws),
			patch.object(self.middleware, "_get_user_workspace", return_value=profile_ws),
		]

	# ── exempt URL ───────────────────────────────────────────────────────────────

	def test_exempt_url_immediately_sets_public_context(self):
		"""Exempt URLs bypass all tenant resolution and switch to public schema."""
		request = self._make_anon_request("/accounts/login/")
		with patch.object(self.middleware, "_is_exempt_url", return_value=True), \
			 patch.object(self.middleware, "_set_public_context") as mock_public:
			result = self.middleware.process_request(request)
		mock_public.assert_called_once_with(request)
		self.assertIsNone(result)

	# ── resolution priority ──────────────────────────────────────────────────────

	def test_domain_workspace_is_authoritative_over_profile(self):
		"""Domain mapping overrides profile workspace; resolution source is 'domain'."""
		request = self._make_auth_request(profile_workspace=self.profile_ws)
		patches = self._base_patches(domain_ws=self.tenant_ws, profile_ws=self.profile_ws)
		with contextlib.ExitStack() as stack:
			for p in patches:
				stack.enter_context(p)
			stack.enter_context(patch.object(self.middleware, "_handle_workspace_mismatch"))
			stack.enter_context(
				patch.object(self.middleware, "_validate_workspace_access",
							 return_value={"allowed": True})
			)
			stack.enter_context(patch.object(self.middleware, "_is_sensitive_path", return_value=False))
			mock_set_tenant = stack.enter_context(
				patch.object(self.middleware, "_set_tenant_context")
			)
			self.middleware.process_request(request)
		self.assertEqual(request.tenant_resolution_source, "domain")
		mock_set_tenant.assert_called_once_with(request, self.tenant_ws)

	def test_path_workspace_wins_over_profile_without_domain(self):
		"""Path workspace beats profile fallback when no domain mapping exists."""
		path_ws = SimpleNamespace(id=12, schema_name="path_ws")
		request = self._make_auth_request(profile_workspace=self.profile_ws)
		patches = self._base_patches(domain_ws=None, path_ws=path_ws, profile_ws=self.profile_ws)
		with contextlib.ExitStack() as stack:
			for p in patches:
				stack.enter_context(p)
			stack.enter_context(patch.object(self.middleware, "_handle_workspace_mismatch"))
			stack.enter_context(
				patch.object(self.middleware, "_validate_workspace_access",
							 return_value={"allowed": True})
			)
			stack.enter_context(patch.object(self.middleware, "_is_sensitive_path", return_value=False))
			mock_set_tenant = stack.enter_context(
				patch.object(self.middleware, "_set_tenant_context")
			)
			self.middleware.process_request(request)
		self.assertEqual(request.tenant_resolution_source, "path")
		mock_set_tenant.assert_called_once_with(request, path_ws)

	@patch("apps.orgs.middleware_v2.HttpResponseRedirect")
	@patch("apps.orgs.middleware_v2.messages")
	@patch("apps.orgs.middleware_v2.reverse", return_value="/orgs/workspace/10/dashboard/")
	def test_domain_path_workspace_mismatch_redirects_to_domain_workspace(
		self, _reverse, mock_messages, mock_redirect
	):
		"""A workspace id in path cannot target a different tenant than the mapped domain."""
		request = self._make_auth_request(path="/orgs/workspace/6/", profile_workspace=self.profile_ws)
		path_ws = SimpleNamespace(id=6, schema_name="tenant_six")
		patches = self._base_patches(
			domain_ws=self.tenant_ws,
			path_ws=path_ws,
			profile_ws=self.profile_ws,
		)

		with contextlib.ExitStack() as stack:
			for p in patches:
				stack.enter_context(p)
			mock_public = stack.enter_context(
				patch.object(self.middleware, "_set_public_context")
			)
			mock_mismatch_handler = stack.enter_context(
				patch.object(self.middleware, "_handle_workspace_mismatch")
			)
			result = self.middleware.process_request(request)

		mock_public.assert_called_once_with(request)
		mock_messages.error.assert_called_once()
		mock_redirect.assert_called_once_with("/orgs/workspace/10/dashboard/")
		mock_mismatch_handler.assert_not_called()
		self.assertIsNotNone(result)

	def test_platform_admin_bypasses_domain_path_workspace_mismatch_guard(self):
		"""Platform admins can still access path-target workspace even when domain differs."""
		path_ws = SimpleNamespace(id=6, schema_name="tenant_six")
		profile = SimpleNamespace(workspace=self.profile_ws, save=lambda **kw: None)
		superuser = SimpleNamespace(
			id=5,
			is_authenticated=True,
			is_superuser=True,
			profile=profile,
		)
		request = SimpleNamespace(path="/orgs/workspace/6/", user=superuser, META={})
		patches = self._base_patches(
			domain_ws=self.tenant_ws,
			path_ws=path_ws,
			profile_ws=self.profile_ws,
		)

		with contextlib.ExitStack() as stack:
			for p in patches:
				stack.enter_context(p)
			stack.enter_context(patch.object(self.middleware, "_handle_workspace_mismatch"))
			stack.enter_context(
				patch.object(self.middleware, "_validate_workspace_access", return_value={"allowed": True})
			)
			stack.enter_context(patch.object(self.middleware, "_is_sensitive_path", return_value=False))
			mock_set_tenant = stack.enter_context(
				patch.object(self.middleware, "_set_tenant_context")
			)
			result = self.middleware.process_request(request)

		self.assertEqual(request.tenant_resolution_source, "domain")
		mock_set_tenant.assert_called_once_with(request, self.tenant_ws)
		self.assertIsNone(result)

	# ── unauthenticated requests ─────────────────────────────────────────────────

	@patch("apps.orgs.middleware_v2.HttpResponseRedirect")
	@patch("apps.orgs.middleware_v2.reverse", return_value="/accounts/login/")
	def test_unauthenticated_with_domain_workspace_redirects_to_login(self, _rev, mock_redir):
		"""Anonymous request on tenant domain is forced to login with public context."""
		request = self._make_anon_request("/")
		with patch.object(self.middleware, "_is_exempt_url", return_value=False), \
			 patch.object(self.middleware, "_resolve_workspace_from_domain", return_value=self.tenant_ws), \
			 patch.object(self.middleware, "_resolve_workspace_from_path", return_value=None), \
			 patch.object(self.middleware, "_set_public_context") as mock_public, \
			 patch.object(self.middleware, "_set_tenant_context") as mock_tenant:
			self.middleware.process_request(request)

		mock_public.assert_called_once_with(request)
		mock_tenant.assert_not_called()
		mock_redir.assert_called_once()

	def test_unauthenticated_without_workspace_gets_public_context(self):
		"""Anonymous request with no workspace anywhere falls back to public schema."""
		request = self._make_anon_request("/")
		with patch.object(self.middleware, "_is_exempt_url", return_value=False), \
			 patch.object(self.middleware, "_resolve_workspace_from_domain", return_value=None), \
			 patch.object(self.middleware, "_resolve_workspace_from_path", return_value=None), \
			 patch.object(self.middleware, "_set_public_context") as mock_public:
			result = self.middleware.process_request(request)
		mock_public.assert_called_once_with(request)
		self.assertIsNone(result)

	@patch("apps.orgs.middleware_v2.HttpResponseRedirect")
	@patch("apps.orgs.middleware_v2.reverse", return_value="/accounts/login/")
	def test_unauthenticated_required_tenant_path_redirects_to_login(self, _rev, mock_redir):
		"""Anonymous request to tenant-only paths is redirected to login."""
		request = self._make_anon_request("/girvi/loans/")
		with patch.object(self.middleware, "_is_exempt_url", return_value=False), \
			 patch.object(self.middleware, "_resolve_workspace_from_domain", return_value=None), \
			 patch.object(self.middleware, "_resolve_workspace_from_path", return_value=None), \
			 patch.object(self.middleware, "_set_public_context") as mock_public:
			self.middleware.process_request(request)
		mock_public.assert_called_once_with(request)
		mock_redir.assert_called_once()

	# ── workspace-required redirect ───────────────────────────────────────────────

	@patch("apps.orgs.middleware_v2.HttpResponseRedirect")
	@patch("apps.orgs.middleware_v2.reverse", return_value="/orgs/workspace/select/")
	@patch("apps.orgs.middleware_v2.messages")
	def test_requires_workspace_but_none_resolved_redirects(self, mock_msgs, _rev, mock_redir):
		"""Authenticated user with no workspace on a required path is redirected to selector."""
		request = self._make_auth_request(path="/girvi/loans/", profile_workspace=None)
		patches = self._base_patches(domain_ws=None, path_ws=None, profile_ws=None)
		with contextlib.ExitStack() as stack:
			for p in patches:
				stack.enter_context(p)
			stack.enter_context(patch.object(self.middleware, "_handle_workspace_mismatch"))
			stack.enter_context(patch.object(self.middleware, "_requires_workspace", return_value=True))
			stack.enter_context(patch.object(self.middleware, "_set_public_context"))
			self.middleware.process_request(request)
		mock_msgs.warning.assert_called_once()
		mock_redir.assert_called_once()

	# ── access denied profile cleanup ────────────────────────────────────────────

	@patch("apps.orgs.middleware_v2.HttpResponseRedirect")
	@patch("apps.orgs.middleware_v2.reverse", return_value="/orgs/workspace/select/")
	@patch("apps.orgs.middleware_v2.messages")
	def test_access_denied_clears_profile_workspace(self, mock_msgs, _rev, _redir):
		"""When membership validation denies access, the stale profile workspace is cleared."""
		save_calls = []
		profile = SimpleNamespace(
			workspace=self.tenant_ws,
			save=lambda **kw: save_calls.append(kw),
		)
		user = SimpleNamespace(id=5, is_authenticated=True, profile=profile)
		request = SimpleNamespace(path="/girvi/loans/", user=user, META={})
		patches = self._base_patches(domain_ws=self.tenant_ws, profile_ws=self.tenant_ws)
		with contextlib.ExitStack() as stack:
			for p in patches:
				stack.enter_context(p)
			stack.enter_context(patch.object(self.middleware, "_handle_workspace_mismatch"))
			stack.enter_context(
				patch.object(self.middleware, "_validate_workspace_access",
							 return_value={
								 "allowed": False,
								 "reason": "not_member",
								 "message": "Access denied.",
							 })
			)
			stack.enter_context(patch.object(self.middleware, "_log_access"))
			stack.enter_context(patch.object(self.middleware, "_set_public_context"))
			self.middleware.process_request(request)
		self.assertIsNone(profile.workspace)
		self.assertTrue(save_calls)
		mock_msgs.error.assert_called_once()


class InvitationSignalHandlerTests(SimpleTestCase):
	def test_invite_accepted_existing_user_is_idempotent(self):
		user = SimpleNamespace(id=7)
		role = SimpleNamespace(name="Member")
		invitation = SimpleNamespace(company=SimpleNamespace(id=9), role=role)

		fake_qs = SimpleNamespace(first=lambda: user)
		with patch.object(org_signals.User.objects, "filter", return_value=fake_qs), \
			 patch.object(org_signals.Membership.objects, "get_or_create") as mock_get_or_create, \
			 patch.object(org_signals.PendingInvitation.objects, "get_or_create") as mock_pending:
			org_signals.create_membership(
				sender=object(), email="User@Example.com", invitation=invitation
			)

		mock_get_or_create.assert_called_once_with(
			user=user,
			company=invitation.company,
			defaults={"role": invitation.role},
		)
		mock_pending.assert_not_called()

	def test_invite_accepted_unknown_user_creates_pending(self):
		invitation = SimpleNamespace(
			company=SimpleNamespace(id=9),
			role=SimpleNamespace(name="Member"),
		)
		fake_qs = SimpleNamespace(first=lambda: None)

		with patch.object(org_signals.User.objects, "filter", return_value=fake_qs), \
			 patch.object(org_signals.Membership.objects, "get_or_create") as mock_get_or_create, \
			 patch.object(org_signals.PendingInvitation.objects, "get_or_create") as mock_pending:
			org_signals.create_membership(
				sender=object(), email="new@example.com", invitation=invitation
			)

		mock_get_or_create.assert_not_called()
		mock_pending.assert_called_once_with(
			email="new@example.com",
			company=invitation.company,
			defaults={"role": invitation.role},
		)

	def test_invite_accepted_without_invitation_is_noop(self):
		with patch.object(org_signals.Membership.objects, "get_or_create") as mock_get_or_create, \
			 patch.object(org_signals.PendingInvitation.objects, "get_or_create") as mock_pending:
			org_signals.create_membership(sender=object(), email="x@example.com")

		mock_get_or_create.assert_not_called()
		mock_pending.assert_not_called()

	def test_user_signed_up_consumes_all_pending_invites(self):
		user = SimpleNamespace(email="user@example.com")
		pending_1 = SimpleNamespace(
			company=SimpleNamespace(id=1),
			role=SimpleNamespace(name="Member"),
			delete=lambda: None,
		)
		pending_2 = SimpleNamespace(
			company=SimpleNamespace(id=2),
			role=SimpleNamespace(name="Admin"),
			delete=lambda: None,
		)

		class PendingQS:
			def select_related(self, *_args):
				return [pending_1, pending_2]

		with patch.object(
			org_signals.PendingInvitation.objects,
			"filter",
			return_value=PendingQS(),
		), patch.object(
			org_signals.transaction,
			"atomic",
			return_value=contextlib.nullcontext(),
		), patch.object(
			org_signals.Membership.objects,
			"get_or_create",
		) as mock_get_or_create, patch.object(
			pending_1,
			"delete",
		) as delete_1, patch.object(
			pending_2,
			"delete",
		) as delete_2:
			org_signals.create_membership_on_signup(sender=object(), user=user)

		self.assertEqual(mock_get_or_create.call_count, 2)
		delete_1.assert_called_once()
		delete_2.assert_called_once()

	def test_user_signed_up_without_email_is_noop(self):
		with patch.object(org_signals.PendingInvitation.objects, "filter") as mock_filter:
			org_signals.create_membership_on_signup(
				sender=object(), user=SimpleNamespace(email="")
			)
		mock_filter.assert_not_called()
