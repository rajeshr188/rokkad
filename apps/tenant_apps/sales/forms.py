from crispy_forms.helper import FormHelper
from crispy_forms.layout import (ButtonHolder, Column, Field, Layout, Row,
                                 Submit)
from django import forms
from django.urls import reverse_lazy
from django_select2.forms import Select2Widget
from django_tables2 import Column

from apps.tenant_apps.approval.models import Approval
from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.product.forms import StockWidget
from apps.tenant_apps.product.models import Stock
from apps.tenant_apps.utils.custom_layout_object import *

from .models import Invoice, InvoiceItem, Receipt


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"


class DateTimeLocalField(forms.DateTimeField):
    # Set DATETIME_INPUT_FORMATS here because, if USE_L10N
    # is True, the locale-dictated format will be applied
    # instead of settings.DATETIME_INPUT_FORMATS.
    # See also:
    # https://developer.mozilla.org/en-US/docs/Web/HTML/Date_and_time_formats

    input_formats = ["%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M"]
    widget = DateTimeLocalInput(format="%Y-%m-%dT%H:%M")


class InvoiceForm(forms.ModelForm):
    voucher_date = DateTimeLocalField()
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(), widget=CustomerWidget
    )
    approval = forms.ModelChoiceField(
        queryset=Approval.objects.filter(status="Pending"),
        widget=Select2Widget,
        required=False,
    )

    class Meta:
        model = Invoice
        fields = [
            "voucher_date",
            "approval",
            "is_ratecut",
            "is_gst",
            "term",
            "customer",
            "gold_rate",
            "silver_rate",
        ]

    def __init__(self, *args, **kwargs):
        super(InvoiceForm, self).__init__(*args, **kwargs)
        self.helper = FormHelper()
        # self.helper.form_show_labels = False
        self.helper.form_tag = False
        self.helper.form_class = "form-group"
        self.helper.label_class = "col-md-6 form-label"
        self.helper.field_class = "col-md-12"

        self.helper.layout = Layout(
            Row(
                Column(Field("voucher_date", css_class="form-control ")),
                Column(Field("customer", css_class="form-control ")),
                css_class="form-row",
            ),
            Row(
                Column(Field("gold_rate", css_class="form-control ")),
                Column(Field("silver_rate", css_class="form-control ")),
                css_class="form-row",
            ),
            Row(
                Column(Field("is_ratecut", css_class="form-control ")),
                Column(Field("is_gst", css_class="form-control ")),
                css_class="form-row",
            ),
            Row(
                Column(Field("approval", css_class="form-control")),
                Column(Field("term", css_class="form-control ")),
                css_class="form-row",
            ),
            ButtonHolder(Submit("submit", "save")),
        )


class InvoiceItemForm(forms.ModelForm):
    # TODO filter only lots that has qty and wt > 0
    # TODO add form validation
    product = forms.ModelChoiceField(
        queryset=Stock.objects.exclude(status="Empty"),
        widget=StockWidget,
    )

    class Meta:
        model = InvoiceItem
        fields = [
            "is_return",
            "product",
            "quantity",
            "weight",
            "less_stone",
            "touch",
            "wastage",
            "making_charge",
            "net_wt",
        ]
        widgets = {
            "weight": forms.NumberInput(
                attrs={
                    "hx-include": "[name='contact'], [name='product']",
                    "hx-get": reverse_lazy("sales:sale_product_price"),
                    "hx-target": "#div_id_touch",
                    "hx-trigger": "change",
                    "hx-swap": "innerHTML",
                }
            )
        }


class ReceiptForm(forms.ModelForm):
    customer = forms.ModelChoiceField(
        queryset=Customer.objects.exclude(customer_type="S"), widget=CustomerWidget
    )
    voucher_date = DateTimeLocalInput()

    class Meta:
        model = Receipt
        fields = [
            "voucher_date",
            "customer",
            "weight",
            "touch",
            "rate",
            "total",
            "description",
        ]
