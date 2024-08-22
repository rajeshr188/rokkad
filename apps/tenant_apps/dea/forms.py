from django import forms
from django_select2 import forms as s2forms
from djmoney.forms import MoneyField

from .models import (
    Account,
    AccountStatement,
    AccountTransaction,
    JournalEntry,
    Ledger,
    LedgerStatement,
    LedgerTransaction,
)


class AccountWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "contact__name__icontains",
        "contact__relatedas__icontains",
        "contact__relatedto__icontains",
        "contact__contactno__phone_number__icontains",
    ]


class LedgerWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "name__icontains",
        "AccountType__AccountType__icontains",
        "parent__name__icontains",
    ]


class JournalEntryWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "description__icontains",
    ]


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = "__all__"


class AccountStatementForm(forms.ModelForm):
    class Meta:
        model = AccountStatement
        fields = ("AccountNo", "ClosingBalance", "TotalCredit", "TotalDebit")


class LedgerForm(forms.ModelForm):
    name = forms.ModelChoiceField(queryset=Ledger.objects.all(), widget=LedgerWidget)

    class Meta:
        model = Ledger
        fields = "__all__"


class LedgerStatementForm(forms.ModelForm):
    class Meta:
        model = LedgerStatement
        fields = ("ledgerno", "ClosingBalance")


class LedgerTransactionForm(forms.ModelForm):
    ledgerno = forms.ModelChoiceField(
        queryset=Ledger.objects.all(), widget=LedgerWidget
    )
    ledgerno_dr = forms.ModelChoiceField(
        queryset=Ledger.objects.all(), widget=LedgerWidget
    )
    journal_entry = forms.ModelChoiceField(
        queryset=JournalEntry.objects.all(), widget=JournalEntryWidget
    )
    amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR")

    class Meta:
        model = LedgerTransaction
        fields = "__all__"


class AccountTransactionForm(forms.ModelForm):
    Account = forms.ModelChoiceField(
        queryset=Account.objects.all(), widget=AccountWidget
    )
    ledgerno = forms.ModelChoiceField(
        queryset=Ledger.objects.all(), widget=LedgerWidget
    )
    journal_entry = forms.ModelChoiceField(
        queryset=JournalEntry.objects.all(), widget=JournalEntryWidget
    )

    # amount = MoneyField(max_digits=13, decimal_places=2, default_currency='INR')
    class Meta:
        model = AccountTransaction
        fields = "__all__"


class JournalEntryForm(forms.ModelForm):
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = JournalEntry
        fields = {"description"}


# op bal foormset for ledger and acc
