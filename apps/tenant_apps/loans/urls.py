from django.urls import path

from apps.tenant_apps.loans import views

app_name = "loans"

urlpatterns = [
    path("setup/", views.license_list, name="license_list"),
    path("setup/licenses/create/", views.license_create, name="license_create"),
    path("setup/licenses/<int:pk>/", views.license_detail, name="license_detail"),
    path("setup/licenses/<int:pk>/edit/", views.license_update, name="license_update"),
    path("setup/licenses/<int:pk>/expire/", views.license_expire, name="license_expire"),
    path("setup/licenses/<int:pk>/activate/", views.license_activate, name="license_activate"),
    path("setup/licenses/<int:license_pk>/series/create/", views.series_create, name="series_create"),
    path("setup/series/<int:pk>/edit/", views.series_update, name="series_update"),
]
