from django.urls import path

from . import views

app_name = "accounting"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("setup/", views.setup, name="setup"),
    path("activation/", views.activation, name="activation"),
    path("reports/", views.reports, name="reports"),
    path("transactions/create/", views.transaction_create, name="transaction_create"),
    path("vouchers/<uuid:pk>/", views.voucher_detail, name="voucher_detail"),
    path("vouchers/<uuid:pk>/authorize/", views.voucher_authorize, name="voucher_authorize"),
    path("vouchers/<uuid:pk>/post/", views.voucher_post, name="voucher_post"),
    path("vouchers/<uuid:pk>/allocate/", views.receipt_allocate, name="receipt_allocate"),
    path("vouchers/<uuid:pk>/reverse/", views.voucher_reverse, name="voucher_reverse"),
]
