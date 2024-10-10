# Register your models here.
# admin.py
from django import forms
from django.apps import apps
from django.contrib import admin
from django_tenants.admin import TenantAdminMixin
from django_tenants.utils import get_public_schema_name
from invitations.admin import InvitationAdmin

from .models import Company, CompanyInvitation, Domain, Membership, Role


class PublicTenantOnlyMixin:
    """Allow Access to Public Tenant Only."""

    def _only_public_tenant_access(self, request):
        return True if request.tenant.schema_name == get_public_schema_name() else False

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
class CompanyAdmin(TenantAdminMixin, admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ("name", "owner", "theme", "logo")
    search_fields = ["name"]
    list_filter = ["owner"]


# app = apps.get_app_config('orgs')
# for model_name, model in app.models.items():
#     admin.site.register(model, CompanyAdmin)

# @admin.register(CompanyInvitation)
# class CompanyInvitationAdmin(PublicTenantOnlyMixin,TenantAdminMixin,InvitationAdmin):
#     pass


admin.site.register(Membership)
admin.site.register(Role)
admin.site.register(Domain)
