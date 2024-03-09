from django import forms
from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from import_export import fields, resources
from import_export.admin import ImportExportModelAdmin
from import_export.widgets import ForeignKeyWidget

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import ProductVariant

from .forms import LoanForm
from .models import License, Loan, LoanItem, LoanPayment, Release, Series


class LoanResource(resources.ModelResource):
    customer = fields.Field(
        column_name="customer",
        attribute="customer",
        widget=ForeignKeyWidget(Customer, "pk"),
    )
    # license=fields.Field(column_name='license',
    #                         attribute='license',
    #                         widget=ForeignKeyWidget(License,'id'))
    series = fields.Field(
        column_name="series", attribute="series", widget=ForeignKeyWidget(Series, "id")
    )

    class Meta:
        model = Loan
        import_id_fields = ("id",)


class LoanItemResource(resources.ModelResource):
    loan = fields.Field(
        column_name="loan", attribute="loan", widget=ForeignKeyWidget(Loan, "pk")
    )
    item = fields.Field(
        column_name="item",
        attribute="item",
        widget=ForeignKeyWidget(ProductVariant, "id"),
    )

    class Meta:
        model = LoanItem


class LoanPaymentResource(resources.ModelResource):
    loan = fields.Field(
        column_name="loan", attribute="loan", widget=ForeignKeyWidget(Loan, "pk")
    )

    class Meta:
        model = LoanPayment


class ReleaseResource(resources.ModelResource):
    loan = fields.Field(
        column_name="loan", attribute="loan", widget=ForeignKeyWidget(Loan, "pk")
    )
    released_by = fields.Field(
        column_name="released_by",
        attribute="released_by",
        widget=ForeignKeyWidget(Customer, "pk"),
    )

    class Meta:
        model = Release


class LicenseAdminForm(forms.ModelForm):
    class Meta:
        model = License
        fields = "__all__"


class LicenseAdmin(admin.ModelAdmin):
    form = LicenseAdminForm
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


class LoanAdminForm(forms.ModelForm):
    date_heirarchy = "created"
    list_filter = ("customer", "series")

    class Meta:
        model = Loan
        fields = "__all__"


# class LoanAdmin(ImportExportModelAdmin):
class LoanAdmin(admin.ModelAdmin):
    def print(self, obj):
        original_url = reverse("girvi:original", args=[obj.id])
        duplicate_url = reverse("girvi:duplicate", args=[obj.id])
        return format_html(
            """
            <div class="btn-group" role="group" aria-label="Button group with nested dropdown">
                <div class="btn-group" role="group">
                    <ul class="dropdown-menu">
                        <li><a class="dropdown-item" href="{0}">Original</a></li>
                        <li><a class="dropdown-item" href="{1}">Duplicate</a></li>
                    </ul>
                </div>
            </div>
            """,
            original_url,
            duplicate_url,
        )

    print.short_description = "Print Options"
    form = LoanAdminForm
    # resource_class = LoanResource
    list_display = [
        "id",
        "loan_id",
        "customer",
        "series",
        "loan_date",
        "item_desc",
        "loan_amount",
        "print",
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
    # resource_class = ReleaseResource

    list_display = [
        "release_id",
        "loan",
        "created_at",
        "updated_at",
        "release_date",
        "released_by",
    ]


admin.site.register(License, LicenseAdmin)
admin.site.register(Series)
admin.site.register(LoanPayment)
admin.site.register(Loan, LoanAdmin)
admin.site.register(Release, ReleaseAdmin)
