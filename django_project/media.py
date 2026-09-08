"""Public development media excludes private notification artifacts."""

import posixpath

from django.http import Http404
from django.views.static import serve


def serve_public_media(request, path, **kwargs):
    normalized = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
    if normalized == "notify_v2/artifacts" or normalized.startswith("notify_v2/artifacts/"):
        raise Http404
    return serve(request, path=path, **kwargs)
