"""Named Party routes carrying the Workspace selected by middleware."""

from django.urls import path

from apps.orgs.route_adapters import workspace_view

from .urls import urlpatterns as party_patterns

app_name = "workspace_party"


urlpatterns = [
    path(str(pattern.pattern), workspace_view(pattern.callback), name=pattern.name)
    for pattern in party_patterns
]
