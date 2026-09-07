from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from apps.orgs.tenant_context import resolve_request_workspace
from apps.subscriptions import entitlements


def subscription_feature_required(feature_code):
    """Require an active subscription entitlement for a workspace feature."""

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            workspace = resolve_request_workspace(request, include_public=False)
            if workspace is None:
                messages.warning(
                    request,
                    "Select a workspace before accessing this feature.",
                )
                return redirect("workspace_list")

            if not entitlements.enabled(workspace, feature_code):
                messages.warning(
                    request,
                    "This feature is not available on your current plan.",
                )
                return redirect(
                    "workspace_subscriptions:dashboard",
                    workspace_slug=workspace.slug,
                )

            return view_func(request, *args, **kwargs)

        return wrapped_view

    return decorator
