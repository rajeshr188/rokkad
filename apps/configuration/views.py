from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from dynamic_preferences.views import PreferenceFormView

from apps.orgs.models import Company, Membership

from .forms import workspace_preference_form_builder
from .registries import workspace_preferences_registry


def _can_edit_workspace_preferences(user, workspace):
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return Membership.objects.filter(
        user=user,
        company=workspace,
        role__name__in=["Owner", "Admin"],
    ).exists()


@login_required
def workspace_preferences_redirect(request, workspace_id):
    workspace = get_object_or_404(Company, id=workspace_id, is_deleted=False)
    if not _can_edit_workspace_preferences(request.user, workspace):
        raise Http404("Workspace preferences not found")
    return redirect("workspace_settings_preferences", workspace_id=workspace.id)


@method_decorator(login_required, name="dispatch")
class WorkspacePreferenceBuilder(PreferenceFormView):
    template_name = "configuration/workspace_preferences.html"
    title = "Workspace Configuration"

    def dispatch(self, request, *args, **kwargs):
        workspace_id = kwargs.get("workspace_id")
        if workspace_id is None:
            raise Http404("Workspace ID is required")

        self.workspace = get_object_or_404(Company, id=workspace_id, is_deleted=False)
        if not _can_edit_workspace_preferences(request.user, self.workspace):
            raise Http404("Workspace preferences not found")
        return super().dispatch(request, *args, **kwargs)

    def get_section(self):
        return self.request.GET.get("section") or None

    def get_success_url(self):
        section = self.get_section()
        base_url = reverse(
            "workspace_settings_preferences",
            kwargs={"workspace_id": self.workspace.id},
        ).url
        if section:
            return f"{base_url}?section={section}"
        return base_url

    def get_form_class(self):
        section = self.get_section()
        preferences = []
        if section and section in workspace_preferences_registry:
            preferences = list(workspace_preferences_registry[section].values())

        return workspace_preference_form_builder(
            instance=self.workspace,
            Preferences=preferences,
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["workspace"] = self.workspace
        context["workspace_id"] = self.workspace.id
        context["current_section"] = self.get_section()
        context["sections"] = [
            {
                "name": section,
                "obj": workspace_preferences_registry.section_objects.get(section),
            }
            for section in workspace_preferences_registry.sections()
        ]
        context["legacy_preferences_url"] = reverse(
            "workspace_preferences",
            kwargs={"workspace_id": self.workspace.id},
        )
        return context
