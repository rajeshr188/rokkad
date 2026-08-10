import django_filters
from django import forms
from django.db.models import Q

from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnLoan


class PawnLoanFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="filter_search",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Loan number, borrower, party code...",
            }
        ),
    )
    state = django_filters.ChoiceFilter(
        choices=PawnLoan._meta.get_field("state").choices,
        empty_label="All states",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    license = django_filters.ModelChoiceFilter(
        queryset=LoanLicense.objects.none(),
        empty_label="All licenses",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    series = django_filters.ModelChoiceFilter(
        queryset=LoanSeries.objects.none(),
        empty_label="All series",
        label="Series",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    loan_date_from = django_filters.DateFilter(
        field_name="loan_date",
        lookup_expr="gte",
        label="Loan date from",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    loan_date_to = django_filters.DateFilter(
        field_name="loan_date",
        lookup_expr="lte",
        label="Loan date to",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    class Meta:
        model = PawnLoan
        fields = ()

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["license"].queryset = LoanLicense.objects.filter(
            workspace=workspace
        ).order_by("license_number")
        self.filters["series"].queryset = LoanSeries.objects.filter(
            license__workspace=workspace
        ).select_related("license").order_by(
            "license__license_number",
            "code",
        )

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(loan_number__icontains=value)
            | Q(borrower__display_name__icontains=value)
            | Q(borrower__party_code__icontains=value)
            | Q(license__license_number__icontains=value)
            | Q(series__code__icontains=value)
        )
