"""
Audit logging system for tracking security-sensitive operations.
"""

from functools import wraps

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.orgs.tenant_context import resolve_request_workspace


class AuditLogManager(models.Manager):
    """Custom manager for AuditLog with common query methods"""

    def for_user(self, user):
        """Get all audit logs for a specific user"""
        return self.filter(user=user)

    def for_company(self, company):
        """Get all audit logs for a specific company"""
        return self.filter(company=company)

    def for_action(self, action):
        """Get all audit logs for a specific action type"""
        return self.filter(action=action)

    def security_events(self):
        """Get security-related events"""
        return self.filter(
            action__in=[
                "LOGIN",
                "LOGOUT",
                "LOGIN_FAILED",
                "PERMISSION_DENIED",
                "UNAUTHORIZED_ACCESS",
            ]
        )

    def recent(self, days=7):
        """Get recent audit logs"""
        from datetime import timedelta

        cutoff = timezone.now() - timedelta(days=days)
        return self.filter(timestamp__gte=cutoff)


class AuditLog(models.Model):
    """
    Comprehensive audit logging for security and compliance.
    Tracks all sensitive operations across the application.
    """

    # Action types
    ACTION_CHOICES = [
        # Authentication
        ("LOGIN", "User Login"),
        ("LOGOUT", "User Logout"),
        ("LOGIN_FAILED", "Login Failed"),
        ("PASSWORD_CHANGE", "Password Changed"),
        ("PASSWORD_RESET", "Password Reset"),
        # Company/Workspace
        ("COMPANY_CREATE", "Company Created"),
        ("COMPANY_UPDATE", "Company Updated"),
        ("COMPANY_DELETE", "Company Deleted"),
        ("COMPANY_RESTORE", "Company Restored"),
        ("WORKSPACE_ACCESS", "Workspace Accessed"),
        # Team Management
        ("MEMBER_INVITE", "Member Invited"),
        ("MEMBER_JOIN", "Member Joined"),
        ("MEMBER_REMOVE", "Member Removed"),
        ("MEMBER_ROLE_CHANGE", "Member Role Changed"),
        # Permissions & Security
        ("PERMISSION_GRANT", "Permission Granted"),
        ("PERMISSION_REVOKE", "Permission Revoked"),
        ("PERMISSION_DENIED", "Permission Denied"),
        ("UNAUTHORIZED_ACCESS", "Unauthorized Access Attempt"),
        # Data Operations
        ("DATA_CREATE", "Data Created"),
        ("DATA_UPDATE", "Data Updated"),
        ("DATA_DELETE", "Data Deleted"),
        ("DATA_EXPORT", "Data Exported"),
        ("DATA_IMPORT", "Data Imported"),
        # Billing
        ("BILLING_UPDATE", "Billing Updated"),
        ("SUBSCRIPTION_CHANGE", "Subscription Changed"),
        ("SUBSCRIPTION_CANCEL", "Subscription Cancelled"),
        ("PAYMENT_SUCCESS", "Payment Successful"),
        ("PAYMENT_FAILED", "Payment Failed"),
        # Settings
        ("SETTINGS_UPDATE", "Settings Updated"),
        # Preferences
        ("PREFERENCES_UPDATE", "Preferences Updated"),
        # Ownership
        ("OWNERSHIP_TRANSFER", "Ownership Transferred"),
    ]

    # Core fields
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("User"),
        help_text=_("User who performed the action"),
    )

    company = models.ForeignKey(
        "orgs.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_logs",
        verbose_name=_("Company"),
        help_text=_("Company context for the action"),
    )

    action = models.CharField(
        max_length=50, choices=ACTION_CHOICES, verbose_name=_("Action"), db_index=True
    )

    timestamp = models.DateTimeField(
        auto_now_add=True, verbose_name=_("Timestamp"), db_index=True
    )

    # Object tracking (for generic relations)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name=_("Content Type"),
    )
    object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name=_("Object ID")
    )
    content_object = GenericForeignKey("content_type", "object_id")

    # Request metadata
    ip_address = models.GenericIPAddressField(
        null=True, blank=True, verbose_name=_("IP Address")
    )
    user_agent = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("User Agent")
    )

    # Details
    description = models.TextField(
        blank=True,
        verbose_name=_("Description"),
        help_text=_("Human-readable description of the action"),
    )

    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Additional Data"),
        help_text=_("JSON data with additional context"),
    )

    # Result
    success = models.BooleanField(
        default=True,
        verbose_name=_("Success"),
        help_text=_("Whether the action was successful"),
    )

    error_message = models.TextField(
        blank=True,
        verbose_name=_("Error Message"),
        help_text=_("Error message if action failed"),
    )

    objects = AuditLogManager()

    class Meta:
        verbose_name = _("Audit Log")
        verbose_name_plural = _("Audit Logs")
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["company", "-timestamp"]),
            models.Index(fields=["action", "-timestamp"]),
            models.Index(fields=["-timestamp"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} by {self.user} at {self.timestamp}"

    @staticmethod
    def log(
        action,
        user=None,
        company=None,
        description="",
        data=None,
        request=None,
        content_object=None,
        success=True,
        error_message="",
    ):
        """
        Convenience method to create audit log entries.

        Usage:
            AuditLog.log('COMPANY_CREATE', user=request.user, company=company,
                        description='Created new company', request=request)
        """
        log_data = {
            "action": action,
            "user": user,
            "company": company,
            "description": description,
            "data": data or {},
            "success": success,
            "error_message": error_message,
        }

        # Extract request metadata
        if request:
            log_data["ip_address"] = get_client_ip(request)
            log_data["user_agent"] = request.META.get("HTTP_USER_AGENT", "")[:255]

        # Add generic foreign key if object provided
        if content_object:
            log_data["content_object"] = content_object

        return AuditLog.objects.create(**log_data)


def get_client_ip(request):
    """Extract client IP address from request"""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")
    return ip


# ============================================================================
# DECORATOR FOR AUTOMATIC AUDIT LOGGING
# ============================================================================


def audit_log(action, description="", log_args=False):
    """
    Decorator to automatically log function calls.

    Usage:
        @audit_log('COMPANY_CREATE', 'Company creation')
        def create_company(request, ...):
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            request = None
            user = None
            company = None

            # Try to extract request from args
            for arg in args:
                if hasattr(arg, "user") and hasattr(arg, "META"):
                    request = arg
                    user = request.user if request.user.is_authenticated else None
                    if user:
                        company = resolve_request_workspace(
                            request,
                            include_public=True,
                        )
                    break

            # Execute the function
            try:
                result = func(*args, **kwargs)

                # Log success
                log_data = {}
                if log_args:
                    log_data["args"] = str(args)
                    log_data["kwargs"] = str(kwargs)

                AuditLog.log(
                    action=action,
                    user=user,
                    company=company,
                    description=description,
                    data=log_data,
                    request=request,
                    success=True,
                )

                return result

            except Exception as e:
                # Log failure
                AuditLog.log(
                    action=action,
                    user=user,
                    company=company,
                    description=description,
                    request=request,
                    success=False,
                    error_message=str(e),
                )
                raise

        return wrapper

    return decorator
