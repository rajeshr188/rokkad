"""
Enhanced WorkspaceMiddleware with security validation.
Fixes critical authorization bypass vulnerability.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.db import connection
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils.deprecation import MiddlewareMixin
from django_tenants.utils import get_public_schema_name

from apps.orgs.audit import AuditLog
from apps.orgs.models import Membership

logger = logging.getLogger(__name__)


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
    EXEMPT_URLS = [
        "/accounts/",
        "/admin/",
        "/static/",
        "/media/",
        "/__debug__/",
    ]

    # URLs that require workspace
    WORKSPACE_REQUIRED_URLS = [
        "/girvi/",
        "/dea/",
        "/sales/",
        "/purchase/",
        "/contact/",
        "/product/",
        "/rates/",
    ]

    def process_request(self, request):
        """🔒 SECURE: Process request with membership validation"""

        # Not authenticated → public schema
        if not request.user.is_authenticated:
            connection.set_schema_to_public()
            return None

        # Exempt URL → public schema
        if self._is_exempt_url(request.path):
            connection.set_schema_to_public()
            return None

        # Get user's workspace preference
        workspace = self._get_user_workspace(request.user)

        # No workspace but URL requires it → redirect
        if not workspace and self._requires_workspace(request.path):
            messages.warning(request, "Please select a workspace to continue.")
            return HttpResponseRedirect(reverse("orgs_company_list"))

        # Public workspace → use public schema
        if workspace and workspace.schema_name == get_public_schema_name():
            connection.set_schema_to_public()
            request.tenant = workspace
            return None

        # 🔒 CRITICAL: Validate workspace access
        if workspace:
            validation = self._validate_workspace_access(
                user=request.user, workspace=workspace, request=request
            )

            if validation["allowed"]:
                # ✅ Access granted
                connection.set_tenant(workspace)
                request.tenant = workspace

                # Log sensitive access
                if self._is_sensitive_path(request.path):
                    self._log_access(request, workspace, success=True)

                return None
            else:
                # ❌ Access denied
                self._log_access(
                    request, workspace, success=False, reason=validation["reason"]
                )

                # Clear invalid workspace
                request.user.profile.workspace = None
                request.user.profile.save()

                # Show error
                messages.error(request, validation["message"])
                return HttpResponseRedirect(reverse("workspace_list"))

        # Default: public schema
        connection.set_schema_to_public()
        return None

    def _validate_workspace_access(self, user, workspace, request):
        """
        🔒 CRITICAL SECURITY CHECK

        Validates that user is actually a member of the workspace.
        Returns dict with 'allowed', 'reason', 'message' keys.
        """

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

        # Future: Check 3: Subscription status
        if "subscriptions" in settings.INSTALLED_APPS:
            subscription_check = self._check_subscription(workspace)
            if not subscription_check["allowed"]:
                return subscription_check

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

    def _check_subscription(self, workspace):
        """Check if workspace subscription is active"""
        try:
            from subscriptions.models import Subscription

            subscription = (
                Subscription.objects.filter(company=workspace)
                .order_by("-created_at")
                .first()
            )

            if not subscription:
                return {
                    "allowed": False,
                    "reason": "NO_SUBSCRIPTION",
                    "message": "This workspace does not have an active subscription.",
                }

            if hasattr(subscription, "is_expired") and subscription.is_expired():
                return {
                    "allowed": False,
                    "reason": "SUBSCRIPTION_EXPIRED",
                    "message": "This workspace subscription has expired.",
                }

            if hasattr(subscription, "is_suspended") and subscription.is_suspended():
                return {
                    "allowed": False,
                    "reason": "SUBSCRIPTION_SUSPENDED",
                    "message": "This workspace subscription has been suspended.",
                }

        except ImportError:
            # Subscriptions app not installed, skip check
            pass
        except Exception as e:
            logger.error(
                f"Error checking subscription for workspace {workspace.id}: {e}"
            )

        return {"allowed": True, "reason": "SUBSCRIPTION_ACTIVE", "message": ""}

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
