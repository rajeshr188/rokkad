from django.contrib import admin

# Register your models here.
# admin.py
from django import forms
from invitations.admin import InvitationAdmin
from .models import CompanyInvitation,Company,Membership,Role

admin.site.register(Membership)

class CompanyAdminForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ['name', 'owner']  # Specify the fields you want to include


class CompanyAdmin(admin.ModelAdmin):
    form = CompanyAdminForm
    list_display = ('name', 'owner')
    search_fields = ['name']


admin.site.register(Company, CompanyAdmin)

admin.site.register(Role)
