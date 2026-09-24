"""Compatibility entry points for retired, non-operational preferences."""
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from apps.orgs.models import Company
from apps.orgs.web.access_helpers import _assert_workspace_access

@login_required
def workspace_preferences_redirect(request, workspace_id):
    workspace = get_object_or_404(Company, id=workspace_id)
    _assert_workspace_access(request, workspace, {"workspace_settings"})
    return redirect("workspace_slug_settings_preferences", workspace_slug=workspace.slug)

@method_decorator(login_required, name="dispatch")
class WorkspacePreferenceBuilder(TemplateView):
    """Keep old bookmarks useful without accepting ineffective settings writes."""
    template_name = "configuration/workspace_preferences.html"
    http_method_names = ["get", "head", "options"]

    def dispatch(self, request, *args, **kwargs):
        workspace_id = kwargs.get("workspace_id")
        if workspace_id is None:
            raise Http404("Workspace ID is required")
        self.workspace = get_object_or_404(Company, id=workspace_id)
        _assert_workspace_access(request, self.workspace, {"workspace_settings"})
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        return {**super().get_context_data(**kwargs), "workspace": self.workspace}
