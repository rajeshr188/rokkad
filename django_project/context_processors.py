"""
Context processors for common template variables.
These provide global context to all templates.
"""
from django.conf import settings

from apps.orgs.permissions import get_effective_permissions, get_workspace_role_name
from apps.orgs.tenant_context import (
    resolve_preferred_workspace,
    resolve_request_workspace,
)


def rehearsal_environment(request):
    """Only the opt-in rehearsal web settings install this display context."""
    return {
        "rehearsal_browser": getattr(settings, "REHEARSAL_BROWSER", False),
        "ticket_template_sandbox": getattr(settings, "TICKET_TEMPLATE_SANDBOX", False),
    }


def _resolve_workspace(request):
    return resolve_request_workspace(request, include_public=False)


def google_oauth_context(request):
    """
    Expose Google OAuth client ID from settings to templates.
    Prevents hardcoding secrets in template files.
    """
    google_client_id = settings.SOCIALACCOUNT_PROVIDERS.get("google", {}).get("CLIENT_ID", "")
    google_oauth_enabled = False

    if google_client_id:
        try:
            from allauth.socialaccount.models import SocialApp

            google_oauth_enabled = SocialApp.objects.filter(provider="google").exists()
        except Exception:
            google_oauth_enabled = False

    return {
        "GOOGLE_CLIENT_ID": google_client_id,
        "GOOGLE_OAUTH_ENABLED": google_oauth_enabled,
    }


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
    workspace = _resolve_workspace(request)
    preferred_workspace = resolve_preferred_workspace(request.user)

    in_tenant = workspace and workspace.slug != "public"

    return {
        "in_tenant": in_tenant,
        "workspace_name": workspace.name if workspace else None,
        "workspace_theme": workspace.get_theme_color()
        if hasattr(workspace, "get_theme_color")
        else None,
        "preferred_workspace": preferred_workspace,
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

    from apps.subscriptions.access_policy import workspace_activity
    from apps.orgs.permissions import is_platform_admin
    activity = getattr(request, "workspace_activity", None) or workspace_activity(workspace)
    from datetime import timedelta
    from django.utils import timezone
    access_context = {
        "workspace_activity": activity,
        "workspace_can_write": activity.can_write,
        "can_manage_workspace_billing": workspace.owner_id == request.user.pk or is_platform_admin(request.user),
        "billing_checkout_enabled": settings.BILLING_CHECKOUT_ENABLED,
        "subscription_ends_soon": activity.mode == "full" and not activity.grant and activity.until
            and timezone.now() <= activity.until <= timezone.now() + timedelta(days=7),
    }
    try:
        from apps.subscriptions.models import Subscription
        from apps.subscriptions.billing import effective_billing_state

        subscription = Subscription.objects.get(company=workspace)
        billing = effective_billing_state(subscription)

        return {
            **access_context,
            "has_active_subscription": billing.commercially_available,
            "subscription_plan": subscription.plan.name if subscription.plan else None,
            "days_until_renewal": subscription.days_until_renewal(),
            "subscription_expired": billing.recovery_only,
        }

    except Exception:
        # Subscription doesn't exist or error fetching
        return {
            **access_context,
            "has_active_subscription": False,
            "subscription_plan": None,
            "days_until_renewal": None,
            "subscription_expired": False,
        }
