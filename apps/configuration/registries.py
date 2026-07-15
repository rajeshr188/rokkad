from dynamic_preferences.registries import PerInstancePreferenceRegistry


class WorkspacePreferenceRegistry(PerInstancePreferenceRegistry):
    pass


workspace_preferences_registry = WorkspacePreferenceRegistry()
