from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import ProductVariant

from .forms import LoanForm
from .models import License, Loan, LoanItem, LoanPayment, Release, Series
from .resources import (LicenseResource, LoanItemResource, LoanPaymentResource,
                        LoanResource, ReleaseResource)


class LicenseAdminForm(forms.ModelForm):
    class Meta:
        model = License
        fields = "__all__"


class LicenseAdmin(admin.ModelAdmin):
    form = LicenseAdminForm
    resource_class = LicenseResource
    list_display = [
        "name",
        "id",
        "created",
        "updated",
        "type",
        "shopname",
        "address",
        "phonenumber",
        "propreitor",
        "renewal_date",
    ]


class SeriesAdminForm(forms.ModelForm):
    class Meta:
        model = Series
        fields = "__all__"


class SeriesAdmin(admin.ModelAdmin):
    form = SeriesAdminForm
    list_display = [
        "id",
        "name",
        "created",
    ]


class LoanAdminForm(forms.ModelForm):
    date_heirarchy = "created"
    list_filter = ("customer", "series")

    class Meta:
        model = Loan
        fields = "__all__"


# class LoanAdmin(ImportExportModelAdmin):
class LoanAdmin(admin.ModelAdmin):
    form = LoanAdminForm
    resource_class = LoanResource
    list_display = [
        "id",
        "loan_id",
        "customer",
        "series",
        "loan_date",
        "item_desc",
        "loan_amount",
    ]
    search_fields = ["customer__name", "series"]
    autocomplete_fields = ["customer"]


class ReleaseAdminForm(forms.ModelForm):
    class Meta:
        model = Release
        fields = "__all__"


# class ReleaseAdmin(ImportExportModelAdmin):
class ReleaseAdmin(admin.ModelAdmin):
    form = ReleaseAdminForm
    resource_class = ReleaseResource

    list_display = [
        "release_id",
        "loan",
        "created_at",
        "updated_at",
        "release_date",
        "released_by",
    ]


admin.site.register(License, LicenseAdmin)
admin.site.register(Series, SeriesAdmin)
admin.site.register(LoanPayment)
admin.site.register(Loan, LoanAdmin)
admin.site.register(Release, ReleaseAdmin)
