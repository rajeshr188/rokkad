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
    path(
        "plans/<int:plan_id>/start-trial/",
        views.StartTrialView.as_view(),
        name="start-trial",
    ),
    path("checkout/<int:plan_id>/", views.CheckoutView.as_view(), name="checkout"),
    # Payments
    path("payment/order/", views.OrderView.as_view(), name="order-create"),
    path("payment/create/", views.PaymentView.as_view(), name="payment-create"),
    path("webhook/razorpay/", views.razorpay_webhook, name="razorpay-webhook"),
    # Dashboard and Billing
    path("dashboard/", views.SubscriptionDashboardView.as_view(), name="dashboard"),
    path("reviews/", views.BillingReviewListView.as_view(), name="reviews"),
    path("invoices/<int:pk>/resolve-review/", views.ResolveBillingReviewView.as_view(), name="resolve-review"),
    # Invoices
    path(
        "invoices/<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice-detail"
    ),
    path("invoices/<int:pk>/pdf/", views.InvoicePDFView.as_view(), name="invoice-pdf"),
    path("invoices/<int:pk>/reconcile/", views.ReconcileInvoiceView.as_view(), name="invoice-reconcile"),
]
