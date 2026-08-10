from uuid import UUID

import django_filters
from django import forms
from django.db.models import Q

from apps.tenant_apps.loans.models import (
    LoanDocumentIssue,
    LoanLicense,
    LoanSeries,
    PawnLoan,
    PawnPhysicalVerificationSession,
    PawnStorageLocation,
)


def _within_storage_hierarchy(field_prefix, location):
    return (
        Q(**{f"{field_prefix}pk": location.pk})
        | Q(**{f"{field_prefix}parent_id": location.pk})
        | Q(**{f"{field_prefix}parent__parent_id": location.pk})
        | Q(**{f"{field_prefix}parent__parent__parent_id": location.pk})
        | Q(**{f"{field_prefix}parent__parent__parent__parent_id": location.pk})
    )


def _storage_text_query(field_prefix, value):
    query = Q(**{f"{field_prefix}code__icontains": value}) | Q(
        **{f"{field_prefix}name__icontains": value}
    )
    parent_prefix = f"{field_prefix}parent__"
    for _ in range(4):
        query |= Q(**{f"{parent_prefix}code__icontains": value})
        query |= Q(**{f"{parent_prefix}name__icontains": value})
        parent_prefix += "parent__"
    return query


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


class PawnStorageLocationFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="filter_search",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Location code, name, or path...",
            }
        ),
    )
    within = django_filters.ModelChoiceFilter(
        method="filter_within",
        queryset=PawnStorageLocation.objects.none(),
        empty_label="All locations",
        label="Within hierarchy",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    level = django_filters.ChoiceFilter(
        choices=PawnStorageLocation.Level.choices,
        empty_label="All levels",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = django_filters.ChoiceFilter(
        method="filter_status",
        choices=(("ACTIVE", "Active"), ("INACTIVE", "Inactive")),
        empty_label="All states",
        label="State",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    class Meta:
        model = PawnStorageLocation
        fields = ()

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["within"].queryset = PawnStorageLocation.objects.filter(
            workspace=workspace
        ).select_related(
            "parent",
            "parent__parent",
            "parent__parent__parent",
            "parent__parent__parent__parent",
        )

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(_storage_text_query("", value))

    def filter_within(self, queryset, name, value):
        return queryset.filter(_within_storage_hierarchy("", value))

    def filter_status(self, queryset, name, value):
        return queryset.filter(is_active=value == "ACTIVE")


class PawnPhysicalVerificationSessionFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(
        method="filter_search",
        label="Search",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "placeholder": "Session, scope, or operator...",
            }
        ),
    )
    within = django_filters.ModelChoiceFilter(
        method="filter_within",
        queryset=PawnStorageLocation.objects.none(),
        empty_label="All locations",
        label="Within hierarchy",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    status = django_filters.ChoiceFilter(
        choices=PawnPhysicalVerificationSession.Status.choices,
        empty_label="All statuses",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    started_date_from = django_filters.DateFilter(
        field_name="started_at",
        lookup_expr="date__gte",
        label="Started from",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    started_date_to = django_filters.DateFilter(
        field_name="started_at",
        lookup_expr="date__lte",
        label="Started to",
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )

    class Meta:
        model = PawnPhysicalVerificationSession
        fields = ()

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["within"].queryset = PawnStorageLocation.objects.filter(
            workspace=workspace
        ).select_related(
            "parent",
            "parent__parent",
            "parent__parent__parent",
            "parent__parent__parent__parent",
        )

    def filter_search(self, queryset, name, value):
        value = value.strip()
        if not value:
            return queryset
        query = (
            _storage_text_query("scope_location__", value)
            | Q(started_by__username__icontains=value)
            | Q(completed_by__username__icontains=value)
        )
        try:
            public_id = UUID(value)
        except (TypeError, ValueError):
            public_id = None
        if public_id is not None:
            query |= Q(public_id=public_id)
        return queryset.filter(query)

    def filter_within(self, queryset, name, value):
        return queryset.filter(
            _within_storage_hierarchy("scope_location__", value)
        )
