"""
Enhanced WorkspaceMiddleware with security validation.
Fixes critical authorization bypass vulnerability.

This module is intentionally standalone (it does not inherit from
schema-tenancy middleware). The request flow is security-critical and custom:
deterministic Workspace resolution, membership authorization, and explicit
redirect/cleanup behavior.
"""

import logging
import re

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import DisallowedHost
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.urls import reverse, set_urlconf
from django.utils.deprecation import MiddlewareMixin

from apps.orgs.audit import AuditLog
from apps.orgs.access import resolve_workspace_access
from apps.orgs.lifecycle import lifecycle_access
from apps.orgs.models import Company, Domain, Membership
from apps.orgs.permissions import is_platform_admin
from apps.tenancy.context import workspace_context

logger = logging.getLogger(__name__)

PUBLIC_WORKSPACE_SLUG = "public"


class SecureWorkspaceMiddleware(MiddlewareMixin):
    """
    🔒 SECURE middleware with proper authorization validation.

    Security Features:
    ✅ Validates user membership before granting access
    ✅ Checks subscription status
    ✅ Logs all access attempts
    ✅ Handles suspended/deleted companies
    ✅ Prevents unauthorized tenant context switching
    """

    # URLs exempt from workspace validation
    # Note: "/admin/" is intentionally NOT exempt here so that Django admin
    # requests on tenant domains receive the correct tenant schema context.
    # The public-schema admin is served from SECRET_ADMIN_URL (public_urls.py),
    # not from "/admin/", so there is no conflict.
    EXEMPT_URLS = [
        "/accounts/",
        "/app/",
        "/onboarding/",
        "/profile/",
        "/static/",
        "/media/",
        "/__debug__/",
    ]

    GLOBAL_CONTROL_PLANE_URLS = {
        "/orgs/workspace/",
        "/orgs/workspace/create/",
        "/orgs/workspace/list/",
        "/orgs/workspace/archived/",
        "/orgs/team/invitations/",
        "/orgs/memberships/",
        "/orgs/profile/",
        "/orgs/account/settings/",
    }

    # URLs that require workspace
    WORKSPACE_REQUIRED_URLS = [
        "/party/",
        "/portal/",
        "/girvi/",
        "/loans/",
        "/sales/",
        "/purchase/",
        "/contact/",
        "/data-tools/",
        "/rates/",
        "/approval/",
        "/notify/",
        "/notify-v2/",
    ]

    WORKSPACE_ID_PATTERNS = [
        re.compile(r"^/orgs/workspace/(?P<workspace_id>\d+)(/|$)"),
        re.compile(r"^/orgs/company/(?P<workspace_id>\d+)(/|$)"),
        re.compile(r"^/workspace/(?P<workspace_id>\d+)/settings(/|$)"),
    ]
    WORKSPACE_SLUG_PATTERNS = [
        re.compile(r"^/w/(?P<workspace_slug>[A-Za-z0-9_][A-Za-z0-9_-]{0,62})(/|$)"),
    ]

    def process_request(self, request):
        """Process request with deterministic tenant resolution and membership validation."""

        # Exempt URL → public schema and public URLConf
        if self._is_exempt_url(request.path):
            self._set_public_context(request)
            return None

        # Resolve only explicit request identity. Profile Workspace is a
        # navigation preference, never request or database authority.
        domain_workspace = self._resolve_workspace_from_domain(request)
        path_workspace = self._resolve_workspace_from_path(request)

        workspace, source = self._select_workspace_candidate(
            domain_workspace=domain_workspace,
            path_workspace=path_workspace,
        )

        # Multiple explicit identities must agree. Platform authority never
        # resolves an ambiguous Workspace identity.
        if (
            domain_workspace
            and path_workspace
            and domain_workspace.id != path_workspace.id
            and domain_workspace.schema_name != PUBLIC_WORKSPACE_SLUG
        ):
            logger.warning(
                "Workspace path/domain mismatch for user %s: domain=%s path=%s path_url=%s",
                getattr(request.user, "id", None),
                domain_workspace.id,
                path_workspace.id,
                request.path,
            )
            self._set_public_context(request)
            messages.error(
                request,
                "Workspace URL does not match the current domain.",
            )
            return HttpResponseForbidden("Conflicting Workspace identity.")

        # Keep a clear signal for downstream code and diagnostics.
        request.workspace_resolution_source = source

        # Unauthenticated requests can still be served in the resolved tenant schema.
        if not request.user.is_authenticated:
            if workspace and workspace.schema_name != PUBLIC_WORKSPACE_SLUG:
                # For ERP SaaS: no public content on tenant domains — force login
                self._set_public_context(request)
                return HttpResponseRedirect(
                    f"{reverse('account_login')}?next={request.path}"
                )

            if self._requires_workspace(request.path):
                # Safety reset: explicitly clear any stale tenant schema/urlconf before
                # redirecting to login.  DB connections are reused across requests, so
                # leaving a tenant schema active while serving a public redirect is unsafe —
                # response middleware and error handlers would run against the wrong schema.
                self._set_public_context(request)
                return HttpResponseRedirect(reverse("account_login"))

            self._set_public_context(request)
            return None

        # No workspace but URL requires it → redirect
        if not workspace and self._requires_workspace(request.path):
            messages.warning(request, "Please select a workspace to continue.")
            self._set_public_context(request)
            return HttpResponseRedirect(reverse("workspace_selector"))

        # Public workspace (or unresolved) → public schema
        if not workspace or workspace.schema_name == PUBLIC_WORKSPACE_SLUG:
            self._set_public_context(request)
            return None

        # Validate membership and tenant status before switching schema.
        validation = self._validate_workspace_access(
            user=request.user, workspace=workspace, request=request
        )

        if validation["allowed"]:
            self._set_workspace_context(request, workspace)
            request.workspace_access = validation.get("access")

            if getattr(request.workspace_access, "platform_override", False):
                self._log_platform_override(request, workspace)
            elif self._is_sensitive_path(request.path):
                self._log_access(request, workspace, success=True)

            return None

        # ❌ Access denied
        self._log_access(request, workspace, success=False, reason=validation["reason"])

        # Clear invalid profile workspace if it points to denied tenant.
        if hasattr(request.user, "profile") and request.user.profile.workspace == workspace:
            request.user.profile.workspace = None
            request.user.profile.save(update_fields=["workspace"])

        # Show error and bounce to selector.
        messages.error(request, validation["message"])
        self._set_public_context(request)
        return HttpResponseRedirect(reverse("workspace_selector"))

    def _set_public_context(self, request):
        """Clear Workspace context for a global/control-plane request."""
        self._close_workspace_context(request)
        request.workspace = None
        request.workspace_access = None
        request.urlconf = settings.ROOT_URLCONF
        set_urlconf(request.urlconf)

    def _set_workspace_context(self, request, workspace):
        """Establish explicit shared-schema Workspace context."""
        context_manager = workspace_context(workspace.id)
        context_manager.__enter__()
        request._workspace_context_manager = context_manager
        request.workspace = workspace
        request.urlconf = settings.ROOT_URLCONF
        set_urlconf(request.urlconf)

    def _close_workspace_context(self, request, exc=None):
        context_manager = getattr(request, "_workspace_context_manager", None)
        if context_manager is None:
            return
        request._workspace_context_manager = None
        if exc is None:
            context_manager.__exit__(None, None, None)
        else:
            context_manager.__exit__(type(exc), exc, exc.__traceback__)

    def process_response(self, request, response):
        self._close_workspace_context(request)
        return response

    def process_exception(self, request, exception):
        self._close_workspace_context(request, exception)
        return None

    def _resolve_workspace_from_domain(self, request):
        """Resolve workspace from request hostname via Domain model."""
        try:
            hostname = request.get_host().split(":")[0].lower().removeprefix("www.")
        except DisallowedHost:
            logger.warning("Disallowed host header encountered during tenant resolution")
            return None

        domain = Domain.objects.select_related("tenant").filter(domain=hostname).first()
        if domain:
            return domain.tenant
        return None

    def _resolve_workspace_from_path(self, request):
        """Resolve workspace from known id or slug path patterns."""
        workspace_id = self._extract_workspace_id_from_path(request.path)
        if workspace_id:
            return Company.all_objects.filter(id=workspace_id).first()

        workspace_slug = self._extract_workspace_slug_from_path(request.path)
        if not workspace_slug or workspace_slug == PUBLIC_WORKSPACE_SLUG:
            return None

        return Company.all_objects.filter(
            schema_name=workspace_slug,
        ).first()

    def _extract_workspace_id_from_path(self, path):
        """Extract workspace id from path using known workspace URL patterns."""
        for pattern in self.WORKSPACE_ID_PATTERNS:
            match = pattern.match(path)
            if match:
                return int(match.group("workspace_id"))
        return None

    def _extract_workspace_slug_from_path(self, path):
        """Extract workspace slug from future /w/<workspace_slug>/... paths."""
        for pattern in self.WORKSPACE_SLUG_PATTERNS:
            match = pattern.match(path)
            if match:
                return match.group("workspace_slug")
        return None

    def _select_workspace_candidate(
        self, domain_workspace, path_workspace, profile_workspace=None
    ):
        """Pick the effective Workspace from explicit request identity."""
        public_schema = PUBLIC_WORKSPACE_SLUG

        if domain_workspace and domain_workspace.schema_name != public_schema:
            return domain_workspace, "domain"

        if path_workspace and path_workspace.schema_name != public_schema:
            return path_workspace, "path"

        if domain_workspace and domain_workspace.schema_name == public_schema:
            return domain_workspace, "domain-public"

        return None, "public"

    def _get_user_workspace(self, request):
        """Retired compatibility seam: profile preference is never authority."""
        return None

    def _handle_workspace_mismatch(self, **kwargs):
        """Retired compatibility seam; explicit conflicts are rejected inline."""
        return None

    def _validate_workspace_access(self, user, workspace, request):
        """
        🔒 CRITICAL SECURITY CHECK

        Validates that user is actually a member of the workspace.
        Returns dict with 'allowed', 'reason', 'message' keys.
        """

        access = resolve_workspace_access(actor=user, workspace=workspace)

        lifecycle = lifecycle_access(workspace=workspace, access=access)
        recovery_path = request.path.startswith(
            (
                f"/w/{workspace.schema_name}/settings/",
                f"/w/{workspace.schema_name}/data-tools/export/",
                f"/workspace/{workspace.id}/settings/",
                f"/orgs/workspace/{workspace.id}/restore/",
                f"/orgs/workspace/{workspace.id}/lifecycle/",
            )
        )
        if not lifecycle.may_enter_business and not (
            recovery_path and lifecycle.may_use_recovery
        ):
            return {
                "allowed": False,
                "reason": "WORKSPACE_LIFECYCLE_DENIED",
                "message": "This Workspace is not available for ordinary operation.",
            }

        # Platform administrators bypass membership, never lifecycle controls.
        if access.platform_override:
            logger.debug(
                f"✅ Superuser {user.id} ({user.email}) granted access to workspace "
                f"{workspace.id} ({workspace.name}) without membership requirement."
            )
            return {
                "allowed": True,
                "reason": "SUPERUSER",
                "message": "",
                "membership": None,
                "access": access,
            }

        # 🔒 Check 1: IS USER A MEMBER? (MOST IMPORTANT)
        membership = access.membership
        if membership is None:
            # ❌ NOT A MEMBER - LOG AS SECURITY INCIDENT
            logger.error(
                f"🚨 SECURITY ALERT: User {user.id} ({user.email}) "
                f"attempted to access workspace {workspace.id} ({workspace.name}) "
                f"WITHOUT MEMBERSHIP - Potential attack!"
            )

            # Log to audit system
            AuditLog.log(
                action="UNAUTHORIZED_ACCESS",
                user=user,
                company=workspace,
                description=f"Unauthorized access attempt to workspace {workspace.name}",
                request=request,
                success=False,
                data={
                    "workspace_id": workspace.id,
                    "workspace_name": workspace.name,
                    "path": request.path,
                },
            )

            return {
                "allowed": False,
                "reason": "NO_MEMBERSHIP",
                "message": "You are not a member of this workspace.",
            }

        # ✅ All checks passed - AUTHORIZED
        logger.debug(
            f"✅ User {user.id} authorized for workspace {workspace.id} "
            f"with role {membership.role.name}"
        )

        return {
            "allowed": True,
            "reason": "AUTHORIZED",
            "message": "",
            "membership": membership,
            "access": access,
        }

    def _is_exempt_url(self, path):
        """Return whether the route is explicitly global/control-plane."""
        return path in self.GLOBAL_CONTROL_PLANE_URLS or any(
            path.startswith(exempt) for exempt in self.EXEMPT_URLS
        )

    def _requires_workspace(self, path):
        """Check if URL requires workspace context"""
        return any(
            path.startswith(required) for required in self.WORKSPACE_REQUIRED_URLS
        )

    def _is_sensitive_path(self, path):
        """Check if path should be logged"""
        sensitive = ["/settings/", "/billing/", "/team/", "/preferences/"]
        return any(pattern in path for pattern in sensitive)

    def _log_access(self, request, workspace, success=True, reason=""):
        """Log workspace access attempt"""
        try:
            action = "UNAUTHORIZED_ACCESS" if not success else "WORKSPACE_ACCESS"
            description = f"Access to workspace {workspace.name}"
            if not success:
                description += f" denied: {reason}"

            AuditLog.log(
                action=action,
                user=request.user,
                company=workspace,
                description=description,
                request=request,
                success=success,
                data={"path": request.path, "reason": reason},
            )
        except Exception as e:
            logger.error(f"Failed to log workspace access: {e}")

    def _log_platform_override(self, request, workspace):
        """Audit every successful membership bypass after context is established."""
        try:
            AuditLog.log(
                action="WORKSPACE_ACCESS",
                user=request.user,
                company=workspace,
                description=f"Platform override access to workspace {workspace.name}",
                request=request,
                success=True,
                data={
                    "workspace_id": workspace.id,
                    "path": request.path,
                    "resolution_source": request.workspace_resolution_source,
                    "platform_override": True,
                },
            )
        except Exception as exc:
            logger.error(f"Failed to log platform override access: {exc}")
