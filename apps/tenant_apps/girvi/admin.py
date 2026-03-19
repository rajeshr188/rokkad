from django import forms
from django.contrib import admin
from django.http import Http404
from django.shortcuts import render

# admin.py
from django.urls import path, reverse
from django.utils.html import format_html

from .forms import LoanItemStorageBoxForm
from .models import (
    GivenLoan,
    License,
    LicenseDocument,
    LoanItem,
    LoanItemStorageBox,
    LoanPayment,
    LoanTemplate,
    Release,
    Series,
    TakenLoan,
    TemplateFrame,
)
from .resources import (
    LicenseResource,
    LoanPaymentResource,
    LoanResource,
    ReleaseResource,
)


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
        fieldsets = (
            ("Basic Information", {
                "fields": ("license", "name", "prefix", "loan_type")
            }),
            ("Configuration", {
                "fields": ("max_limit", "is_active")
            }),
            ("Guardrails & Thresholds", {
                "classes": ("collapse",),
                "fields": (
                    "loan_count_threshold",
                    "loan_amount_threshold",
                    "deactivation_rule",
                    "deactivated_for_loans",
                    "deactivated_for_releases",
                    "deactivation_date",
                    "threshold_exceeded_reason",
                )
            }),
        )


class SeriesAdmin(admin.TabularInline):
    form = SeriesAdminForm
    list_display = [
        "id",
        "name",
        "created",
        "guardrail_status",
    ]
    model = Series
    extra = 1
    
    def guardrail_status(self, obj):
        """Display guardrail status indicator"""
        if obj.deactivated_for_loans and obj.deactivated_for_releases:
            return "🔒 Locked (loans & releases)"
        elif obj.deactivated_for_loans:
            return "🔒 Loans disabled"
        elif obj.deactivated_for_releases:
            return "🔒 Releases disabled"
        elif obj.is_any_threshold_exceeded():
            return "⚠️ Threshold exceeded"
        else:
            return "✓ Active"
    guardrail_status.short_description = "Status"


class LicenseAdminForm(forms.ModelForm):
    class Meta:
        model = License
        fields = "__all__"


class LicenseDocumentInline(admin.TabularInline):
    """Inline for managing license documents"""

    model = LicenseDocument
    extra = 1
    fields = [
        "document_type",
        "title",
        "document_file",
        "expiry_date",
        "is_verified",
        "is_active",
    ]
    readonly_fields = ["upload_date"]


class LicenseAdmin(admin.ModelAdmin):
    form = LicenseAdminForm
    inlines = [
        SeriesAdmin,
        LicenseDocumentInline,
    ]
    resource_class = LicenseResource
    fieldsets = (
        (
            "Basic Information",
            {
                "fields": (
                    "name",
                    "license_number",
                    "type",
                    "status",
                    "is_active",
                )
            },
        ),
        (
            "Business Details",
            {
                "fields": (
                    "shopname",
                    "business_type",
                    "address",
                    "city",
                    "state",
                    "postal_code",
                    "phonenumber",
                    "email",
                    "propreitor",
                )
            },
        ),
        (
            "License Details",
            {
                "fields": (
                    "issuing_authority",
                    "date_issued",
                    "renewal_date",
                    "date_expires",
                    "is_renewable",
                )
            },
        ),
        (
            "Additional Notes",
            {"fields": ("notes",), "classes": ("collapse",)},
        ),
    )
    list_display = [
        "name",
        "license_number",
        "id",
        "status",
        "type",
        "business_type",
        "shopname",
        "status_color_display",
        "expiry_status",
        "created",
    ]
    list_filter = [
        "status",
        "type",
        "business_type",
        "is_active",
        "date_expires",
        "created",
    ]
    search_fields = [
        "name",
        "license_number",
        "shopname",
        "propreitor",
        "address",
    ]
    readonly_fields = ["created", "updated"]
    ordering = ["-created"]

    def status_color_display(self, obj):
        """Display colored status badge"""
        color = obj.get_status_display_color()
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color,
            obj.get_status_display(),
        )

    status_color_display.short_description = "Status"

    def expiry_status(self, obj):
        """Display expiry status"""
        if obj.is_expired():
            return format_html('<span class="badge bg-danger">Expired</span>')
        elif obj.is_expiring_soon(days=30):
            days = obj.days_until_expiry()
            return format_html(
                '<span class="badge bg-warning">Expires in {} days</span>',
                days,
            )
        return format_html('<span class="badge bg-success">Active</span>')

    expiry_status.short_description = "Expiry Status"


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
    fk_name = "loan"


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
    list_filter = ("borrower", "series")

    class Meta:
        model = GivenLoan
        fields = "__all__"


# class LoanAdmin(ImportExportModelAdmin):
class GivenLoanAdmin(admin.ModelAdmin):
    form = LoanAdminForm
    resource_class = LoanResource
    inlines = [
        LoanItemAdmin,
        # ReleaseAdmin,  # Removed: Release only applies to GivenLoan, configured separately
        # LoanPaymentAdmin,  # Removed: LoanPayment FK needs updating to support GivenLoan/TakenLoan
    ]
    list_display = [
        "id",
        "loan_id",
        "borrower",
        "series",
        "loan_date",
        "display_item_desc",
        "display_loan_amount",
    ]
    search_fields = ["borrower__firstname", "borrower__lastname", "loan_id"]
    autocomplete_fields = ["borrower"]
    list_filter = ["series"]

    def display_item_desc(self, obj):
        """Display the item description"""
        return obj.get_item_description()

    display_item_desc.short_description = "Item Description"

    def display_loan_amount(self, obj):
        """Display the calculated loan amount"""
        return obj.get_loan_amount

    display_loan_amount.short_description = "Loan Amount"


class TakenLoanAdminForm(forms.ModelForm):
    date_heirarchy = "created"
    list_filter = ("lender", "series")

    class Meta:
        model = TakenLoan
        fields = "__all__"


class TakenLoanAdmin(admin.ModelAdmin):
    form = TakenLoanAdminForm
    resource_class = LoanResource
    inlines = []  # RepledgedLoanItem inline can be added later
    list_display = [
        "id",
        "loan_id",
        "lender",
        "series",
        "loan_date",
        "display_item_desc",
        "display_loan_amount",
    ]
    search_fields = ["lender__firstname", "lender__lastname", "loan_id"]
    autocomplete_fields = ["lender"]
    list_filter = ["series"]

    def display_item_desc(self, obj):
        """Display the item description"""
        return obj.get_item_description()

    display_item_desc.short_description = "Item Description"

    def display_loan_amount(self, obj):
        """Display the calculated loan amount"""
        return obj.get_loan_amount

    display_loan_amount.short_description = "Loan Amount"


class LoanItemStorageBoxAdmin(admin.ModelAdmin):
    form = LoanItemStorageBoxForm


class LicenseDocumentAdmin(admin.ModelAdmin):
    """Admin for License Documents"""

    list_display = [
        "title",
        "license",
        "document_type",
        "upload_date",
        "expiry_date",
        "is_verified",
        "is_active",
    ]
    list_filter = [
        "document_type",
        "is_verified",
        "is_active",
        "upload_date",
    ]
    search_fields = ["title", "license__name", "license__license_number"]
    readonly_fields = ["upload_date", "uploaded_by", "file_size", "file_type"]
    fieldsets = (
        (
            "Document Information",
            {
                "fields": (
                    "license",
                    "document_type",
                    "title",
                    "description",
                )
            },
        ),
        (
            "File Information",
            {
                "fields": (
                    "document_file",
                    "file_size",
                    "file_type",
                    "upload_date",
                    "uploaded_by",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Verification & Status",
            {
                "fields": (
                    "expiry_date",
                    "is_verified",
                    "is_active",
                ),
            },
        ),
    )


admin.site.register(License, LicenseAdmin)
admin.site.register(LicenseDocument, LicenseDocumentAdmin)
admin.site.register(GivenLoan, GivenLoanAdmin)
admin.site.register(TakenLoan, TakenLoanAdmin)
admin.site.register(LoanItemStorageBox, LoanItemStorageBoxAdmin)
