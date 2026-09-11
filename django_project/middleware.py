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
        "workspace_slug_settings_billing",
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

        # Centralized subscription evaluation.
        try:
            subscription = Subscription.objects.filter(company=workspace).first()
            if subscription is None:
                messages.warning(
                    request,
                    "No subscription found. Please set up billing to continue.",
                )
                return redirect(
                    "workspace_subscriptions:plan-list",
                    workspace_slug=workspace.slug,
                )

            decision = effective_billing_state(subscription)

            if not decision.commercially_available:
                if decision.reason == "NO_SUBSCRIPTION":
                    try:
                        current_url = resolve(request.path).url_name
                    except Exception:
                        return None

                    if (
                        current_url
                        and not current_url.startswith("subscriptions:")
                    ):
                        messages.warning(
                            request,
                            "⚠️ No active subscription found. Please set up billing to continue.",
                        )
                        return redirect(
                            "workspace_subscriptions:plan-list",
                            workspace_slug=workspace.slug,
                        )

                    return None

                messages.warning(request, decision.message or "Subscription access is unavailable.")
                return redirect(
                    "workspace_subscriptions:dashboard",
                    workspace_slug=workspace.slug,
                )

            if subscription and getattr(subscription, "end_date", None):
                days_left = (subscription.end_date - timezone.now()).days
                if 0 <= days_left <= 7:
                    messages.info(
                        request, f"Your current subscription period ends in {days_left} days. Open Billing to renew."
                    )

        except Exception:
            import logging

            logger = logging.getLogger(__name__)
            logger.exception("Subscription validation failed closed")
            return HttpResponse(
                "Subscription validation is temporarily unavailable.",
                status=503,
            )

        return None
