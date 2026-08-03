from django.urls import path

from apps.tenant_apps.loans import views

app_name = "loans"

urlpatterns = [
    path("internal/", views.pawn_loan_list, name="pawn_loan_list"),
    path("internal/create/", views.pawn_loan_create, name="pawn_loan_create"),
    path("internal/<int:pk>/", views.pawn_loan_detail, name="pawn_loan_detail"),
    path("internal/<int:pk>/edit/", views.pawn_loan_update, name="pawn_loan_update"),
    path("internal/<int:pk>/approve/", views.pawn_loan_approve, name="pawn_loan_approve"),
    path("internal/<int:pk>/reopen/", views.pawn_loan_reopen, name="pawn_loan_reopen"),
    path("internal/<int:pk>/cancel/", views.pawn_loan_cancel, name="pawn_loan_cancel"),
    path("internal/<int:pk>/disburse/", views.pawn_loan_disburse, name="pawn_loan_disburse"),
    path("internal/<int:pk>/repay/", views.pawn_loan_repay, name="pawn_loan_repay"),
    path("internal/<int:pk>/accrue/", views.pawn_loan_accrue, name="pawn_loan_accrue"),
    path("internal/<int:pk>/capitalize/", views.pawn_loan_capitalize, name="pawn_loan_capitalize"),
    path("internal/<int:pk>/release/full/", views.pawn_loan_release_full, name="pawn_loan_release_full"),
    path("internal/<int:pk>/release/partial/", views.pawn_loan_release_partial, name="pawn_loan_release_partial"),
    path("internal/<int:pk>/events/<int:event_pk>/reverse/", views.pawn_loan_reverse_event, name="pawn_loan_reverse_event"),
    path("internal/<int:pk>/transfer-setup/", views.pawn_loan_transfer_setup, name="pawn_loan_transfer_setup"),
    path("internal/outbox/<int:pk>/retry/", views.pawn_outbox_retry, name="pawn_outbox_retry"),
    path("setup/", views.license_list, name="license_list"),
    path("setup/licenses/create/", views.license_create, name="license_create"),
    path("setup/licenses/<int:pk>/", views.license_detail, name="license_detail"),
    path("setup/licenses/<int:pk>/edit/", views.license_update, name="license_update"),
    path("setup/licenses/<int:pk>/expire/", views.license_expire, name="license_expire"),
    path("setup/licenses/<int:pk>/activate/", views.license_activate, name="license_activate"),
    path("setup/licenses/<int:license_pk>/series/create/", views.series_create, name="series_create"),
    path("setup/series/<int:pk>/edit/", views.series_update, name="series_update"),
]
