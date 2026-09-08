from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django_project.shared_urlpatterns import shared_urlpatterns
from django_project.media import serve_public_media

WORKSPACE_ADMIN_URLPATTERNS = [
    path("admin/", admin.site.urls),
]

# Shared-schema business routes. Explicit Workspace identity is established by
# /w/<slug>/ paths or a mapped domain before these views execute.
WORKSPACE_APP_URLPATTERNS = [
    path("portal/", include("apps.tenant_apps.party.portal_urls")),
    path("party/", include("apps.tenant_apps.party.urls")),
    path("contact/", include("django_project.legacy_contact_urls")),
    path("data-tools/", include("apps.tenant_apps.utils.importing.urls")),
    path("girvi/", include("django_project.legacy_girvi_urls")),
    path("loans/", include("apps.tenant_apps.loans.urls")),
    path("rates/", include("apps.tenant_apps.rates.urls")),
    path("notify/", include("django_project.legacy_notify_urls")),
    path("notify-v2/", include("apps.tenant_apps.notify_v2.urls")),
]

urlpatterns = WORKSPACE_ADMIN_URLPATTERNS + WORKSPACE_APP_URLPATTERNS + shared_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, view=serve_public_media, document_root=settings.MEDIA_ROOT)
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
