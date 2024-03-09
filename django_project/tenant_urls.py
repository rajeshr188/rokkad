from django.conf import settings
from django.conf.urls import i18n
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("i18n/", include(i18n)),
    # path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("pages.urls")),
    path("invitations/", include("invitations.urls")),
    path("orgs/", include("apps.orgs.urls")),
    path("profile/", include("accounts.urls")),
    path("contacts/", include("apps.tenant_apps.contact.urls")),
    path("girvi/", include("apps.tenant_apps.girvi.urls")),
    path("rates/", include("apps.tenant_apps.rates.urls")),
    path("products/", include("apps.tenant_apps.products.urls")),
    # path("purchase/", include("apps.tenant_apps.purchase.urls")),
    # path("sales/", include("apps.tenant_apps.sales.urls")),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns = [
        path("__debug__/", include(debug_toolbar.urls)),
    ] + urlpatterns
