from django.conf.urls import i18n
from django.urls import include, path


# Routes shared by both public and tenant URL configurations.
shared_urlpatterns = [
    path("i18n/", include(i18n)),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("allauth.socialaccount.urls")),
    path("dynamic_preferences/", include("dynamic_preferences.urls")),
    path("select2/", include("django_select2.urls")),
    path("", include("pages.urls")),
    path("invitations/", include("invitations.urls")),
    path("onboarding/", include("apps.onboarding.urls")),
    path("orgs/", include("apps.orgs.urls")),
    path("profile/", include("accounts.urls")),
    path("subscriptions/", include("apps.subscriptions.urls")),
]