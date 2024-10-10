from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import ProductVariant

from .forms import LoanForm, LoanItemStorageBoxForm
from .models import (
    License,
    Loan,
    LoanItem,
    LoanItemStorageBox,
    LoanPayment,
    Release,
    Series,
)
from .resources import (
    LicenseResource,
    LoanItemResource,
    LoanPaymentResource,
    LoanResource,
    ReleaseResource,
)


class SeriesAdminForm(forms.ModelForm):
    class Meta:
        model = Series
        fields = "__all__"


class SeriesAdmin(admin.TabularInline):
    form = SeriesAdminForm
    list_display = [
        "id",
        "name",
        "created",
    ]
    model = Series
    extra = 1


class LicenseAdminForm(forms.ModelForm):
    class Meta:
        model = License
        fields = "__all__"


class LicenseAdmin(admin.ModelAdmin):
    form = LicenseAdminForm
    inlines = [
        SeriesAdmin,
    ]
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


class LoanPaymentAdminForm(forms.ModelForm):
    class Meta:
        model = LoanPayment
        fields = "__all__"


class LoanPaymentAdmin(admin.TabularInline):
    model = LoanPayment
    extra = 1
    form = LoanPaymentAdminForm
    resource_class = LoanPaymentResource
    list_display = [
        "id",
        "loan",
        "payment_date",
        "payment_amount",
        # "payment_mode",
        # "payment_status",
    ]
    search_fields = ["loan__loan_id"]
    # autocomplete_fields = ["loan"]


class LoanItemAdminForm(forms.ModelForm):
    class Meta:
        model = LoanItem
        fields = "__all__"


class LoanItemAdmin(admin.TabularInline):
    form = LoanItemAdminForm
    extra = 1
    # resource_class = LoanItemResource
    list_display = ("loan", "itemdesc", "itemtype", "weight", "loanamount")
    search_fields = ["loan__loan_id", "itemdesc"]
    autocomplete_fields = [
        "loan",
    ]
    model = LoanItem


class ReleaseAdminForm(forms.ModelForm):
    class Meta:
        model = Release
        fields = "__all__"


# class ReleaseAdmin(ImportExportModelAdmin):
class ReleaseAdmin(admin.TabularInline):
    form = ReleaseAdminForm
    resource_class = ReleaseResource
    search_fields = ["loan__loan_id", "released_by__name"]
    list_display = [
        "release_id",
        "loan",
        "created_at",
        "updated_at",
        "release_date",
        "released_by",
    ]
    autocomplete_fields = ["loan", "released_by"]
    model = Release


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
    inlines = [
        LoanItemAdmin,
        ReleaseAdmin,
        LoanPaymentAdmin,
    ]
    list_display = [
        "id",
        "loan_id",
        "customer",
        "series",
        "loan_date",
        "item_desc",
        "loan_amount",
    ]
    search_fields = ["customer__name", "loan_id", "item_desc"]
    autocomplete_fields = ["customer"]
    list_filter = ["series"]


class LoanItemStorageBoxAdmin(admin.ModelAdmin):
    form = LoanItemStorageBoxForm


admin.site.register(License, LicenseAdmin)
admin.site.register(Loan, LoanAdmin)
admin.site.register(LoanItemStorageBox, LoanItemStorageBoxAdmin)
