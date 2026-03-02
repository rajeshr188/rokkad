from django.urls import path

from .views import (
    HomePageView,
    TenantPageView,
    AboutPageView,
    PrivacyPolicy,
    CancellationAndRefund,
    TermsAndConditions,
    ContactPageView,
    HelpPageView,
    FaqPageView,
    Dashboard,
    company_dashboard,  # DEPRECATED - kept for backward compatibility
    maxx_files_upload,
    download_template_pack,
)

# Import workspace views from apps.orgs
from apps.orgs.views import workspace_selector, workspace_select, team_invitations

urlpatterns = [
    path("", HomePageView.as_view(), name="home"),
    path("about/", AboutPageView.as_view(), name="about"),
    path("tenant/", TenantPageView.as_view(), name="tenant"),
    path("privacy-policy/", PrivacyPolicy.as_view(), name="privacy_policy"),
    path(
        "cancellation-and-refund/",
        CancellationAndRefund.as_view(),
        name="cancellation_and_refund",
    ),
    path(
        "terms-and-conditions/",
        TermsAndConditions.as_view(),
        name="terms_and_conditions",
    ),
    path("contact/", ContactPageView.as_view(), name="contact"),
    path("help/", HelpPageView.as_view(), name="help"),
    path("faq/", FaqPageView.as_view(), name="faq"),
    # Main dashboard router (smart landing)
    path("dashboard/", Dashboard, name="dashboard"),
    # DEPRECATED - old company_dashboard URL kept for backward compatibility
    path("company_dashboard/", company_dashboard, name="company_dashboard"),
    # Workspace views (imported from apps.orgs - these are the correct patterns)
    path(
        "workspace/", workspace_selector, name="workspace_home"
    ),  # Main workspace selector
    path(
        "invitations/", team_invitations, name="workspace_invitations"
    ),  # Team invitations
    path(
        "workspace/<int:workspace_id>/select/",
        workspace_select,
        name="workspace_select",
    ),  # Select workspace
    # Utility views
    path("maxxupload/", maxx_files_upload, name="maxx_upload"),
    path("download-templates/", download_template_pack, name="download_template_pack"),
]
