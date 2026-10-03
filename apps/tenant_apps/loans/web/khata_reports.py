"""Private operational Khata reports and authorized bounded CSV downloads."""
from django import forms
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.http import content_disposition_header
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.selectors.khata_reports import cash_operations, cash_totals, cash_row, custody_items, custody_totals
from apps.tenant_apps.loans.services.khata_report_exports import export_csv
from .khata_views import RegisterForm, _private


class ReportForm(RegisterForm):
    borrower = forms.IntegerField(required=False, min_value=1, max_value=2**63 - 1, widget=forms.HiddenInput())
    account = forms.IntegerField(required=False, min_value=1, max_value=2**63 - 1, widget=forms.HiddenInput())
    from_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    to_date = forms.DateField(required=False, widget=forms.DateInput(attrs={"type": "date"}))
    kind = forms.ChoiceField(label="Cash / correction event", required=False, choices=(("", "All cash and corrections"),
        ("WITHDRAW", "Withdrawals"), ("INTEREST", "Interest receipts"), ("REVISE", "Reduction principal receipts"),
        ("SETTLE", "Settlements"), ("CORRECT", "Corrections")))
    custody = forms.ChoiceField(label="Current custody", required=False, choices=(("physical", "Physically held, including pending"),
        ("held", "Held, not reserved"), ("pending", "Awaiting handover"), ("returned", "Returned"), ("all", "All recorded items")))
    metal = forms.ChoiceField(required=False, choices=(("", "Both metals"), ("GOLD", "Gold"), ("SILVER", "Silver")))

    def __init__(self, *args, section, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("state", "attention", *(('custody', 'metal') if section == 'cash' else ('kind',))):
            self.fields.pop(name)
        self.fields["q"].label = "Number, borrower or payment reference" if section == "cash" else "Number, borrower, item or storage"
        self.fields["from_date"].label = "Business date from" if section == "cash" else "Received from (optional)"
        self.fields["to_date"].label = "Business date through" if section == "cash" else "Received through (optional)"
        if section == "cash":
            self.fields["from_date"].required = self.fields["to_date"].required = True
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean(self):
        data = super().clean()
        if data.get("from_date") and data.get("to_date") and data["from_date"] > data["to_date"]:
            self.add_error("to_date", "Through date must be on or after the from date.")
        for name in ("from_date", "to_date"):
            if data.get(name) and data[name] > timezone.localdate():
                self.add_error(name, "Choose today or an earlier date.")
        return data


@loans_workspace_required
@never_cache
@require_GET
def reports(request):
    workspace = request.loans_workspace
    section = request.GET.get("section", "cash")
    if section not in ("cash", "custody"):
        raise Http404("Unknown Khata report.")
    if request.GET.get("export"):
        request.loans_workspace_access.require("report.export")
        if request.GET["export"] != "csv":
            raise Http404("Khata reports currently support CSV downloads.")
    params = request.GET.copy()
    params.pop("export", None)
    params.pop("page", None)
    params["section"] = section
    if section == "cash":
        for name in ("from_date", "to_date"):
            if name not in params:
                params[name] = timezone.localdate().isoformat()
        if "sort" not in params:
            params["sort"] = "oldest"
    form = ReportForm(params, workspace=workspace, section=section)
    qs, totals = None, None
    if form.is_valid():
        qs = (cash_operations if section == "cash" else custody_items)(workspace=workspace, data=form.cleaned_data)
        totals = cash_totals(qs) if section == "cash" else custody_totals(qs)
    if request.GET.get("export"):
        if not form.is_valid():
            return _private(HttpResponse("Invalid report filters. Review the report form before exporting.", status=400, content_type="text/plain"))
        try:
            content = export_csv(workspace=workspace, section=section, queryset=qs, absolute_url=request.build_absolute_uri)
        except ValueError as exc:
            return _private(HttpResponse(str(exc), status=409, content_type="text/plain"))
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = content_disposition_header(True, f"khata-{section}-{timezone.localdate()}.csv")
        return _private(response)
    page = Paginator(qs if qs is not None else [], 25).get_page(request.GET.get("page"))
    rows = [cash_row(op) for op in page] if section == "cash" else page
    return _private(render(request, "loans/khata/reports.html", dict(form=form, section=section, page=page, rows=rows,
        totals=totals, query=params.urlencode(), as_of=timezone.localdate(), valid=form.is_valid(),
        can_export=request.loans_workspace_access.can("report.export"))))
