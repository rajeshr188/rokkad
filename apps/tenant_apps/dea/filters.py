import django_filters
from django_select2.forms import Select2Widget

from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget

from .models import (
    Account,
    AccountingPeriod,
    AccountType_Ext,
    JournalEntry,
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
    party = django_filters.ModelChoiceFilter(
        queryset=Party.objects.all(), label="Party", widget=PartyAutocompleteWidget()
    )
    AccountType_Ext = django_filters.ModelChoiceFilter(
        queryset=AccountType_Ext.objects.all(),
        label="Account Type",
        widget=Select2Widget,
    )

    class Meta:
        model = Account
        fields = ["party", "AccountType_Ext"]


class JournalEntryFilter(django_filters.FilterSet):
    posted_at = django_filters.DateFromToRangeFilter()
    desc = django_filters.CharFilter(lookup_expr="icontains")
    balance_status = django_filters.ChoiceFilter(
        choices=(
            ("balanced", "Balanced only"),
            ("unbalanced", "Unbalanced only"),
        ),
        label="Balance Status",
        empty_label="All Entries",
        method="filter_balance_status",
    )

    class Meta:
        model = JournalEntry
        fields = ["posted_at", "desc", "balance_status"]

    def filter_balance_status(self, queryset, name, value):
        if value not in {"balanced", "unbalanced"}:
            return queryset

        target_balanced = value == "balanced"
        matching_ids = []

        for entry in queryset:
            is_balanced, _, _, _ = entry.validate_balanced()
            if is_balanced == target_balanced:
                matching_ids.append(entry.pk)

        return queryset.filter(pk__in=matching_ids)


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
