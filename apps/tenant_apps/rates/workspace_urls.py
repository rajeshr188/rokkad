from django.urls import path
from apps.orgs.route_adapters import workspace_view
from .urls import urlpatterns as rate_patterns

app_name = "workspace_rates"
urlpatterns = [
    path(str(pattern.pattern).replace("ratesources/", "sources/", 1).removeprefix("rates/"),
         workspace_view(pattern.callback), name=pattern.name)
    for pattern in rate_patterns
]
