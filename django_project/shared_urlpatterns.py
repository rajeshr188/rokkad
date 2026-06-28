from django.conf.urls import i18n
from django.urls import include, path


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
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("allauth.socialaccount.urls")),
    path("invitations/", include("invitations.urls")),
]

# Authenticated global/control-plane routes. These are still included in tenant
# URLConf for compatibility until Phase 2 route separation is completed.
GLOBAL_AUTHENTICATED_URLPATTERNS = [
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
