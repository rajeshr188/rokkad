from django.contrib import admin

from .models import PreferenceAuditLog, WorkspacePreferenceModel


@admin.register(WorkspacePreferenceModel)
class WorkspacePreferenceAdmin(admin.ModelAdmin):
    list_display = ("instance", "section", "name")
    readonly_fields = ("instance", "section", "name", "raw_value")
    # Retained storage is historical compatibility data, not operational settings.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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
