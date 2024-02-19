from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls import i18n

urlpatterns = [
    path('i18n/', include(i18n)),
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("pages.urls")),
    path("invitations/", include("invitations.urls")),
    path("orgs/", include("apps.orgs.urls")),
    path("profile/", include("accounts.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
