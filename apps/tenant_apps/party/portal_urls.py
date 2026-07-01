from django.urls import path

from apps.tenant_apps.party import portal_views


urlpatterns = [
    path("", portal_views.portal_dashboard, name="customer_portal_dashboard"),
    path("loans/", portal_views.portal_loans, name="customer_portal_loans"),
    path("invoices/", portal_views.portal_invoices, name="customer_portal_invoices"),
    path("payments/", portal_views.portal_payments, name="customer_portal_payments"),
    path("documents/", portal_views.portal_documents, name="customer_portal_documents"),
    path("statements/", portal_views.portal_statements, name="customer_portal_statements"),
]
