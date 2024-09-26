from datetime import datetime

from django import forms
from django.urls import reverse_lazy
from django_select2.forms import Select2Widget

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.models import ProductVariant
from apps.tenant_apps.utils.custom_layout_object import *

from .models import Payment, Purchase, PurchaseItem


class PurchaseForm(forms.ModelForm):
    supplier = forms.ModelChoiceField(
        queryset=Customer.objects.exclude(customer_type="Re"), widget=CustomerWidget
    )
    voucher_date = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "class": "form-control datetimepicker-input",
                "type": "datetime-local",
            }
        )
    )

    class Meta:
        model = Purchase
        fields = [
            "voucher_date",
            "is_gst",
            "is_ratecut",
            "supplier",
            "term",
            "status",
            "gold_rate",
            "silver_rate",
        ]


class PurchaseItemForm(forms.ModelForm):
    product = forms.ModelChoiceField(
        queryset=ProductVariant.objects.all(), widget=Select2Widget
    )

    class Meta:
        model = PurchaseItem
        fields = [
            "huid",
            "product",
            "quantity",
            "weight",
            "touch",
            "making_charge",
        ]
        widgets = {
            "weight": forms.NumberInput(
                attrs={
                    "hx-include": "[name='supplier'], [name='product']",
                    "hx-get": reverse_lazy("purchase:price_history"),
                    "hx-target": "#div_id_touch",
                    "hx-trigger": "change",
                    "hx-swap": "innerHTML",
                }
            )
        }


class PaymentForm(forms.ModelForm):
    voucher_date = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"type": "datetime-local"})
    )
    supplier = forms.ModelChoiceField(
        queryset=Customer.objects.all(), widget=Select2Widget
    )

    class Meta:
        model = Payment
        fields = [
            "supplier",
            "voucher_date",
            # "payment_type",
            "weight",
            "touch",
            "rate",
            "total",
            "description",
            "status",
        ]
