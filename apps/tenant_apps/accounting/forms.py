from django import forms

from .models import OpenItem
from apps.tenant_apps.party.models import Party


class AccountingBootstrapForm(forms.Form):
    period_key = forms.CharField(max_length=64, initial="FY2026")
    start_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))

    def clean(self):
        data = super().clean()
        if data.get("start_date") and data.get("end_date") and data["end_date"] < data["start_date"]:
            self.add_error("end_date", "End date cannot be before start date.")
        return data


class AccountingActivationForm(forms.Form):
    workflow_mode = forms.ChoiceField(
        choices=(("OWNER", "Owner-operated — create and post in one confirmation"),
                 ("TEAM", "Team — separate maker, authorizer, and poster"))
    )
    enabled = forms.BooleanField(required=False, label="Enable standalone accounting writes")
    confirmation = forms.CharField(
        max_length=32,
        required=False,
        help_text="Type ENABLE ACCOUNTING when enabling.",
    )

    def clean(self):
        data = super().clean()
        if data.get("enabled") and data.get("confirmation", "").strip() != "ENABLE ACCOUNTING":
            self.add_error("confirmation", "Type ENABLE ACCOUNTING exactly to enable writes.")
        return data


class AccountingTransactionForm(forms.Form):
    CASH_SALE = "CASH_SALE"
    CREDIT_SALE = "CREDIT_SALE"
    CUSTOMER_RECEIPT = "CUSTOMER_RECEIPT"
    TYPES = (
        (CASH_SALE, "Cash sale"),
        (CREDIT_SALE, "Credit sale"),
        (CUSTOMER_RECEIPT, "Customer receipt"),
    )

    transaction_type = forms.ChoiceField(choices=TYPES)
    source_id = forms.CharField(max_length=128, label="Document/reference number")
    effective_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    amount = forms.DecimalField(min_value=0.01, max_digits=20, decimal_places=2)
    party = forms.ModelChoiceField(
        queryset=Party.objects.none(), required=False, label="Customer (Party)"
    )
    new_party_name = forms.CharField(
        max_length=255, required=False, label="Or create a new Party"
    )
    narration = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, book, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["party"].queryset = Party.objects.filter(
            status=Party.PartyStatus.ACTIVE
        ).order_by("display_name", "party_code")

    def clean(self):
        data = super().clean()
        if data.get("transaction_type") != self.CASH_SALE and not data.get("party"):
            if not data.get("new_party_name"):
                self.add_error("party", "Choose a Party or enter a new Party name below.")
        return data


class ReceiptAllocationForm(forms.Form):
    open_item = forms.ModelChoiceField(queryset=OpenItem.objects.none())
    amount = forms.DecimalField(min_value=0.01, max_digits=20, decimal_places=2)

    def __init__(self, *args, book, external_account, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["open_item"].queryset = OpenItem.objects.filter(
            book=book, external_account=external_account
        ).order_by("due_date", "open_item_key")


class AccountingReversalForm(forms.Form):
    reversal_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 3}))
    confirmation = forms.CharField(
        max_length=16, help_text="Type REVERSE to confirm."
    )

    def clean_confirmation(self):
        value = self.cleaned_data["confirmation"].strip()
        if value != "REVERSE":
            raise forms.ValidationError("Type REVERSE exactly.")
        return value
