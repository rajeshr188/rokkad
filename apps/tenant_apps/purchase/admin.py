import decimal

from django import forms
from django.contrib import admin

from apps.tenant_apps.contact.models import Customer

from .models import Payment, Purchase, PurchaseItem

# from import_export import fields, resources
# from import_export.admin import (ImportExportActionModelAdmin,
#                                  ImportExportModelAdmin)
# from import_export.widgets import DecimalWidget, ForeignKeyWidget


# class CustomDecimalWidget(DecimalWidget):
#     """
#     Widget for converting decimal fields.
#     """

#     def clean(self, value, row=None):
#         if self.is_empty(value):
#             return None
#         return decimal.Decimal(str(value))


# class supplierWidget(ForeignKeyWidget):
#     def clean(self, value, row=None, *args, **kwargs):
#         return self.model.objects.get_or_create(name=value, type="Wh")[0]


class PurchaseAdminForm(forms.ModelForm):
    class Meta:
        model = Purchase
        fields = "__all__"


# class PurchaseResource(resources.ModelResource):
#     supplier = fields.Field(
#         column_name="supplier",
#         attribute="supplier",
#         widget=supplierWidget(Customer, "name"),
#     )

#     class Meta:
#         model = Purchase
#         fields = (
#             "id",
#             "supplier",
#             "created",
#             # "rate",
#             # "balancetype",
#             # "balance",
#             "status",
#         )
#         skip_unchanged = True
#         report_skipped = False


# class PurchaseAdmin(ImportExportActionModelAdmin):
class PurchaseAdmin(admin.ModelAdmin):
    form = PurchaseAdminForm
    # resource_class = PurchaseResource
    list_display = [
        "id",
        "created",
        "updated",
        "supplier",
        # "rate",
        # "balancetype",
        # "balance",
        "status",
    ]


admin.site.register(Purchase, PurchaseAdmin)


class PurchaseItemAdminForm(forms.ModelForm):
    class Meta:
        model = PurchaseItem
        fields = "__all__"


class PurchaseItemAdmin(admin.ModelAdmin):
    form = PurchaseItemAdminForm
    list_display = ["weight", "touch", "quantity"]
    list_filter = ("invoice",)
    search_fields = ("invoice__id",)


admin.site.register(PurchaseItem, PurchaseItemAdmin)


class PaymentAdminForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = "__all__"


# class PaymentResourse(resources.ModelResource):
#     supplier = fields.Field(
#         column_name="supplier",
#         attribute="supplier",
#         widget=ForeignKeyWidget(Customer, "name"),
#     )
#     total = fields.Field(
#         column_name="total", attribute="total", widget=CustomDecimalWidget()
#     )

#     class Meta:
#         model = Payment
#         skip_unchanged = True
#         report_skipped = False


# class PaymentAdmin(ImportExportActionModelAdmin):
class PaymentAdmin(admin.ModelAdmin):
    form = PaymentAdminForm
    # resource_class = PaymentResourse
    list_display = [
        "id",
        "created",
        "updated",
        "supplier",
        # "payment_type",
        "total",
        "description",
        "status",
    ]


admin.site.register(Payment, PaymentAdmin)
