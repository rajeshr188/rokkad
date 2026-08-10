import django_filters
from django import forms
from django.db.models import Q

from apps.tenant_apps.loans.models import (
    LoanDocumentIssue,
    LoanLicense,
    LoanSeries,
    PawnLoan,
)


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


class LoanDocumentIssueFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="filter_search",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Issue, source, or profile...",
            }
        ),
    )
    document_type = django_filters.ChoiceFilter(
        choices=LoanDocumentIssue._meta.get_field("document_type").choices,
        empty_label="All document types",
        label="Document type",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    issue_kind = django_filters.ChoiceFilter(
        choices=LoanDocumentIssue.Kind.choices,
        empty_label="All issue kinds",
        label="Issue kind",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    profile_scope = django_filters.ChoiceFilter(
        method="filter_profile_scope",
        choices=(
            *LoanDocumentIssue.PrintProfileSource.choices,
            ("NOT_RECORDED", "Historical / not recorded"),
        ),
        empty_label="All profile sources",
        label="Profile source",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    issued_date_from = django_filters.DateFilter(
        field_name="issued_at",
        lookup_expr="date__gte",
        label="Issued from",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    issued_date_to = django_filters.DateFilter(
        field_name="issued_at",
        lookup_expr="date__lte",
        label="Issued to",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    class Meta:
        model = LoanDocumentIssue
        fields = ()

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        query = (
            Q(source_type__icontains=value)
            | Q(source_id__icontains=value)
            | Q(print_profile_name__icontains=value)
        )
        if value.isdigit():
            query |= Q(pk=int(value))
        return queryset.filter(query)

    def filter_profile_scope(self, queryset, name, value):
        if value == "NOT_RECORDED":
            return queryset.filter(print_profile_source_scope="")
        return queryset.filter(print_profile_source_scope=value)
