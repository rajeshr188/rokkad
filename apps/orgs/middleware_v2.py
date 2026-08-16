"""
Enhanced WorkspaceMiddleware with security validation.
Fixes critical authorization bypass vulnerability.

This module is intentionally standalone (it does not inherit from
TenantMainMiddleware). The request flow is security-critical and custom:
deterministic tenant resolution, membership/subscription authorization,
mismatch auditing, and explicit redirect/cleanup behavior.
"""

import logging
import re

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import DisallowedHost
from django.db import connection
from django.http import HttpResponseRedirect
from django.urls import reverse, set_urlconf
from django.utils.deprecation import MiddlewareMixin
from django_tenants.utils import (
    get_public_schema_name,
    get_public_schema_urlconf,
    get_tenant_domain_model,
    remove_www,
)

from apps.orgs.audit import AuditLog
from apps.orgs.models import Company, Membership
from apps.orgs.permissions import is_platform_admin
from apps.subscriptions.services import SubscriptionAccessService

logger = logging.getLogger(__name__)

subscription_access_service = SubscriptionAccessService()


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
        "/static/",
        "/media/",
        "/__debug__/",
    ]

    # URLs that require workspace
    WORKSPACE_REQUIRED_URLS = [
        "/party/",
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

        # Resolve candidates in a deterministic order:
        # 1) Domain mapping (authoritative)
        # 2) URL path workspace hints
        # 3) User profile workspace fallback (transition mode)
        domain_workspace = self._resolve_workspace_from_domain(request)
        path_workspace = self._resolve_workspace_from_path(request)
        profile_workspace = (
            self._get_user_workspace(request.user)
            if request.user.is_authenticated
            else None
        )

        workspace, source = self._select_workspace_candidate(
            domain_workspace=domain_workspace,
            path_workspace=path_workspace,
            profile_workspace=profile_workspace,
        )

        # Domain mapping is authoritative. If path embeds a different workspace id,
        # reject it to prevent cross-workspace URL probing on tenant domains.
        if (
            domain_workspace
            and path_workspace
            and domain_workspace.id != path_workspace.id
            and domain_workspace.schema_name != get_public_schema_name()
            and not (
                request.user.is_authenticated and is_platform_admin(request.user)
            )
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
            return HttpResponseRedirect(
                reverse("workspace_dashboard", kwargs={"workspace_id": domain_workspace.id})
            )

        # Keep a clear signal for downstream code and diagnostics.
        request.tenant_resolution_source = source

        # Unauthenticated requests can still be served in the resolved tenant schema.
        if not request.user.is_authenticated:
            if workspace and workspace.schema_name != get_public_schema_name():
                # self._set_tenant_context(request, workspace)
                # return None
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

        self._handle_workspace_mismatch(
            request=request,
            domain_workspace=domain_workspace,
            profile_workspace=profile_workspace,
        )

        # No workspace but URL requires it → redirect
        if not workspace and self._requires_workspace(request.path):
            messages.warning(request, "Please select a workspace to continue.")
            self._set_public_context(request)
            return HttpResponseRedirect(reverse("workspace_selector"))

        # Public workspace (or unresolved) → public schema
        if not workspace or workspace.schema_name == get_public_schema_name():
            self._set_public_context(request)
            return None

        # Validate membership and tenant status before switching schema.
        validation = self._validate_workspace_access(
            user=request.user, workspace=workspace, request=request
        )

        if validation["allowed"]:
            self._set_tenant_context(request, workspace)

            # Keep profile workspace synchronized to the effective tenant.
            if profile_workspace != workspace and hasattr(request.user, "profile"):
                request.user.profile.workspace = workspace
                request.user.profile.save(update_fields=["workspace"])

            # Log sensitive access
            if self._is_sensitive_path(request.path):
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
        """Set request context to public schema and URLConf."""
        connection.set_schema_to_public()
        request.urlconf = getattr(
            settings, "PUBLIC_SCHEMA_URLCONF", get_public_schema_urlconf()
        )
        set_urlconf(request.urlconf)

    def _set_tenant_context(self, request, workspace):
        """Set request context to tenant schema and tenant URLConf."""
        connection.set_tenant(workspace)
        request.tenant = workspace
        request.urlconf = settings.ROOT_URLCONF
        set_urlconf(request.urlconf)

    def _resolve_workspace_from_domain(self, request):
        """Resolve workspace from request hostname via Domain model."""
        connection.set_schema_to_public()

        try:
            hostname = remove_www(request.get_host().split(":")[0]).lower()
        except DisallowedHost:
            logger.warning("Disallowed host header encountered during tenant resolution")
            return None

        domain_model = get_tenant_domain_model()
        domain = domain_model.objects.select_related("tenant").filter(domain=hostname).first()
        if domain:
            return domain.tenant
        return None

    def _resolve_workspace_from_path(self, request):
        """Resolve workspace from known id or slug path patterns."""
        connection.set_schema_to_public()

        workspace_id = self._extract_workspace_id_from_path(request.path)
        if workspace_id:
            return Company.objects.filter(id=workspace_id, is_deleted=False).first()

        workspace_slug = self._extract_workspace_slug_from_path(request.path)
        if not workspace_slug or workspace_slug == get_public_schema_name():
            return None

        return Company.objects.filter(
            schema_name=workspace_slug,
            is_deleted=False,
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

    def _select_workspace_candidate(self, domain_workspace, path_workspace, profile_workspace):
        """Pick the effective workspace in deterministic priority order."""
        public_schema = get_public_schema_name()

        if domain_workspace and domain_workspace.schema_name != public_schema:
            return domain_workspace, "domain"

        if path_workspace and path_workspace.schema_name != public_schema:
            return path_workspace, "path"

        if profile_workspace and profile_workspace.schema_name != public_schema:
            return profile_workspace, "profile"

        if domain_workspace and domain_workspace.schema_name == public_schema:
            return domain_workspace, "domain-public"

        return None, "public"

    def _handle_workspace_mismatch(self, request, domain_workspace, profile_workspace):
        """Log mismatch when domain-resolved tenant and selected profile workspace diverge."""
        if not domain_workspace or not profile_workspace:
            return

        if domain_workspace.id == profile_workspace.id:
            return

        if domain_workspace.schema_name == get_public_schema_name():
            return

        logger.warning(
            "Workspace mismatch detected for user %s: domain=%s profile=%s",
            request.user.id,
            domain_workspace.id,
            profile_workspace.id,
        )

        AuditLog.log(
            action="UNAUTHORIZED_ACCESS",
            user=request.user,
            company=profile_workspace,
            description="Workspace mismatch between domain resolution and selected profile workspace",
            request=request,
            success=False,
            data={
                "path": request.path,
                "domain_workspace_id": domain_workspace.id,
                "profile_workspace_id": profile_workspace.id,
            },
        )

    def _validate_workspace_access(self, user, workspace, request):
        """
        🔒 CRITICAL SECURITY CHECK

        Validates that user is actually a member of the workspace.
        Returns dict with 'allowed', 'reason', 'message' keys.
        """

        # Superusers bypass membership checks (Django admin / staff access)
        if is_platform_admin(user):
            logger.debug(
                f"✅ Superuser {user.id} ({user.email}) granted access to workspace "
                f"{workspace.id} ({workspace.name}) without membership requirement."
            )
            return {
                "allowed": True,
                "reason": "SUPERUSER",
                "message": "",
                "membership": None,
            }

        # Check 1: Is company deleted?
        if workspace.is_deleted:
            logger.warning(
                f"User {user.id} tried to access deleted workspace {workspace.id}"
            )
            return {
                "allowed": False,
                "reason": "COMPANY_DELETED",
                "message": "This workspace has been deleted.",
            }

        # 🔒 Check 2: IS USER A MEMBER? (MOST IMPORTANT)
        try:
            membership = Membership.objects.select_related("role").get(
                user=user, company=workspace
            )
        except Membership.DoesNotExist:
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

        # Centralized subscription and entitlement evaluation.
        if "subscriptions" in settings.INSTALLED_APPS:
            decision = subscription_access_service.evaluate_access(
                user=user,
                workspace=workspace,
                membership=membership,
            )
            if not decision.allowed:
                return {
                    "allowed": False,
                    "reason": decision.reason,
                    "message": decision.message,
                    "membership": membership,
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
        }

    def _get_user_workspace(self, user):
        """Safely get user's workspace"""
        try:
            if hasattr(user, "profile") and user.profile.workspace:
                return user.profile.workspace
        except Exception as e:
            logger.error(f"Error getting workspace for user {user.id}: {e}")
        return None

    def _is_exempt_url(self, path):
        """Check if URL is exempt from workspace validation"""
        return any(path.startswith(exempt) for exempt in self.EXEMPT_URLS)

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
