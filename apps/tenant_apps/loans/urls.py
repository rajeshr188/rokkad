from django.urls import path

from apps.tenant_apps.loans import views

app_name = "loans"

urlpatterns = [
    path("internal/", views.pawn_loan_list, name="pawn_loan_list"),
    path("internal/create/", views.pawn_loan_create, name="pawn_loan_create"),
    path("internal/<int:pk>/", views.pawn_loan_detail, name="pawn_loan_detail"),
    path("internal/<int:pk>/edit/", views.pawn_loan_update, name="pawn_loan_update"),
    path("setup/", views.license_list, name="license_list"),
    path("setup/licenses/create/", views.license_create, name="license_create"),
    path("setup/licenses/<int:pk>/", views.license_detail, name="license_detail"),
    path("setup/licenses/<int:pk>/edit/", views.license_update, name="license_update"),
    path("setup/licenses/<int:pk>/expire/", views.license_expire, name="license_expire"),
    path("setup/licenses/<int:pk>/activate/", views.license_activate, name="license_activate"),
    path("setup/licenses/<int:license_pk>/series/create/", views.series_create, name="series_create"),
    path("setup/series/<int:pk>/edit/", views.series_update, name="series_update"),
]
