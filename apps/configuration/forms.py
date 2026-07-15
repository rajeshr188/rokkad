from dynamic_preferences.forms import (
    PreferenceForm,
    SinglePerInstancePreferenceForm,
    preference_form_builder,
)

from .models import WorkspacePreferenceModel
from .registries import workspace_preferences_registry


class WorkspaceSinglePreferenceForm(SinglePerInstancePreferenceForm):
    class Meta:
        model = WorkspacePreferenceModel
        fields = SinglePerInstancePreferenceForm.Meta.fields


class WorkspacePreferenceForm(PreferenceForm):
    registry = workspace_preferences_registry


def workspace_preference_form_builder(instance, Preferences=None, **kwargs):
    return preference_form_builder(
        WorkspacePreferenceForm,
        Preferences or [],
        instance=instance,
        **kwargs,
    )
