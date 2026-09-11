from django import forms
from django.contrib import admin

from .models import Rate, RateSource


# Register your models here.
class RateSourceAdminForm(forms.ModelForm):
    class Meta:
        model = RateSource
        fields = "__all__"


class RateSourceAdmin(admin.ModelAdmin):
    form = RateSourceAdminForm
    list_display = [
        "name",
        "location",
        "tax_included",
    ]


admin.site.register(RateSource, RateSourceAdmin)


class RateAdminForm(forms.ModelForm):
    class Meta:
        model = Rate
        fields = "__all__"


class RateAdmin(admin.ModelAdmin):
    form = RateAdminForm
    list_display = [
        "rate_source",
        "timestamp",
        "metal",
        "purity",
        "buying_rate",
        "selling_rate",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


admin.site.register(Rate, RateAdmin)
