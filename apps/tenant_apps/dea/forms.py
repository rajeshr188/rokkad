from crispy_forms.helper import FormHelper
from crispy_forms.layout import Button, Submit
from django import forms
from django.urls import reverse_lazy
from django_select2 import forms as s2forms
from djmoney.forms import MoneyField

from .models import (Account, AccountStatement, AccountTransaction,
                     JournalEntry, Ledger, LedgerStatement, LedgerTransaction,
                     TransactionType_Ext)


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
        "desc__icontains",
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
    class Meta:
        model = Ledger
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super(LedgerForm, self).__init__(*args, **kwargs)
        instance = kwargs.get("instance")
        self.fields["parent"].queryset = Ledger.objects.exclude(pk=self.instance.pk)
        self.helper = FormHelper()
        if instance:
            self.helper.attrs = {
                "hx-post": reverse_lazy("dea_ledger_update", kwargs={"pk": instance.pk})
            }
            cancel_url = reverse_lazy("dea_ledger_detail", kwargs={"pk": instance.id})
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-get": cancel_url,
                    "hx-target": "closest form",
                    "hx-swap": "outerHTML",
                },
            )
        else:
            self.helper.attrs = {"hx-post": reverse_lazy("dea_ledger_create")}
            cancel_url = reverse_lazy("dea_ledger_list")
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-on": 'click: this.closest("form").remove()',
                },
            )
        self.helper.add_input(Submit("submit", "Save", css_class="btn btn-success"))
        self.helper.add_input(cancel_button)


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
    # journal_entry = forms.ModelChoiceField(
    #     queryset=JournalEntry.objects.all(), widget=JournalEntryWidget
    # )
    amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR")

    class Meta:
        model = LedgerTransaction
        fields = ("ledgerno", "ledgerno_dr", "amount")

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data["ledgerno"] == cleaned_data["ledgerno_dr"]:
            raise forms.ValidationError("Ledger No and Ledger No Dr cannot be same")
        return cleaned_data

    def __init__(self, *args, **kwargs):
        # lt = kwargs.pop("lt")
        journalentry_id = kwargs.pop("journalentry_id", None)
        instance = kwargs.get("instance")
        super(LedgerTransactionForm, self).__init__(*args, **kwargs)
        # self.fields["ledgerno_dr"].queryset = Ledger.objects.exclude(
        #     pk=self.instance.ledgerno.pk
        # )
        self.helper = FormHelper()

        if instance:
            self.helper.attrs = {
                "hx-post": reverse_lazy(
                    "dea_ledgertransaction_create",
                    kwargs={"pk": instance.journal_entry.pk},
                )
            }
            cancel_url = reverse_lazy(
                "dea_ledgertransaction_detail", kwargs={"pk": instance.id}
            )
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-get": cancel_url,
                    "hx-target": "closest li",
                    "hx-swap": "outerHTML",
                },
            )
        else:
            self.helper.attrs = {
                "hx-post": reverse_lazy(
                    "dea_ledgertransaction_create", kwargs={"pk": journalentry_id}
                )
            }
            cancel_url = reverse_lazy("dea_ledgertransaction_list")
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-on": 'click: this.closest("form").remove()',
                },
            )
        self.helper.add_input(cancel_button)
        self.helper.add_input(Submit("submit", "Save", css_class="btn btn-success"))


class AccountTransactionForm(forms.ModelForm):
    Account = forms.ModelChoiceField(
        queryset=Account.objects.all(), widget=AccountWidget
    )
    ledgerno = forms.ModelChoiceField(
        queryset=Ledger.objects.all(), widget=LedgerWidget
    )
    # journal_entry = forms.ModelChoiceField(
    #     queryset=JournalEntry.objects.all(), widget=JournalEntryWidget
    # )
    amount = MoneyField(max_digits=13, decimal_places=2, default_currency="INR")

    class Meta:
        model = AccountTransaction
        fields = ("ledgerno", "Account", "XactTypeCode", "XactTypeCode_ext", "amount")

    def __init__(self, *args, **kwargs):
        # lt = kwargs.pop("lt")
        journalentry_id = kwargs.pop("journalentry_id", None)
        instance = kwargs.get("instance")
        super(AccountTransactionForm, self).__init__(*args, **kwargs)

        self.helper = FormHelper()
        if instance:
            self.helper.attrs = {
                "hx-post": reverse_lazy(
                    "dea_accounttransaction_create",
                    kwargs={"pk": instance.journal_entry.pk},
                )
            }
            cancel_url = reverse_lazy(
                "dea_accounttransaction_detail", kwargs={"pk": instance.id}
            )
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-get": cancel_url,
                    "hx-target": "closest li",
                    "hx-swap": "outerHTML",
                },
            )
        else:
            self.helper.attrs = {
                "hx-post": reverse_lazy(
                    "dea_accounttransaction_create", kwargs={"pk": journalentry_id}
                )
            }
            cancel_button = Button(
                "cancel",
                "Cancel",
                css_class="btn btn-danger",
                **{
                    "hx-on": 'click: this.closest("form").remove()',
                },
            )
        self.helper.add_input(cancel_button)
        self.helper.add_input(Submit("submit", "Save", css_class="btn btn-success"))


class JournalEntryForm(forms.ModelForm):
    desc = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}))

    class Meta:
        model = JournalEntry
        fields = ("desc",)


# op bal foormset for ledger and acc
