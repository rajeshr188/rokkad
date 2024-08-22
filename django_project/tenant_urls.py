from django.conf import settings
from django.conf.urls import i18n
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("i18n/", include(i18n)),
    # path("admin/", admin.site.urls),
    path("select2/", include("django_select2.urls")),
    path("", include("pages.urls")),
    path("orgs/", include("apps.orgs.urls")),
    path("profile/", include("accounts.urls")),
    path("accounts/", include("allauth.urls")),
    path("accounts/", include("allauth.socialaccount.urls")),
    # path("activity/", include("actstream.urls")),
    path("dynamic_preferences/", include("dynamic_preferences.urls")),
    path("contact/", include("apps.tenant_apps.contact.urls")),
    path("girvi/", include("apps.tenant_apps.girvi.urls")),
    path("rates/", include("apps.tenant_apps.rates.urls")),
    path("product/", include("apps.tenant_apps.product.urls")),
    path("notify/", include("apps.tenant_apps.notify.urls")),
    path("dea/", include("apps.tenant_apps.dea.urls")),
    path("purchase/", include("apps.tenant_apps.purchase.urls")),
    path("sales/", include("apps.tenant_apps.sales.urls")),
    path("approval/", include("apps.tenant_apps.approval.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
