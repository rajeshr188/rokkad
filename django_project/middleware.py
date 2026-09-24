from django.contrib.messages import get_messages
from django.template.loader import render_to_string
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import resolve
from django.utils import timezone
from django.contrib import messages
from django.http import HttpResponse
from apps.orgs.tenant_context import resolve_request_workspace
from apps.subscriptions.billing import effective_billing_state
from apps.subscriptions.models import Subscription


class HtmxMessagesMiddleware(MiddlewareMixin):
    """
    Middleware that moves messages into the HX-Trigger header when request is made with HTMX
    """

    def process_response(self, request, response):
        # The HX-Request header indicates that the request was made with HTMX
        if "HX-Request" not in request.headers:
            return response

        # Ignore HTTP redirections because HTMX cannot read the body
        if 300 <= response.status_code < 400:
            return response

        # Ignore client-side redirection because HTMX drops OOB swaps
        if "HX-Redirect" in response.headers:
            return response

        # Extract the messages
        messages_list = get_messages(request)
        if not messages_list:
            return response

        response.write(
            render_to_string(
                template_name="toasts.html",
                context={"messages": messages_list},
                request=request,
            )
        )

        return response


class SubscriptionValidationMiddleware(MiddlewareMixin):
    """Apply commercial activity policy after Workspace/RLS resolution.

    Billing recovery keeps its own authorization. Read-only access permits
    reviewed reads/exports and explains unavailable actions without redirecting staff.
    """

    # URLs that don't require subscription check
    EXEMPT_URLS = [
        "account_login",
        "account_logout",
        "account_signup",
        "home",
        "dashboard",
        "workspace_home",
        "user_workspaces",
        "workspace_invitations",
        "workspace_select",
        "workspace_create",
        "workspace_list",
        "onboarding_start",
        "onboarding_profile",
        "onboarding_company",
        "onboarding_team",
        "onboarding_tour",
        "onboarding_complete",
        "onboarding_skip",
        "admin:index",
        "admin:login",
        # Subscription URLs (exempt from subscription check)
        "subscriptions:plan-list",  # view available plans
        "subscriptions:checkout",  # checkout page
        "subscriptions:payment-create",  # process payment
        "subscriptions:dashboard",  # billing dashboard
        "subscriptions:razorpay-webhook",  # payment webhook
        "subscriptions:invoice-detail",  # view invoice
        "subscriptions:invoice-pdf",  # download invoice PDF
        "workspace_slug_settings_billing",
        "workspace_portability:export",  # Authorized partial export survives paid expiry.
    ]

    def _resolve_workspace(self, request):
        return resolve_request_workspace(request, include_public=True)

    def process_request(self, request):
        """Check subscription before processing request"""

        # Skip for unauthenticated users
        if not request.user.is_authenticated:
            return None

        # Skip for exempt URLs
        current_view = ""
        try:
            resolved = resolve(request.path)
            current_url = resolved.url_name
            current_view = resolved.view_name
            if (
                current_url in self.EXEMPT_URLS
                or current_view in self.EXEMPT_URLS
                or current_view.startswith("subscriptions:")
                or current_view.startswith("workspace_subscriptions:")
                or current_view.startswith("admin:")
                or current_view in {
                    "workspace_notify:notify_v2_whatsapp_cloud_webhook",
                    "notify_v2_whatsapp_cloud_webhook",
                }
            ):
                return None
        except Exception:
            pass

        # Skip static/media files
        if request.path.startswith(("/static/", "/media/", "/admin/", "/__debug__/")):
            return None

        # Check if user has a workspace selected
        workspace = self._resolve_workspace(request)
        if not workspace:
            return None

        # Skip public schema
        if workspace.slug == "public":
            return None

        # Commercial activity is separate from the truthful billing status.
        try:
            from apps.subscriptions.access_policy import workspace_activity
            from apps.subscriptions.route_policy import read_route_allowed
            from django.shortcuts import render
            decision = workspace_activity(workspace)
            request.workspace_activity = decision
            if decision.can_write:
                return None
            if decision.mode == "read_only" and read_route_allowed(current_view, request.method):
                return None
            if decision.mode == "recovery" and workspace.owner_id == request.user.pk:
                return redirect("workspace_subscriptions:plan-list", workspace_slug=workspace.slug)
            return render(request, "subscriptions/access_restricted.html", {"activity": decision}, status=403)
        except Exception:
            import logging
            logging.getLogger(__name__).exception("Subscription validation failed closed")
            return HttpResponse("Subscription validation is temporarily unavailable.", status=503)
