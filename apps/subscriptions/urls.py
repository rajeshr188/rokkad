"""
URL routing for subscription app.
Handles plans, checkout, payments, and invoices.
"""

from django.urls import path
from . import views

app_name = "subscriptions"

urlpatterns = [
    # Plans and Subscriptions
    path("plans/", views.SubscriptionPlanListView.as_view(), name="plan-list"),
    path("checkout/<int:plan_id>/", views.CheckoutView.as_view(), name="checkout"),
    # Payments
    path("payment/create/", views.PaymentView.as_view(), name="payment-create"),
    path("webhook/razorpay/", views.razorpay_webhook, name="razorpay-webhook"),
    # Dashboard and Billing
    path("dashboard/", views.SubscriptionDashboardView.as_view(), name="dashboard"),
    # Invoices
    path(
        "invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice-detail"
    ),
    path("invoices/<int:pk>/pdf/", views.InvoicePDFView.as_view(), name="invoice-pdf"),
]
