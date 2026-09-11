"""Canonical Loans routes under explicit Workspace identity."""
from django.urls import path
from apps.orgs.route_adapters import workspace_view
from .urls import urlpatterns as loan_patterns

app_name = "workspace_loans"

urlpatterns = [
    path(str(pattern.pattern), workspace_view(pattern.callback), name=pattern.name)
    for pattern in loan_patterns
]
