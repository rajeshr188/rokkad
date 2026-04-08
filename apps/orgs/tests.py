import contextlib
from types import SimpleNamespace
from unittest.mock import patch

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import reverse
from django_tenants.utils import get_public_schema_name

from apps.orgs.middleware_v2 import SecureWorkspaceMiddleware
from apps.orgs.views import CompanyPreferenceBuilder
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

	# ── unauthenticated requests ─────────────────────────────────────────────────

	def test_unauthenticated_with_domain_workspace_gets_tenant_context(self):
		"""Anonymous request on a domain-mapped host receives tenant schema context."""
		request = self._make_anon_request("/")
		with patch.object(self.middleware, "_is_exempt_url", return_value=False), \
			 patch.object(self.middleware, "_resolve_workspace_from_domain", return_value=self.tenant_ws), \
			 patch.object(self.middleware, "_resolve_workspace_from_path", return_value=None), \
			 patch.object(self.middleware, "_set_tenant_context") as mock_set_tenant:
			result = self.middleware.process_request(request)
		mock_set_tenant.assert_called_once_with(request, self.tenant_ws)
		self.assertIsNone(result)

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
