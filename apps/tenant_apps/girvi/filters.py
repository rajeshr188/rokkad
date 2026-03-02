import django_filters
from django.db.models import Q
from django_filters.widgets import RangeWidget

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer

from .forms import LoansWidget
from .models import ItemType, GivenLoan, LoanItem, LoanPayment, Release


class LoanFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="universal_search", label="Search")
    borrower = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(),
    )

    loan_date_range = django_filters.DateFromToRangeFilter(
        field_name="loan_date",
        label="Loan Date Range",
        widget=RangeWidget(attrs={"type": "date"}),
    )
    date = django_filters.DateRangeFilter(field_name="loan_date", label="Loan Date")

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
        # if value.replace(".", "", 1).isdigit():
        #     value = Decimal(value)
        #     return (
        #         Loan.objects.with_details(None, None,None)
        #         .prefetch_related("notifications", "loanitems")
        #         .filter(Q(id=value) | Q(loan_amount=value))
        #     )

        return (
            GivenLoan.objects.for_table_display()
            .prefetch_related("notifications", "loanitems")
            .filter(
                Q(id__icontains=value)
                | Q(borrower__firstname__icontains=value)
                | Q(borrower__lastname__icontains=value)
                | Q(loan_id__icontains=value)
                | Q(item_desc__icontains=value)
            )
        )

    # Filter for sunken/overdue loans - adds annotation first
    def sunken(self, queryset, name, value):
        # Add the overdue annotation before filtering
        queryset = queryset.with_overdue_status()
        return queryset.filter(is_overdue=value)


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


class LoanPaymentFilter(django_filters.FilterSet):
    class Meta:
        model = LoanPayment
        fields = ["loan"]


class LoanPaymentFilter(django_filters.FilterSet):
    class Meta:
        model = LoanPayment
        fields = ["loan"]


class ReleaseFilter(django_filters.FilterSet):
    loan = django_filters.ModelChoiceFilter(
        widget=LoansWidget, queryset=GivenLoan.objects.filter(release__isnull=False)
    )

    class Meta:
        model = Release
        fields = ["release_id", "loan", "release_date", "loan__series"]
