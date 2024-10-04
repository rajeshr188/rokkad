import django_filters
from django.db.models import Q
from django_select2.forms import ModelSelect2Widget, Select2Widget

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer

from .models import Account, AccountType_Ext, Ledger


class LedgerTransactionFilter(django_filters.FilterSet):
    created = django_filters.DateFromToRangeFilter()
    ledgerno = django_filters.ModelChoiceFilter(
        queryset=Ledger.objects.all().select_related("AccountType"), label="Credit"
    )
    ledgerno_dr = django_filters.ModelChoiceFilter(
        queryset=Ledger.objects.all().select_related("AccountType"), label="Debit"
    )

    class Meta:
        model = Ledger
        fields = ["created", "ledgerno", "ledgerno_dr"]


class AccountFilter(django_filters.FilterSet):
    contact = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(), label="Account", widget=CustomerWidget()
    )
    AccountType_Ext = django_filters.ModelChoiceFilter(
        queryset=AccountType_Ext.objects.all(),
        label="Account Type",
        widget=Select2Widget,
    )

    class Meta:
        model = Account
        fields = ["contact", "AccountType_Ext"]


class JournalEntryFilter(django_filters.FilterSet):
    created = django_filters.DateFromToRangeFilter()
    desc = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Ledger
        fields = ["created", "desc"]
