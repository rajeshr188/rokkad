from decimal import Decimal

import django_filters
from django.db.models import Q

from apps.tenant_apps.contact.forms import CustomerWidget
from apps.tenant_apps.contact.models import Customer

from .forms import LoansWidget
from .models import Loan, LoanItem, LoanPayment, Release


class LoanFilter(django_filters.FilterSet):
    query = django_filters.CharFilter(method="universal_search", label="Search")
    customer = django_filters.ModelChoiceFilter(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(),
    )
    loan_date = django_filters.DateFromToRangeFilter(
        field_name="loan_date",
        help_text="dd/mm/yy", label="Loan Date"
    )
    date = django_filters.DateRangeFilter(field_name="loan_date", label="Loan Date")

    # notice = django_filters.CharFilter(
    #     field_name="notifications__notice_type", lookup_expr="icontains"
    # )
    # loan_type = django_filters.ChoiceFilter(
    #     choices=Loan.LoanType.choices, empty_label="Select Loan Type"
    # )
    def filter_item_type(self, queryset, name, value):
        return queryset.filter(loanitems__itemtype=value)

    item_type = django_filters.ChoiceFilter(
        method="filter_item_type",
        choices=LoanItem.ItemType.choices,
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
        model = Loan
        fields = [
            "query",
            "series",
            "customer",
        ]

    def universal_search(self, queryset, name, value):
        if value.replace(".", "", 1).isdigit():
            value = Decimal(value)
            return (
                Loan.objects.with_details(None, None)
                .prefetch_related("notifications", "loanitems")
                .filter(Q(id=value) | Q(lid=value) | Q(loan_amount=value))
            )

        return (
            Loan.objects.with_details(None, None)
            .prefetch_related("notifications", "loanitems")
            .filter(
                Q(id__icontains=value)
                | Q(customer__name__icontains=value)
                | Q(lid__icontains=value)
                | Q(loan_id__icontains=value)
                | Q(item_desc__icontains=value)
                | Q(loan_amount__icontains=value)
            )
        )

    # causes trouble in the table while filtering by id
    def sunken(self, queryset, name, value):
        return queryset.filter(is_overdue=value)


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
        widget=LoansWidget, queryset=Loan.released.all()
    )

    class Meta:
        model = Release
        fields = ["release_id", "loan", "release_date"]
