"""Named Party routes carrying the Workspace selected by middleware."""

from functools import wraps

from django.http import Http404
from django.urls import path

from .urls import urlpatterns as party_patterns

app_name = "workspace_party"


def workspace_view(view):
    @wraps(view)
    def dispatch(request, workspace_slug, *args, **kwargs):
        workspace = getattr(request, "workspace", None)
        if workspace is None or workspace.slug != workspace_slug:
            raise Http404
        return view(request, *args, **kwargs)

    return dispatch


urlpatterns = [
    path(str(pattern.pattern), workspace_view(pattern.callback), name=pattern.name)
    for pattern in party_patterns
]
