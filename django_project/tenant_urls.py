from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django_project.shared_urlpatterns import shared_urlpatterns

TENANT_ADMIN_URLPATTERNS = [
    path("admin/", admin.site.urls),
]

# Tenant/workspace ERP routes. These should stay tenant-schema only; public and
# global control-plane routes continue to come from shared_urlpatterns below for
# compatibility until the later route split introduces explicit aliases.
TENANT_ERP_URLPATTERNS = [
    path("portal/", include("apps.tenant_apps.party.portal_urls")),
    path("party/", include("apps.tenant_apps.party.urls")),
    path("contact/", include("apps.tenant_apps.contact.urls")),
    path("data-tools/", include("apps.tenant_apps.utils.importing.urls")),
    path("girvi/", include("apps.tenant_apps.girvi.urls")),
    path("rates/", include("apps.tenant_apps.rates.urls")),
    path("product/", include("apps.tenant_apps.product.urls")),
    path("notify/", include("apps.tenant_apps.notify.urls")),
    path("notify-v2/", include("apps.tenant_apps.notify_v2.urls")),
    path("dea/", include("apps.tenant_apps.dea.urls")),
]

urlpatterns = TENANT_ADMIN_URLPATTERNS + TENANT_ERP_URLPATTERNS + shared_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
