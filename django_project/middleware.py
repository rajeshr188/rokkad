from django.contrib.messages import get_messages
from django.template.loader import render_to_string
from django.utils.deprecation import MiddlewareMixin
from django.shortcuts import redirect
from django.urls import resolve
from django.utils import timezone
from django.contrib import messages
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
        "orgs_company_create",
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

    def process_request(self, request):
        """Check subscription before processing request"""

        # Skip for unauthenticated users
        if not request.user.is_authenticated:
            return None

        # Skip for exempt URLs
        try:
            current_url = resolve(request.path).url_name
            if current_url in self.EXEMPT_URLS or current_url.startswith("admin:"):
                return None
        except:
            pass

        # Skip static/media files
        if request.path.startswith(("/static/", "/media/", "/admin/", "/__debug__/")):
            return None

        # Check if user has a workspace selected
        workspace = request.user.profile.workspace
        if not workspace:
            return None

        # Skip public schema
        if workspace.schema_name == "public":
            return None

        # Check subscription
        try:
            subscription = workspace.subscription

            # Check if active
            if not subscription.is_active:
                messages.warning(
                    request,
                    "⚠️ Your subscription has expired. Please renew to continue using this workspace.",
                )
                return redirect("subscriptions:dashboard")

            # Check if past due
            if subscription.status == "past_due":
                messages.warning(
                    request,
                    "⚠️ Payment is overdue. Please update your billing information.",
                )
                return redirect("subscriptions:dashboard")

            # Warn if ending soon (7 days or less)
            if subscription.end_date:
                days_left = (subscription.end_date - timezone.now()).days
                if 0 <= days_left <= 7:
                    messages.info(
                        request, f"Your subscription will renew in {days_left} days."
                    )

        except Subscription.DoesNotExist:
            # No subscription attached to workspace yet
            # Allow user to navigate to plans/checkout to create one
            # Only block tenant-specific features
            try:
                current_url = resolve(request.path).url_name
            except:
                return None

            # If accessing tenant-specific data (not billing/plan pages), redirect
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

        except AttributeError:
            # Workspace exists but doesn't have subscription attribute
            # This shouldn't happen, but allow request to proceed
            return None

        except Exception as e:
            # Log error but don't block request
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Subscription validation error: {str(e)}")
            return None

        return None
