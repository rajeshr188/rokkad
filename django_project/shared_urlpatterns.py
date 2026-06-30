from django.conf.urls import i18n
from django.urls import include, path
from django.views.generic import RedirectView

from apps.orgs import views as org_views


# Cross-plane service routes used by both public and tenant URLConfs.
SERVICE_URLPATTERNS = [
    path("i18n/", include(i18n)),
    path("dynamic_preferences/", include("dynamic_preferences.urls")),
    path("select2/", include("django_select2.urls")),
]

# Public/platform pages. The dashboard routes inside pages.urls still redirect
# authenticated users through the current compatibility flow.
PUBLIC_PLATFORM_URLPATTERNS = [
    path("", include("pages.urls")),
]

# Authentication and invitation entrypoints. These remain shared during the
# transition because users can arrive from public and tenant domains.
AUTH_URLPATTERNS = [
    path(
        "login/",
        RedirectView.as_view(
            pattern_name="account_login",
            permanent=False,
            query_string=True,
        ),
        name="login",
    ),
    path(
        "signup/",
        RedirectView.as_view(
            pattern_name="account_signup",
            permanent=False,
            query_string=True,
        ),
        name="signup",
    ),
    path(
        "password/reset/",
        RedirectView.as_view(
            pattern_name="account_reset_password",
            permanent=False,
            query_string=True,
        ),
        name="password_reset",
    ),
    path(
        "invitations/accept/<str:key>/",
        org_views.team_accept_invitation,
        name="public_invitation_accept",
    ),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("allauth.socialaccount.urls")),
    path("invitations/", include("invitations.urls")),
]

# Canonical SaaS control-plane aliases. These are additive aliases for the
# current orgs routes; old /orgs/... paths remain the compatibility surface.
CANONICAL_CONTROL_PLANE_URLPATTERNS = [
    path("app/", org_views.workspace_selector, name="app_dashboard"),
    path("app/workspaces/", org_views.workspace_selector, name="app_workspaces"),
    path("app/workspaces/new/", org_views.workspace_create, name="app_workspace_create"),
    path("app/invitations/", org_views.team_invitations, name="app_invitations"),
    path("app/memberships/", org_views.my_memberships, name="app_memberships"),
    path(
        "workspace/<int:workspace_id>/settings/",
        org_views.workspace_detail,
        name="workspace_settings_home",
    ),
    path(
        "workspace/<int:workspace_id>/settings/setup/",
        org_views.workspace_setup,
        name="workspace_settings_setup",
    ),
    path(
        "workspace/<int:workspace_id>/settings/setup/state/",
        org_views.workspace_setup_state,
        name="workspace_settings_setup_state",
    ),
    path(
        "workspace/<int:workspace_id>/settings/preferences/",
        org_views.CompanyPreferenceBuilder.as_view(),
        name="workspace_settings_preferences",
    ),
    path(
        "workspace/<int:workspace_id>/settings/team/",
        org_views.membership_list,
        name="workspace_settings_team",
    ),
    path(
        "workspace/<int:workspace_id>/settings/invitations/",
        org_views.companyinvitations_list,
        name="workspace_settings_invitations",
    ),
    path(
        "workspace/<int:workspace_id>/settings/invitations/new/",
        org_views.team_invite,
        name="workspace_settings_invite",
    ),
    path(
        "workspace/<int:workspace_id>/settings/leave/",
        org_views.workspace_leave,
        name="workspace_settings_leave",
    ),
]

CANONICAL_WORKSPACE_SLUG_URLPATTERNS = [
    path(
        "w/<str:workspace_slug>/",
        org_views.workspace_slug_dashboard,
        name="workspace_slug_dashboard",
    ),
    path(
        "w/<str:workspace_slug>/settings/",
        org_views.workspace_slug_settings_home,
        name="workspace_slug_settings",
    ),
    path(
        "w/<str:workspace_slug>/settings/preferences/",
        org_views.workspace_slug_settings_preferences,
        name="workspace_slug_settings_preferences",
    ),
    path(
        "w/<str:workspace_slug>/settings/team/",
        org_views.workspace_slug_settings_team,
        name="workspace_slug_settings_team",
    ),
    path(
        "w/<str:workspace_slug>/settings/invitations/",
        org_views.workspace_slug_settings_invitations,
        name="workspace_slug_settings_invitations",
    ),
    path(
        "w/<str:workspace_slug>/parties/",
        org_views.workspace_slug_parties,
        name="workspace_slug_parties",
    ),
    path(
        "w/<str:workspace_slug>/loans/",
        org_views.workspace_slug_loans,
        name="workspace_slug_loans",
    ),
    path(
        "w/<str:workspace_slug>/inventory/",
        org_views.workspace_slug_inventory,
        name="workspace_slug_inventory",
    ),
    path(
        "w/<str:workspace_slug>/accounting/",
        org_views.workspace_slug_accounting,
        name="workspace_slug_accounting",
    ),
]

# Authenticated global/control-plane routes. These are still included in tenant
# URLConf for compatibility until Phase 2 route separation is completed.
GLOBAL_AUTHENTICATED_URLPATTERNS = [
    *CANONICAL_CONTROL_PLANE_URLPATTERNS,
    *CANONICAL_WORKSPACE_SLUG_URLPATTERNS,
    path("onboarding/", include("apps.onboarding.urls")),
    path("orgs/", include("apps.orgs.urls")),
    path("profile/", include("accounts.urls")),
    path("subscriptions/", include("apps.subscriptions.urls")),
]

# Backward-compatible aggregate used by current public and tenant URLConfs.
shared_urlpatterns = (
    SERVICE_URLPATTERNS
    + PUBLIC_PLATFORM_URLPATTERNS
    + AUTH_URLPATTERNS
    + GLOBAL_AUTHENTICATED_URLPATTERNS
)
