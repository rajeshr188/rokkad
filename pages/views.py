from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.generic import TemplateView

from apps.orgs.decorators_v2 import roles_required
from apps.orgs.models import Company, Membership
from apps.orgs.tenant_context import resolve_request_workspace, resolve_preferred_workspace


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
def Dashboard(request):
    """
    Smart landing page - routes user to appropriate destination.

    Decision tree:
    1. Valid remembered Workspace -> its explicit dashboard.
    2. Exactly one active membership -> its explicit dashboard.
    3. Otherwise -> Workspace list, including incoming invitations.
    """
    user = request.user
    selected_workspace = resolve_request_workspace(request) or resolve_preferred_workspace(user)
    if selected_workspace:
        return redirect("workspace_slug_dashboard", workspace_slug=selected_workspace.slug)
    memberships = list(user.memberships.select_related("company").filter(
        company__lifecycle_state=Company.LifecycleState.ACTIVE,
    )[:2])
    if len(memberships) == 1:
        return redirect("workspace_slug_dashboard", workspace_slug=memberships[0].company.slug)
    # The chooser also exposes incoming invitations for users with no Workspace.
    return redirect("workspace_selector")


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
    if workspace and workspace.slug == "public":
        return redirect("dashboard")

    if workspace:
        return redirect(
            "workspace_slug_dashboard",
            workspace_slug=workspace.slug,
        )
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
