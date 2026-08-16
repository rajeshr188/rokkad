from django.contrib.messages import get_messages
from django.template.loader import render_to_string
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import resolve
from django.utils import timezone
from django.contrib import messages
from apps.orgs.tenant_context import resolve_request_workspace
from apps.subscriptions.services import SubscriptionAccessService


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


subscription_access_service = SubscriptionAccessService()


class SubscriptionValidationMiddleware(MiddlewareMixin):
    """
    Validates that user's workspace has an active subscription before
    allowing access to tenant-specific features.

    Redirects to subscription/billing page if:
    - Subscription is inactive/expired
    - Workspace has no subscription
    - Subscription is past due
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
    ]

    def _resolve_workspace(self, request):
        return resolve_request_workspace(request, include_public=True)

    def process_request(self, request):
        """Check subscription before processing request"""

        # Skip for unauthenticated users
        if not request.user.is_authenticated:
            return None

        # Skip for exempt URLs
        try:
            current_url = resolve(request.path).url_name
            if current_url in self.EXEMPT_URLS or (
                current_url and current_url.startswith("admin:")
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
        if workspace.schema_name == "public":
            return None

        # Centralized subscription evaluation.
        try:
            decision = subscription_access_service.evaluate_access(
                user=request.user,
                workspace=workspace,
            )

            if not decision.allowed:
                if decision.reason == "NO_SUBSCRIPTION":
                    try:
                        current_url = resolve(request.path).url_name
                    except Exception:
                        return None

                    if (
                        current_url
                        and not current_url.startswith("subscriptions:")
                        and "tenant" in request.path.lower()
                    ):
                        messages.warning(
                            request,
                            "⚠️ No active subscription found. Please set up billing to continue.",
                        )
                        return redirect("subscriptions:plan-list")

                    return None

                messages.warning(request, decision.message or "Subscription access is unavailable.")
                return redirect("subscriptions:dashboard")

            subscription = decision.subscription
            if subscription and getattr(subscription, "end_date", None):
                days_left = (subscription.end_date - timezone.now()).days
                if 0 <= days_left <= 7:
                    messages.info(
                        request, f"Your subscription will renew in {days_left} days."
                    )

        except Exception as e:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Subscription validation error: {str(e)}")
            return None

        return None
