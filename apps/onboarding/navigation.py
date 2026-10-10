"""Unsigned setup navigation; never an authority or a business preference."""
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

from django.shortcuts import redirect
from django.urls import reverse

SETUP_STEPS = ("business", "starting", "license", "lending", "terms", "review")
SETUP_PATHS = ("new", "paper", "import")


def setup_navigation(request):
    workspace = getattr(request, "workspace", None)
    if workspace is None:
        return None
    values = request.POST if request.method == "POST" else request.GET
    step = values.get("setup_step")
    if step not in SETUP_STEPS:
        return None
    path = values.get("setup_path", "new")
    if path not in SETUP_PATHS:
        path = "new"
    url = reverse("workspace_slug_settings_setup", kwargs={"workspace_slug": workspace.slug})
    return {"step": step, "path": path, "return_url": url + "?" + urlencode({"step": step, "path": path})}


def setup_link(request, url, step=None):
    navigation = setup_navigation(request)
    if navigation is None:
        return url
    parts = urlsplit(url)
    values = dict(parse_qsl(parts.query))
    values.update(setup_step=step or navigation["step"], setup_path=navigation["path"])
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(values), parts.fragment))


def setup_saved_redirect(request, *, step):
    """Return only to the current Workspace's canonical setup URL after a save."""
    navigation = setup_navigation(request)
    if navigation is None:
        return None
    url = reverse("workspace_slug_settings_setup", kwargs={"workspace_slug": request.workspace.slug})
    return redirect(url + "?" + urlencode({"step": step, "path": navigation["path"]}))
