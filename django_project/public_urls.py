import environ
from django.conf import settings
from django.conf.urls import i18n
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

env = environ.Env()
environ.Env.read_env()

urlpatterns = [
    path("i18n/", include(i18n)),
    path(env("SECRET_ADMIN_URL") + "/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("allauth.socialaccount.urls")),
    path("select2/", include("django_select2.urls")),
    path("invitations/", include("invitations.urls")),
    path("orgs/", include("apps.orgs.urls")),
    path("profile/", include("accounts.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
