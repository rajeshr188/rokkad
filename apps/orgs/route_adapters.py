"""Adapters for existing business views under explicit Workspace URLs."""

from functools import wraps

from django.http import Http404


def workspace_view(view):
    @wraps(view)
    def dispatch(request, workspace_slug, *args, **kwargs):
        workspace = getattr(request, "workspace", None)
        if workspace is None or workspace.slug != workspace_slug:
            raise Http404
        return view(request, *args, **kwargs)

    return dispatch


