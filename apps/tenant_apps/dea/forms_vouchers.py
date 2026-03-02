"""
Forms for ExpenseVoucher and JournalEntryVoucher

Includes formsets for line items with crispy forms styling and HTMX support.
"""

from django import forms
from django.forms import inlineformset_factory
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Submit, Button, Fieldset, Row, Column, HTML
from django_select2 import forms as s2forms
from djmoney.forms import MoneyField as DjangoMoneyField

from .models import (
    ExpenseVoucher,
    ExpenseLineItem,
    JournalEntryVoucher,
    JournalEntryLineItem,
    Ledger,
    SalesInvoiceVoucher,
    SalesInvoiceLineItem,
    PurchaseInvoiceVoucher,
    PurchaseInvoiceLineItem,
)


class LedgerWidget(s2forms.ModelSelect2Widget):
    """Select2 widget for ledger selection"""

    search_fields = [
        "name__icontains",
        "parent__name__icontains",
    ]


# ============================================================================
# EXPENSE VOUCHER FORMS
# ============================================================================


class ExpenseVoucherForm(forms.ModelForm):
    """Form for creating/editing expense vouchers"""

    class Meta:
        model = ExpenseVoucher
        fields = [
            "expense_date",
            "source_type",
            "source_doc_id",
            "party_name",
            "party_email",
            "description",
            "memo",
        ]
        widgets = {
            "expense_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "source_type": forms.Select(attrs={"class": "form-select"}),
            "source_doc_id": forms.TextInput(attrs={"class": "form-control"}),
            "party_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Employee or Vendor name",
                }
            ),
            "party_email": forms.EmailInput(
                attrs={"class": "form-control", "placeholder": "email@example.com"}
            ),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "memo": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Short reference"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("expense_date", css_class="col-md-4"),
                Column("source_type", css_class="col-md-4"),
                Column("source_doc_id", css_class="col-md-4"),
            ),
            Row(
                Column("party_name", css_class="col-md-6"),
                Column("party_email", css_class="col-md-6"),
            ),
            "description",
            "memo",
        )


class ExpenseLineItemForm(forms.ModelForm):
    """Form for individual expense line items"""

    class Meta:
        model = ExpenseLineItem
        fields = [
            "category",
            "description",
            "amount",
            "is_taxable",
            "tax_rate",
            "tds_rate",
        ]
        widgets = {
            "category": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "description": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "amount": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "is_taxable": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "tax_rate": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "step": "0.01",
                    "value": "18",
                }
            ),
            "tds_rate": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-sm",
                    "step": "0.01",
                    "value": "0",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True


# Create formset for expense line items
ExpenseLineItemFormSet = inlineformset_factory(
    ExpenseVoucher,
    ExpenseLineItem,
    form=ExpenseLineItemForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# ============================================================================
# JOURNAL ENTRY VOUCHER FORMS
# ============================================================================


class JournalEntryVoucherForm(forms.ModelForm):
    """Form for creating/editing journal entries"""

    class Meta:
        model = JournalEntryVoucher
        fields = [
            "je_date",
            "entry_type",
            "description",
            "memo",
            "reference",
        ]
        widgets = {
            "je_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "entry_type": forms.Select(attrs={"class": "form-select"}),
            "description": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
            "memo": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Short reference"}
            ),
            "reference": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "External reference"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.layout = Layout(
            Row(
                Column("je_date", css_class="col-md-4"),
                Column("entry_type", css_class="col-md-4"),
                Column("reference", css_class="col-md-4"),
            ),
            "description",
            "memo",
        )


class JournalEntryLineItemForm(forms.ModelForm):
    """Form for individual journal entry line items"""

    ledger = forms.ModelChoiceField(
        queryset=Ledger.objects.all(),
        widget=LedgerWidget(attrs={"class": "form-select form-select-sm"}),
        required=True,
    )

    class Meta:
        model = JournalEntryLineItem
        fields = [
            "ledger",
            "side",
            "amount",
            "description",
        ]
        widgets = {
            "side": forms.Select(attrs={"class": "form-select form-select-sm"}),
            "amount": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "description": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.form_tag = False
        self.helper.disable_csrf = True

    def save(self, commit=True):
        """Save the line item and populate ledger_id and ledger_name"""
        instance = super().save(commit=False)
        if self.cleaned_data.get("ledger"):
            ledger = self.cleaned_data["ledger"]
            instance.ledger_id = ledger.id
            instance.ledger_name = ledger.name
        if commit:
            instance.save()
        return instance


# Create formset for journal entry line items
JournalEntryLineItemFormSet = inlineformset_factory(
    JournalEntryVoucher,
    JournalEntryLineItem,
    form=JournalEntryLineItemForm,
    extra=4,
    can_delete=True,
    min_num=2,
    validate_min=True,
)


# ============================================================================
# SALES INVOICE FORMS
# ============================================================================


class SalesInvoiceForm(forms.ModelForm):
    """Form for creating/editing sales invoices"""

    class Meta:
        model = SalesInvoiceVoucher
        fields = [
            "invoice_date",
            "customer",
            "reference",
            "description",
            "payment_terms",
            "due_date",
            "notes",
        ]
        widgets = {
            "invoice_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "due_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("invoice_date", css_class="col-md-4"),
                Column("customer", css_class="col-md-8"),
            ),
            "reference",
            "description",
            Row(
                Column("payment_terms", css_class="col-md-6"),
                Column("due_date", css_class="col-md-6"),
            ),
            "notes",
        )
        self.helper.disable_csrf = True


class SalesInvoiceLineItemForm(forms.ModelForm):
    """Form for sales invoice line items"""

    class Meta:
        model = SalesInvoiceLineItem
        fields = [
            "item_code",
            "description",
            "quantity",
            "unit_price",
            "discount_percentage",
            "hsn_code",
            "tax_rate",
            "cgst_rate",
            "sgst_rate",
            "igst_rate",
        ]
        widgets = {
            "item_code": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "description": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "quantity": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.001"}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "discount_percentage": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "hsn_code": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "tax_rate": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "cgst_rate": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "sgst_rate": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "igst_rate": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
        }


# Create formset for sales invoice line items
SalesInvoiceLineItemFormSet = inlineformset_factory(
    SalesInvoiceVoucher,
    SalesInvoiceLineItem,
    form=SalesInvoiceLineItemForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)


# ============================================================================
# PURCHASE INVOICE FORMS
# ============================================================================


class PurchaseInvoiceForm(forms.ModelForm):
    """Form for creating/editing purchase invoices"""

    class Meta:
        model = PurchaseInvoiceVoucher
        fields = [
            "invoice_number",
            "invoice_date",
            "received_date",
            "vendor",
            "purchase_type",
            "reference",
            "description",
            "payment_terms",
            "due_date",
            "notes",
        ]
        widgets = {
            "invoice_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "received_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "due_date": forms.DateInput(
                attrs={"type": "date", "class": "form-control"}
            ),
            "description": forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
            "notes": forms.Textarea(attrs={"rows": 2, "class": "form-control"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            Row(
                Column("invoice_number", css_class="col-md-4"),
                Column("invoice_date", css_class="col-md-4"),
                Column("received_date", css_class="col-md-4"),
            ),
            Row(
                Column("vendor", css_class="col-md-8"),
                Column("purchase_type", css_class="col-md-4"),
            ),
            "reference",
            "description",
            Row(
                Column("payment_terms", css_class="col-md-6"),
                Column("due_date", css_class="col-md-6"),
            ),
            "notes",
        )
        self.helper.disable_csrf = True


class PurchaseInvoiceLineItemForm(forms.ModelForm):
    """Form for purchase invoice line items"""

    class Meta:
        model = PurchaseInvoiceLineItem
        fields = [
            "item_code",
            "description",
            "quantity",
            "unit_price",
            "hsn_code",
            "tax_rate",
            "cgst_rate",
            "sgst_rate",
            "igst_rate",
        ]
        widgets = {
            "item_code": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "description": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "quantity": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.001"}
            ),
            "unit_price": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "hsn_code": forms.TextInput(
                attrs={"class": "form-control form-control-sm"}
            ),
            "tax_rate": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "cgst_rate": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "sgst_rate": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
            "igst_rate": forms.NumberInput(
                attrs={"class": "form-control form-control-sm", "step": "0.01"}
            ),
        }


# Create formset for purchase invoice line items
PurchaseInvoiceLineItemFormSet = inlineformset_factory(
    PurchaseInvoiceVoucher,
    PurchaseInvoiceLineItem,
    form=PurchaseInvoiceLineItemForm,
    extra=3,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
