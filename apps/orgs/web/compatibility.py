"""Compatibility; existing routes and policy remain compatible."""

from django.contrib import messages
from django.shortcuts import redirect
from django.utils import timezone

from apps.orgs.models import Membership
from apps.orgs.permissions import get_effective_permissions, is_platform_admin
from apps.orgs.tenant_context import resolve_request_workspace
from apps.subscriptions.billing import effective_billing_state


def has_permission(user, tenant, permission_codename):
    return permission_codename in get_effective_permissions(user, tenant)


def has_role(user, tenant, role_name):
    if is_platform_admin(user) and role_name == "Superuser":
        return True
    return Membership.objects.filter(
        user=user,
        company=tenant,
        role__name__iexact=role_name,
    ).exists()


def subscription_required(view_func):
    """
    Decorator to ensure workspace has active subscription.
    Redirects to subscription dashboard if subscription missing or expired.
    """

    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("account_login")

        workspace = resolve_request_workspace(request)
        if not workspace:
            return redirect("workspace_list")

        try:
            subscription = workspace.subscription
            decision = effective_billing_state(subscription)
        except Exception:
            subscription = None
            decision = None

        if decision is None or not decision.commercially_available:
            messages.warning(request, "Subscription access is unavailable.")
            return redirect(
                "workspace_subscriptions:dashboard",
                workspace_slug=workspace.slug,
            )

        if subscription and getattr(subscription, "end_date", None):
            days_left = (subscription.end_date - timezone.now()).days
            if 0 <= days_left <= 7:
                messages.warning(
                    request,
                    f"Subscription renews in {days_left} days",
                )

        return view_func(request, *args, **kwargs)

    return wrapper
