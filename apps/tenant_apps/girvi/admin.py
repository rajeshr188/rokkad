from django import forms
from django.contrib import admin
from django.http import Http404
from django.shortcuts import render
# admin.py
from django.urls import path, reverse
from django.utils.html import format_html

from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import ProductVariant

from .forms import LoanForm, LoanItemStorageBoxForm
from .models import (License, Loan, LoanItem, LoanItemStorageBox, LoanPayment,
                     LoanTemplate, Release, Series, TemplateFrame)
from .resources import (LicenseResource, LoanItemResource, LoanPaymentResource,
                        LoanResource, ReleaseResource)


class TemplateFrameInline(admin.TabularInline):
    model = TemplateFrame
    extra = 1
    fieldsets = (
        (None, {"fields": ("frame_name", "field_type", "template_type")}),
        (
            "Position & Size",
            {"fields": ("x_pos", "y_pos", "width", "height"), "classes": ("collapse",)},
        ),
        (
            "Text Settings",
            {"fields": ("font_size", "font_name"), "classes": ("collapse",)},
        ),
    )


@admin.register(LoanTemplate)
class LoanTemplateAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "print_option",
        "dimensions",
        "is_active",
        "is_default",
        "preview_button",
    ]
    list_filter = ["print_option", "is_active", "is_default"]
    search_fields = ["name"]
    inlines = [TemplateFrameInline]

    fieldsets = (
        (None, {"fields": ("name", "print_option", "is_default")}),
        (
            "templates",
            {
                "fields": (
                    "base_template",
                    "dup_template",
                    "terms_template",
                    "form_d3_template",
                ),
            },
        ),
        (
            "Page Settings",
            {
                "fields": ("page_width", "page_height", "is_active"),
                "classes": ("collapse",),
            },
        ),
    )

    def dimensions(self, obj):
        return f"{obj.page_width}cm × {obj.page_height}cm"

    dimensions.short_description = "Page Size"

    def preview_template(self, request, object_id):
        """Handle template preview view"""
        template = self.get_object(request, object_id)
        if template is None:
            raise Http404("Template does not exist")

        context = {
            "template": template,
            "frames": template.templateframe_set.all(),
            "title": f"Preview: {template.name}",
            "opts": self.model._meta,
            **self.admin_site.each_context(request),
        }
        return render(request, "admin/preview_template.html", context)

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "template/<path:object_id>/preview/",
                self.admin_site.admin_view(self.preview_template),
                name="preview_template",
            ),
        ]
        return custom_urls + urls

    def preview_button(self, obj):
        # Use reverse() to generate correct URL
        url = reverse("admin:preview_template", args=[obj.pk])
        return format_html('<a class="button" href="{}">Preview</a>', url)

    preview_button.short_description = "Actions"


@admin.register(TemplateFrame)
class TemplateFrameAdmin(admin.ModelAdmin):
    list_display = [
        "template",
        "frame_name",
        "template_type",
        "field_type",
        "position",
        "size",
    ]
    list_filter = ["template", "field_type", "template_type", "frame_name"]
    search_fields = ["template__name", "frame_name"]

    def position(self, obj):
        return f"({obj.x_pos}, {obj.y_pos})"

    position.short_description = "Position (cm)"

    def size(self, obj):
        return f"{obj.width}×{obj.height}"

    size.short_description = "Size (cm)"


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
