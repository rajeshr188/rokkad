# Register your models here.
# admin.py
from django import forms
from django.contrib import admin
from django.contrib import messages

from .models import AuditLog, Company, Domain, Membership, Role


class PublicTenantOnlyMixin:
    """Allow Access to Public Tenant Only."""

    def _only_public_tenant_access(self, request):
        return getattr(request, "workspace", None) is None

    def has_view_permission(self, request, view=None):
        return self._only_public_tenant_access(request)

    def has_add_permission(self, request, view=None):
        return self._only_public_tenant_access(request)

    def has_change_permission(self, request, view=None):
        return self._only_public_tenant_access(request)

    def has_delete_permission(self, request, view=None):
        return self._only_public_tenant_access(request)

    def has_view_or_change_permission(self, request, view=None):
        return self._only_public_tenant_access(request)


class SoftDeletedFilter(admin.SimpleListFilter):
    title = "soft deleted"
    parameter_name = "is_deleted"

    def lookups(self, request, model_admin):
        return (
            ("yes", "Yes"),
            ("no", "No"),
        )

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(is_deleted=True)
        if self.value() == "no":
            return queryset.filter(is_deleted=False)
        return queryset


class CompanyAdminForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = [
            "name",
            "owner",
            "theme",
            "logo",
        ]  # Specify the fields you want to include


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ("name", "owner", "theme", "logo", "is_deleted")
    search_fields = ["name"]
    list_filter = ["owner", SoftDeletedFilter]
    actions = ["restore_companies", "hard_delete_companies"]

    def get_queryset(self, request):
        # Use the all_objects manager to include soft-deleted instances
        return self.model.all_objects.all()

    def restore_companies(self, request, queryset):
        restored_count = 0
        for company in queryset:
            if company.is_deleted:
                company.restore()
                restored_count += 1

        self.message_user(
            request,
            f"Restored {restored_count} workspace(s).",
            level=messages.SUCCESS,
        )

    restore_companies.short_description = "Restore selected companies"

    def hard_delete_companies(self, request, queryset):
        deleted_count = 0
        blocked_count = 0
        for company in queryset:
            try:
                company.hard_delete()
                deleted_count += 1
            except ValueError as exc:
                blocked_count += 1
                self.message_user(
                    request,
                    f"Skipped hard delete for {company.name}: {exc}",
                    level=messages.WARNING,
                )

        if deleted_count:
            self.message_user(
                request,
                f"Hard-deleted {deleted_count} workspace(s).",
                level=messages.SUCCESS,
            )
        if blocked_count and not deleted_count:
            self.message_user(
                request,
                "No workspaces were hard-deleted.",
                level=messages.WARNING,
            )

    hard_delete_companies.short_description = "Permanently delete selected companies"


# app = apps.get_app_config('orgs')
# for model_name, model in app.models.items():
#     admin.site.register(model, CompanyAdmin)

# @admin.register(CompanyInvitation)
# class CompanyInvitationAdmin(PublicTenantOnlyMixin,TenantAdminMixin,InvitationAdmin):
#     pass


admin.site.register(Membership)
admin.site.register(Role)
admin.site.register(Domain)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Read-only admin for audit logs"""

    list_display = (
        "timestamp",
        "action",
        "user",
        "company",
        "success",
        "ip_address",
        "description",
    )
    list_filter = ("action", "success", "timestamp", "company")
    search_fields = ("user__email", "user__username", "description", "ip_address")
    readonly_fields = (
        "timestamp",
        "action",
        "user",
        "company",
        "content_type",
        "object_id",
        "description",
        "ip_address",
        "user_agent",
        "success",
        "data",
    )
    date_hierarchy = "timestamp"
    ordering = ("-timestamp",)

    def has_add_permission(self, request):
        # Audit logs should only be created programmatically
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of audit logs (compliance requirement)
        return False

    def has_change_permission(self, request, obj=None):
        # Audit logs are immutable
        return False
