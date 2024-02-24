from django.contrib import admin

# Register your models here.
# admin.py
from django import forms
from invitations.admin import InvitationAdmin
from .models import CompanyInvitation,Company,Membership,Role,Domain
from django_tenants.admin import TenantAdminMixin

class CompanyAdminForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'owner']  # Specify the fields you want to include


@admin.register(Company)
class CompanyAdmin(TenantAdminMixin, admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ('name','owner')
    search_fields = ['name']


admin.site.register(Membership)
admin.site.register(Role)
admin.site.register(Domain)
