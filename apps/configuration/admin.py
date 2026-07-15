from django.contrib import admin
from dynamic_preferences.admin import PerInstancePreferenceAdmin

from .models import PreferenceAuditLog, WorkspacePreferenceModel


@admin.register(WorkspacePreferenceModel)
class WorkspacePreferenceAdmin(PerInstancePreferenceAdmin):
    pass


@admin.register(PreferenceAuditLog)
class PreferenceAuditLogAdmin(admin.ModelAdmin):
    list_display = ("scope", "key", "workspace", "subject_user", "changed_by", "created_at")
    list_filter = ("scope", "created_at")
    search_fields = ("key", "workspace__name", "subject_user__email", "changed_by__email")
    readonly_fields = (
        "scope",
        "key",
        "old_value",
        "new_value",
        "workspace",
        "subject_user",
        "changed_by",
        "created_at",
    )

    def has_add_permission(self, request):
        return False
