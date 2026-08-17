from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.onboarding.decorators import onboarding_required
from apps.orgs.decorators_v2 import roles_required
from apps.orgs.models import Company, Membership
from apps.orgs.tenant_context import resolve_request_workspace


class HomePageView(TemplateView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return ["pages/home.html"]


class TenantPageView(TemplateView):
    template_name = "pages/tenant.html"


class PricingPageView(TemplateView):
    template_name = "pages/pricing.html"


@login_required
@onboarding_required
def Dashboard(request):
    """
    Smart landing page - routes user to appropriate destination.

    Decision tree:
    1. Has valid workspace selected -> workspace_dashboard
    2. Has memberships -> workspace_selector (choose workspace)
    3. No memberships -> workspace_create (create first workspace)
    """
    user = request.user
    selected_workspace = resolve_request_workspace(
        request,
        include_public=True,
    )
    if selected_workspace and selected_workspace.schema_name != "public":
        try:
            user.memberships.get(company=selected_workspace)
            return redirect("workspace_dashboard", workspace_id=selected_workspace.id)
        except Membership.DoesNotExist:
            if hasattr(user, "profile"):
                user.profile.workspace = None
                user.profile.save(update_fields=["workspace"])

    memberships = user.memberships.filter(
        company__lifecycle_state=Company.LifecycleState.ACTIVE
    )

    if memberships.exists():
        return redirect("workspace_selector")

    messages.info(request, "Let's create your first workspace!")
    return redirect("workspace_create")


@roles_required(["Owner", "Admin", "Member"])
def company_dashboard(request):
    """
    DEPRECATED: Use workspace_dashboard in apps.orgs.views instead.

    This view redirects to the new workspace_dashboard.
    Kept for backward compatibility with existing URL references.
    """
    workspace = resolve_request_workspace(
        request,
        include_public=True,
    )
    if workspace and workspace.schema_name == "public":
        return redirect("dashboard")

    if workspace:
        return redirect("workspace_dashboard", workspace_id=workspace.id)
    return redirect("workspace_selector")


class AboutPageView(TemplateView):
    template_name = "pages/about.html"


class PrivacyPolicy(TemplateView):
    template_name = "pages/privacy_policy.html"


class CancellationAndRefund(TemplateView):
    template_name = "pages/cancellation_and_refund.html"


class TermsAndConditions(TemplateView):
    template_name = "pages/terms_and_conditions.html"


class ContactPageView(TemplateView):
    template_name = "pages/contact.html"


class HelpPageView(TemplateView):
    template_name = "pages/help.html"


class FaqPageView(TemplateView):
    template_name = "pages/faq.html"
