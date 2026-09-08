from django.urls import path
from apps.orgs.route_adapters import workspace_view
from .urls import urlpatterns as notify_patterns

app_name = "workspace_notify"
urlpatterns = [
    path(str(pattern.pattern), workspace_view(pattern.callback), name=pattern.name)
    for pattern in notify_patterns
]
