"""
Context processors for common template variables.
These provide global context to all templates.
"""
from django.conf import settings

from apps.orgs.permissions import get_effective_permissions, get_workspace_role_name
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

    return {
        "user_permissions": get_effective_permissions(request.user, workspace),
        "user_role": get_workspace_role_name(request.user, workspace),
        "user_workspace": workspace,
    }





def navigation_config(request):
    """
    Deprecated no-op context processor.

    Sidebar navigation is currently rendered directly from
    templates/components/navigation/sidebar.html. Keep this function as a
    compatibility shim until/if dynamic navigation rendering is reintroduced.
    """
    return {}


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
