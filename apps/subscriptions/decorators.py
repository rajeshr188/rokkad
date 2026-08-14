from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.orgs.tenant_context import resolve_request_workspace
from apps.subscriptions.services import SubscriptionAccessService


subscription_access_service = SubscriptionAccessService()


def subscription_feature_required(feature_code):
    """Require an active subscription entitlement for a workspace feature."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            workspace = resolve_request_workspace(
                request,
                include_public=False,
                allow_profile_fallback=False,
            )
            if workspace is None:
                messages.warning(
                    request,
                    "Select a workspace before accessing this feature.",
                )
                return redirect("workspace_list")

            decision = subscription_access_service.evaluate_access(
                user=request.user,
                workspace=workspace,
                feature_code=feature_code,
            )
            if not decision.allowed:
                messages.warning(
                    request,
                    decision.message or "This feature is not available on your current plan.",
                )
                return redirect("subscriptions:dashboard")

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
