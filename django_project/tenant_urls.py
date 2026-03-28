from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from django_project.shared_urlpatterns import shared_urlpatterns

urlpatterns = [
    path("admin/", admin.site.urls),
    path("contact/", include("apps.tenant_apps.contact.urls")),
    path("girvi/", include("apps.tenant_apps.girvi.urls")),
    path("rates/", include("apps.tenant_apps.rates.urls")),
    path("product/", include("apps.tenant_apps.product.urls")),
    path("notify/", include("apps.tenant_apps.notify.urls")),
    path("dea/", include("apps.tenant_apps.dea.urls")),
    path("purchase/", include("apps.tenant_apps.purchase.urls")),
    path("sales/", include("apps.tenant_apps.sales.urls")),
    path("approval/", include("apps.tenant_apps.approval.urls")),
] + shared_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
