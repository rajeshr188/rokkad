"""
Context processors for common template variables.
These provide global context to all templates.
"""
from django.conf import settings
from django.contrib.auth.models import Permission
from apps.orgs.tenant_context import resolve_request_workspace


def _resolve_workspace(request):
    return resolve_request_workspace(request, include_public=False, allow_profile_fallback=True)


def google_oauth_context(request):
    """
    Expose Google OAuth client ID from settings to templates.
    Prevents hardcoding secrets in template files.
    """
    google_client_id = settings.SOCIALACCOUNT_PROVIDERS.get('google', {}).get('CLIENT_ID', '')
    return {'GOOGLE_CLIENT_ID': google_client_id}


def user_permissions(request):
    """
    Add user permissions and role information to template context.

    Makes available in all templates:
    - user_permissions: Set of permission codenames user has
    - user_role: User's role name in current workspace (Owner, Admin, Member)
    - user_workspace: Current workspace object
    """
    if not request.user.is_authenticated:
        return {
            "user_permissions": set(),
            "user_role": None,
            "user_workspace": None,
        }

    workspace = _resolve_workspace(request)
    if not workspace:
        return {
            "user_permissions": set(),
            "user_role": None,
            "user_workspace": None,
        }

    try:
        from apps.orgs.models import Membership

        membership = Membership.objects.get(user=request.user, company=workspace)

        # Get all permissions for user's role
        # This integrates with the permission system defined in models
        role = membership.role

        # Always start with the role-matrix permissions (custom string-based,
        # e.g. 'team_invite', 'workspace_edit') so sidebar gates work correctly.
        # Then union in any explicit Django Permission codenames from the DB.
        perms = _get_permissions_for_role(role.name)
        if hasattr(role, "permissions"):
            perms |= set(role.permissions.values_list("codename", flat=True))

        return {
            "user_permissions": perms,
            "user_role": role.name,
            "user_workspace": workspace,
        }

    except (Membership.DoesNotExist, AttributeError):
        return {
            "user_permissions": set(),
            "user_role": None,
            "user_workspace": workspace,
        }


def _get_permissions_for_role(role_name):
    """
    Get default permission set for a role.

    This implements the permission matrix from PERMISSION_MATRIX_GUIDE.md
    """
    role_name = role_name.lower() if role_name else ""

    # Base permissions available to all roles
    BASE_PERMS = {
        "workspace_view",
        "data_view",
        "team_view",
    }

    # Admin permissions
    ADMIN_PERMS = BASE_PERMS | {
        "workspace_edit",
        "team_invite",
        "billing_view",
        "data_edit",
        "data_export",
        "data_publish",
        # Feature-specific perms
        "girvi_loan_view",
        "sales_invoice_view",
        "purchase_invoice_view",
        "dea_journal_view",
        "contact_view",
    }

    # Owner permissions (superset of admin)
    OWNER_PERMS = ADMIN_PERMS | {
        "workspace_delete",
        "team_remove",
        "billing_edit",
        "billing_delete",
        "workspace_settings",
        # All administrative actions
        "admin_access",
    }

    # Member permissions (limited)
    MEMBER_PERMS = BASE_PERMS | {
        "data_edit",  # Can edit their own data
        # View-only access to some features
        "sales_invoice_view",
        "purchase_invoice_view",
        "contact_view",
    }

    permissions_map = {
        "owner": OWNER_PERMS,
        "admin": ADMIN_PERMS,
        "member": MEMBER_PERMS,
    }

    return permissions_map.get(role_name, BASE_PERMS)


def navigation_config(request):
    """
    Add navigation configuration to context.

    Allows templates to access navigation structure
    for rendering dynamic menus based on permissions.
    """
    from .navigation import NAVIGATION_STRUCTURE

    return {
        "navigation_config": NAVIGATION_STRUCTURE,
    }


def workspace_context(request):
    """
    Add workspace-specific context variables.

    Makes available:
    - in_tenant: Whether user is in a tenant/workspace
    - workspace_name: Current workspace name
    - workspace_theme: Theme color from workspace settings
    """
    # Get workspace from request.tenant or user profile (if authenticated)
    workspace = _resolve_workspace(request)

    in_tenant = workspace and workspace.schema_name != "public"

    return {
        "in_tenant": in_tenant,
        "workspace_name": workspace.name if workspace else None,
        "workspace_theme": workspace.get_theme_color()
        if hasattr(workspace, "get_theme_color")
        else None,
    }


def subscription_context(request):
    """
    Add subscription-related context variables.

    Makes available:
    - has_active_subscription: Whether workspace has active subscription
    - subscription_plan: Current subscription plan name
    - days_until_renewal: Days until next billing cycle
    - subscription_expired: Whether subscription is past due
    """
    if not request.user.is_authenticated:
        return {
            "has_active_subscription": False,
            "subscription_plan": None,
            "days_until_renewal": None,
            "subscription_expired": False,
        }

    workspace = _resolve_workspace(request)
    if not workspace:
        return {
            "has_active_subscription": False,
            "subscription_plan": None,
            "days_until_renewal": None,
            "subscription_expired": False,
        }

    try:
        from apps.subscriptions.models import Subscription

        subscription = Subscription.objects.get(company=workspace)

        return {
            "has_active_subscription": subscription.is_active,
            "subscription_plan": subscription.plan.name if subscription.plan else None,
            "days_until_renewal": subscription.days_until_renewal(),
            "subscription_expired": subscription.status == "past_due",
        }

    except Exception:
        # Subscription doesn't exist or error fetching
        return {
            "has_active_subscription": False,
            "subscription_plan": None,
            "days_until_renewal": None,
            "subscription_expired": False,
        }
