"""Fast paper-book entry; business validation stays in the release service."""
import csv
import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.tenant_apps.loans.access import loans_action_required, loans_owner_required, loans_workspace_required
from apps.tenant_apps.loans.models import PawnLoan, PawnReleaseBatch
from apps.tenant_apps.loans.services.paper_closures import (
    MAX_PAPER_LOANS, complete_paper_closures, preview_paper_closures, set_paper_transition, transition_for, _decode,
)


class HeaderForm(forms.Form):
    closure_date = forms.DateField(label="Actual closure date", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    paper_reference = forms.CharField(label="Book / page reference", max_length=100, required=False)
    exception_reason = forms.CharField(max_length=255, required=False, label="Administrator exception reason")
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    quote_token = forms.CharField(required=False, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(required=False, label="The selected rows match the paper records: these amounts were collected and all collateral was returned on the closure date.")


class RowForm(forms.Form):
    include = forms.BooleanField(required=False, label="Record this loan")
    amount = forms.DecimalField(label="Actual collection", min_value=0, max_digits=16, decimal_places=2)
    paid_by = forms.CharField(label="Paid by", max_length=255)
    collector_is_borrower = forms.TypedChoiceField(label="Received by", choices=(("yes", "Borrower"), ("no", "Another person")), coerce=lambda value: value == "yes")
    collector_name = forms.CharField(label="Recipient name", max_length=255)
    relationship = forms.CharField(max_length=100, required=False)
    authorization_note = forms.CharField(label="Authority to collect", max_length=500, required=False)
    paper_reference = forms.CharField(label="Different book / page reference", max_length=100, required=False)
    concession = forms.DecimalField(label="Interest concession", initial=0, min_value=0, max_digits=16, decimal_places=2, required=False)
    concession_reason = forms.CharField(label="Concession reason", max_length=255, required=False)

    def clean(self):
        data = super().clean()
        data["concession"] = data.get("concession") or 0
        if data.get("concession") and not data.get("concession_reason"):
            self.add_error("concession_reason", "Explain the agreed interest concession.")
        if data.get("collector_is_borrower") is False:
            for name in ("relationship", "authorization_note"):
                if not data.get(name):
                    self.add_error(name, "Required for another recipient.")
        return data


def style(form):
    for field in form.fields.values():
        field.widget.attrs.setdefault("class", "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-select" if isinstance(field.widget, forms.Select) else "form-control")
    return form


@loans_action_required("loan.release")
@require_http_methods(["GET", "POST"])
@never_cache
def create(request):
    workspace = request.loans_workspace
    data = request.POST if request.method == "POST" else None
    header = style(HeaderForm(data, initial={"closure_date": timezone.localdate(), "request_key": uuid.uuid4()}))
    context = {"header": header, "transition": transition_for(workspace), "max_loans": MAX_PAPER_LOANS,
        "can_admin": request.loans_workspace_access.can("workspace.settings.manage"),
        "can_owner": request.loans_workspace_access.can("workspace.transfer"), "rows": []}
    ids = data.getlist("loans") if data else []
    forms_by_id = {}
    if data and header.is_valid() and ids:
        values = header.cleaned_data
        completing = data.get("action") == "complete"
        date_changed = False
        if values["quote_token"]:
            try:
                date_changed = _decode(values["quote_token"], workspace)["date"] != values["closure_date"].isoformat()
            except ValueError:
                date_changed = True
        try:
            # Parse at most 50 rows, even when a forged request bypasses the picker.
            if len(ids) > MAX_PAPER_LOANS or len(set(ids)) != len(ids):
                raise ValueError(f"Choose up to {MAX_PAPER_LOANS} different loans.")
            selected = []
            invalid = False
            for pk in ids:
                pk = int(pk)
                form = style(RowForm(data if data.get(f"row_{pk}-amount") is not None and not date_changed else None, prefix=f"row_{pk}"))
                forms_by_id[pk] = form
                if completing and data.get(f"row_{pk}-include"):
                    if form.is_valid():
                        selected.append({"loan_id": pk, **form.cleaned_data})
                    else:
                        invalid = True
            if completing:
                if date_changed:
                    raise ValueError("The closure date changed. Review the recalculated amounts and confirm again.")
                if invalid:
                    raise ValueError("Correct the highlighted selected rows, or deselect them for later.")
                batch = complete_paper_closures(workspace=workspace, actor=request.user,
                    request_key=values["request_key"], quote_token=values["quote_token"], rows=selected,
                    paper_reference=values["paper_reference"], confirmed=values["confirmed"])
                context["completed"] = batch
                recorded = {str(row["loan_id"]) for row in selected}
                ids = [pk for pk in ids if str(pk) not in recorded]
                values["request_key"] = uuid.uuid4()
            if date_changed and not completing:
                context["notice"] = "Closure date changed. Amounts were recalculated; check them against the paper book."
        except (ValueError, ValidationError) as exc:
            context["error"] = str(exc)
        if ids:
            try:
                preview = preview_paper_closures(workspace=workspace, actor=request.user, loan_ids=ids,
                    closure_date=values["closure_date"], exception_reason=values["exception_reason"])
                context["preview"] = preview
                for row in preview["rows"]:
                    loan = row["loan"]
                    old = forms_by_id.get(loan.pk)
                    if old and old.is_bound:
                        form = old
                    else:
                        form = style(RowForm(prefix=f"row_{loan.pk}", initial={"include": not row.get("error"),
                            "amount": format(row["amount"], ".2f") if "amount" in row else "", "paid_by": loan.borrower.display_name,
                            "collector_is_borrower": "yes", "collector_name": loan.borrower.display_name, "concession": 0}))
                    if row.get("error"):
                        form.fields["include"].disabled = True
                    row["form"] = form
                context["rows"] = preview["rows"]
                values["quote_token"] = preview["token"]
            except (ValueError, ValidationError) as exc:
                context["error"] = str(exc)
        values["confirmed"] = False
        context["header"] = style(HeaderForm(initial=values))
    elif data and not ids:
        context["error"] = "Select at least one loan."
    # Keep selections on validation failures as well as partial submissions.
    safe_ids = [int(pk) for pk in ids[:MAX_PAPER_LOANS] if str(pk).isdigit()]
    context["selected_loans"] = PawnLoan.objects.filter(workspace=workspace, pk__in=safe_ids).select_related("borrower")
    return render(request, "loans/paper/create.html", context)


class TransitionForm(forms.Form):
    system_first_date = forms.DateField(required=False, label="System-first start date", widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}))
    retired = forms.BooleanField(required=False, label="Retire routine paper entry (backlog reconciled)")
    reason = forms.CharField(max_length=255, label="Reason / reconciliation reference")


@loans_owner_required
@require_http_methods(["GET", "POST"])
@never_cache
def settings(request):
    row = transition_for(request.loans_workspace)
    form = style(TransitionForm(request.POST if request.method == "POST" else None,
        initial={"system_first_date": row.system_first_date, "retired": row.retired} if row else {}))
    if request.method == "POST" and form.is_valid():
        try:
            set_paper_transition(workspace=request.loans_workspace, actor=request.user, **form.cleaned_data)
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, "Paper closure transition updated for this workspace. Recorded closures are unchanged.")
            return redirect("workspace_loans:paper_closure_settings", workspace_slug=request.workspace.slug)
    return render(request, "loans/paper/settings.html", {"form": form})


@loans_workspace_required
@require_GET
@never_cache
def guide(request):
    return render(request, "loans/paper/guide.html")


@loans_action_required("data.export")
@require_GET
@never_cache
def batch_csv(request, batch_pk):
    batch = get_object_or_404(PawnReleaseBatch, workspace=request.loans_workspace, pk=batch_pk, mode="PAPER")
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="paper-closures-{batch.pk}.csv"'
    writer = csv.writer(response)
    writer.writerow(["Batch", "Closure date", "Recorded at", "Loan", "Borrower", "Release", "Cash", "Interest concession", "Concession reason", "Paid by", "Received by", "Book/page", "Reversed"])
    def cell(value):
        text = str(value)
        return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text
    for line in batch.lines.select_related("release__loan", "release__reversal"):
        release = line.release
        writer.writerow([cell(value) for value in [batch.pk, batch.effective_date.strftime("%d/%m/%Y"), batch.created_at.isoformat(),
            release.loan.loan_number, line.borrower_name, release.release_number, release.settlement_amount,
            release.interest_concession_amount, release.interest_concession_reason, line.paid_by,
            line.collector_name, line.paper_reference, "Yes" if hasattr(release, "reversal") else "No"]])
    return response
