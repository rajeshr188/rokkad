import django_filters
from django.db.models import Q
from django_filters.widgets import RangeWidget

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer

from .forms import LoansWidget
from .models import (
    ItemType,
    GivenLoan,
    LoanItem,
    Release,
    TakenLoan,
    LoanStatus,
)


class BaseLoanFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="universal_search", label="Search")
    loan_date_range = django_filters.DateFromToRangeFilter(
        field_name="loan_date",
        label="Loan Date Range",
        widget=RangeWidget(attrs={"type": "date"}),
    )
    date = django_filters.DateRangeFilter(field_name="loan_date", label="Loan Date")

    sunk = django_filters.BooleanFilter(method="sunken", label="sunken")

    STATUS_CHOICES = [
        ("All", "All"),
        ("Released", "Released"),
        ("UnReleased", "Not Released"),
    ]

    status = django_filters.ChoiceFilter(
        choices=STATUS_CHOICES,
        method="filter_status",
        label="Status",
    )

    def universal_search(self, queryset, name, value):
        return queryset.filter(
            Q(id__icontains=value)
            | Q(loan_id__icontains=value)
            | Q(series__name__icontains=value)
        )

    # Filter for sunken/overdue loans - adds annotation first
    def sunken(self, queryset, name, value):
        queryset = queryset.with_overdue_status()
        return queryset.filter(is_overdue=value)


class LoanFilter(BaseLoanFilter):
    borrower = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(),
    )

    # notice = django_filters.CharFilter(
    #     field_name="notifications__notice_type", lookup_expr="icontains"
    # )

    def filter_item_type(self, queryset, name, value):
        return queryset.filter(loanitems__itemtype=value)

    item_type = django_filters.ChoiceFilter(
        method="filter_item_type",
        choices=ItemType.choices,
        empty_label="Select Item Type",
        label="Item Type",
    )

    def filter_status(self, queryset, name, value):
        if value == "Released":
            return queryset.filter(release__isnull=False)
        elif value == "UnReleased":
            return queryset.filter(release__isnull=True)
        return queryset

    # def filter_status(self, queryset, name, value):
    #     return queryset.filter(release__isnull=value)

    class Meta:
        model = GivenLoan
        fields = [
            "query",
            "series",
            "borrower",
            "loan_date_range",
        ]

    def universal_search(self, queryset, name, value):
        return queryset.filter(
            Q(id__icontains=value)
            | Q(borrower__firstname__icontains=value)
            | Q(borrower__lastname__icontains=value)
            | Q(loan_id__icontains=value)
        )


class TakenLoanFilter(BaseLoanFilter):
    lender = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(),
    )

    def filter_status(self, queryset, name, value):
        if value == "Released":
            return queryset.filter(status=LoanStatus.RELEASED)
        elif value == "UnReleased":
            return queryset.exclude(status=LoanStatus.RELEASED)
        return queryset

    class Meta:
        model = TakenLoan
        fields = [
            "query",
            "series",
            "lender",
            "loan_date_range",
        ]

    def universal_search(self, queryset, name, value):
        return queryset.filter(
            Q(id__icontains=value)
            | Q(lender__firstname__icontains=value)
            | Q(lender__lastname__icontains=value)
            | Q(loan_id__icontains=value)
        )


class LoanItemFilter(django_filters.FilterSet):
    loan = django_filters.ModelChoiceFilter(
        widget=LoansWidget, queryset=GivenLoan.objects.all()
    )
    status = django_filters.ChoiceFilter(
        choices=LoanFilter.STATUS_CHOICES,
        method="filter_status",
        label="Status",
    )

    def filter_status(self, queryset, name, value):
        if value == "Released":
            return queryset.filter(loan__release__isnull=False)
        elif value == "UnReleased":
            return queryset.filter(loan__release__isnull=True)
        return queryset

    class Meta:
        model = LoanItem
        fields = {
            "loan": ["exact"],
            "itemtype": ["exact"],
            "quantity": ["gte", "lte"],
            "weight": ["gte", "lte"],
            "purity": ["gte", "lte"],
            "loanamount": ["gte", "lte"],
            "interestrate": ["gte", "lte"],
            "interest": ["gte", "lte"],
            "custody_status": ["exact"],
        }


class ReleaseFilter(django_filters.FilterSet):
    loan = django_filters.ModelChoiceFilter(
        widget=LoansWidget, queryset=GivenLoan.objects.filter(release__isnull=False)
    )

    class Meta:
        model = Release
        fields = ["release_id", "loan", "release_date", "loan__series"]
