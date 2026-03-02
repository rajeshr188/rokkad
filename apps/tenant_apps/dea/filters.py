import django_filters
from django_select2.forms import Select2Widget

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer

from .models import (
    Account,
    AccountingPeriod,
    AccountType_Ext,
    Ledger,
    Voucher,
    VoucherType,
    VoucherStatus,
)


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


class PeriodFilter(django_filters.FilterSet):
    """Filter for AccountingPeriod list view"""

    status = django_filters.ChoiceFilter(
        choices=AccountingPeriod.PeriodStatus.choices,
        label="Status",
        empty_label="All Statuses",
    )
    start_date = django_filters.DateFromToRangeFilter(label="Start Date Range")
    end_date = django_filters.DateFromToRangeFilter(label="End Date Range")
    name = django_filters.CharFilter(lookup_expr="icontains", label="Period Name")

    class Meta:
        model = AccountingPeriod
        fields = ["status", "start_date", "end_date", "name"]


# ============================================================================
# VOUCHER FILTER
# ============================================================================


class VoucherFilter(django_filters.FilterSet):
    """
    Filter for Voucher list view.

    Features:
    - Filter by status (Draft, Posted, Reversed, Corrected)
    - Filter by voucher type
    - Filter by date range
    - Filter by created user
    - Search by voucher number or narration
    """

    status = django_filters.ChoiceFilter(
        choices=VoucherStatus.choices, label="Status", empty_label="All Statuses"
    )
    voucher_type = django_filters.ModelChoiceFilter(
        queryset=VoucherType.objects.all(),
        label="Voucher Type",
        empty_label="All Types",
    )
    voucher_date = django_filters.DateFromToRangeFilter(label="Date Range")
    created_by = django_filters.ModelChoiceFilter(
        queryset=None,  # Will be set dynamically
        label="Created By",
        empty_label="All Users",
    )
    voucher_no = django_filters.CharFilter(
        field_name="voucher_no", lookup_expr="icontains", label="Voucher #"
    )
    narration = django_filters.CharFilter(
        field_name="narration", lookup_expr="icontains", label="Description contains"
    )

    class Meta:
        model = Voucher
        fields = [
            "status",
            "voucher_type",
            "voucher_date",
            "created_by",
            "voucher_no",
            "narration",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically load users who have created vouchers
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.filters["created_by"].extra["queryset"] = User.objects.filter(
            vouchers_created__isnull=False
        ).distinct()
