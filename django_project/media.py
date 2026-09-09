"""Development media serving: business uploads require authorized app routes."""

import posixpath

from django.http import Http404
from django.views.static import serve


PUBLIC_MEDIA_PREFIXES = ("company_logos/", "profile_pictures/")


def serve_public_media(request, path, **kwargs):
    normalized = posixpath.normpath(path.replace("\\", "/")).lstrip("/")
    if not normalized.startswith(PUBLIC_MEDIA_PREFIXES):
        raise Http404
    return serve(request, path=normalized, **kwargs)
