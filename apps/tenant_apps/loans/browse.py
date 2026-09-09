"""Workspace collateral and immutable release browsing."""
import django_filters
import django_tables2 as tables
from django import forms
from django.db.models import Q, CharField, Value
from django.db.models.functions import Cast, Replace
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET
from django.views.decorators.vary import vary_on_headers
from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.filters import _within_storage_hierarchy
from apps.tenant_apps.loans.models import PawnCollateralItem, PawnLoan, PawnLoanRelease, PawnStorageLocation


class CollateralFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="Search items, IDs, loans or borrowers")
    metal = django_filters.ChoiceFilter(choices=PawnCollateralItem._meta.get_field("metal").choices, empty_label="All metals")
    custody_state = django_filters.ChoiceFilter(choices=PawnCollateralItem._meta.get_field("custody_state").choices, label="Custody", empty_label="All custody states")
    loan_state = django_filters.ChoiceFilter(field_name="loan__state", choices=PawnLoan._meta.get_field("state").choices, label="Loan status", empty_label="All loan statuses")
    storage = django_filters.ModelChoiceFilter(queryset=PawnStorageLocation.objects.none(), method="storage_filter", label="Storage (including children)", empty_label="All storage locations")

    class Meta:
        model = PawnCollateralItem
        fields = ()

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.filters["storage"].queryset = PawnStorageLocation.objects.filter(workspace=workspace)

    def search(self, queryset, name, value):
        query = Q(description__icontains=value) | Q(loan__loan_number__icontains=value) | Q(loan__borrower__display_name__icontains=value) | Q(loan__borrower__party_code__icontains=value)
        identity = value.removeprefix("CI-").removeprefix("ci-").replace("-", "")
        if identity and all(c in "0123456789abcdefABCDEF" for c in identity):
            queryset = queryset.alias(item_identity=Replace(Cast("public_id", CharField()), Value("-"), Value("")))
            query |= Q(item_identity__istartswith=identity)
        return queryset.filter(query)

    def storage_filter(self, queryset, name, value):
        return queryset.filter(_within_storage_hierarchy("current_storage_location__", value))


class ReleaseFilter(django_filters.FilterSet):
    q = django_filters.CharFilter(method="search", label="Search release, loan or borrower")
    kind = django_filters.ChoiceFilter(method="filter_kind", choices=(("full", "Full"), ("partial", "Partial")), label="Release type", empty_label="All release types")
    status = django_filters.ChoiceFilter(method="filter_status", choices=(("recorded", "Recorded"), ("reversed", "Reversed")), label="Status", empty_label="All statuses")
    date_from = django_filters.DateFilter(field_name="effective_date", lookup_expr="gte", label="Release date from", widget=forms.DateInput(attrs={"type": "date"}))
    date_to = django_filters.DateFilter(field_name="effective_date", lookup_expr="lte", label="Release date to", widget=forms.DateInput(attrs={"type": "date"}))

    class Meta:
        model = PawnLoanRelease
        fields = ()

    def search(self, queryset, name, value):
        return queryset.filter(Q(release_number__icontains=value) | Q(loan__loan_number__icontains=value) | Q(loan__borrower__display_name__icontains=value) | Q(loan__borrower__party_code__icontains=value))

    def filter_kind(self, queryset, name, value):
        return queryset.filter(is_full_release=value == "full")

    def filter_status(self, queryset, name, value):
        return queryset.filter(reversal__isnull=value == "recorded")


class CollateralTable(tables.Table):
    description = tables.TemplateColumn("""<a hx-boost="false" href="{% url 'loans:pawn_collateral_scan' record.public_id %}">{{ record.description }}</a><div class="small text-muted">CI-{{ record.public_id|cut:"-"|slice:":12"|upper }}</div>""", verbose_name="Collateral", order_by="description")
    borrower = tables.Column(accessor="loan.borrower.display_name", verbose_name="Borrower")
    loan = tables.TemplateColumn("""<a hx-boost="false" href="{% url 'loans:pawn_loan_detail' record.loan_id %}">{{ record.loan.loan_number }}</a><div class="small text-muted">{{ record.loan.get_state_display }}</div>""", order_by="loan__loan_number")
    class Meta:
        model = PawnCollateralItem
        fields = ("description", "borrower", "loan", "metal", "gross_weight", "net_weight", "purity_percentage", "latest_appraised_value", "custody_state", "current_storage_location")
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover align-middle"}
        empty_text = "No collateral matches these filters."


class ReleaseTable(tables.Table):
    release_number = tables.TemplateColumn("""<a hx-boost="false" href="{% url 'loans:pawn_release_detail' record.pk %}">{{ record.release_number }}</a>""", order_by="release_number")
    borrower = tables.Column(accessor="loan.borrower.display_name", verbose_name="Borrower")
    loan = tables.TemplateColumn("""<a hx-boost="false" href="{% url 'loans:pawn_loan_detail' record.loan_id %}">{{ record.loan.loan_number }}</a>""", order_by="loan__loan_number")
    kind = tables.TemplateColumn("""{% if record.is_full_release %}Full{% else %}Partial{% endif %}""", verbose_name="Type", order_by="is_full_release")
    settlement_amount = tables.TemplateColumn("{{ record.settlement_amount|floatformat:2 }}", verbose_name="Settlement (INR)", order_by="settlement_amount")
    status = tables.TemplateColumn("""{% if record.reversal %}Reversed{% else %}Recorded{% endif %}""", orderable=False)
    class Meta:
        model = PawnLoanRelease
        fields = ("release_number", "borrower", "loan", "effective_date", "kind", "settlement_amount", "status")
        template_name = "django_tables2/bootstrap5.html"
        attrs = {"class": "table table-hover align-middle"}
        empty_text = "No releases match these filters."


def _list(request, filterset, table_class, title, description):
    for field in filterset.form.fields.values():
        field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"
    queryset = filterset.qs if filterset.is_valid() else filterset.queryset.none()
    table = table_class(queryset)
    tables.RequestConfig(request, paginate=False).configure(table)
    table.paginate(per_page=25)
    table.page = table.paginator.get_page(request.GET.get("page"))
    fragment = request.headers.get("HX-Request") == "true" and request.headers.get("HX-History-Restore-Request") != "true"
    return render(request, "loans/browse/_content.html" if fragment else "loans/browse/list.html", {"filter": filterset, "table": table, "title": title, "description": description})


@loans_workspace_required
@require_GET
@vary_on_headers("HX-Request", "HX-History-Restore-Request")
def collateral_list(request):
    queryset = PawnCollateralItem.objects.filter(workspace=request.loans_workspace).select_related("loan__borrower", "current_storage_location").order_by("-created_at", "-pk")
    return _list(request, CollateralFilter(request.GET, queryset=queryset, workspace=request.loans_workspace), CollateralTable, "Collateral", "Browse pledged items, their loan status and current custody. Weights are in grams; purity is a percentage.")


@loans_workspace_required
@require_GET
@vary_on_headers("HX-Request", "HX-History-Restore-Request")
def release_list(request):
    queryset = PawnLoanRelease.objects.filter(workspace=request.loans_workspace).select_related("loan__borrower", "reversal").order_by("-effective_date", "-pk")
    return _list(request, ReleaseFilter(request.GET, queryset=queryset), ReleaseTable, "Releases", "Find full and partial releases, including reversed records.")


@loans_workspace_required
@require_GET
def release_detail(request, release_pk):
    release = get_object_or_404(PawnLoanRelease.objects.select_related("loan__borrower", "created_by", "reversal__created_by").prefetch_related("items__collateral_item"), workspace=request.loans_workspace, pk=release_pk)
    return render(request, "loans/browse/release_detail.html", {"release": release})
