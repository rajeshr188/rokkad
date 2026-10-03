"""Batch review adapter; all financial work stays in the correction command."""
from uuid import uuid4

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION, loans_action_required
from apps.tenant_apps.loans.selectors.recorded_batches import batch_financial_review
from apps.tenant_apps.loans.services.recorded_corrections import dependencies
from apps.tenant_apps.loans.services.recorded_batch_corrections import preview_batch_correction, record_batch_correction
from .recorded_corrections import CorrectionForm
from .release_batches import _style


class BatchCorrectionForm(forms.Form):
    total_received = forms.DecimalField(max_digits=14, decimal_places=2, min_value=0, label="Actual total received for these releases")
    reference = forms.CharField(max_length=255, label="Source confirming the total collection")
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 2}), label="Why these records need correction")
    confirmed_unchanged = forms.BooleanField(label="I checked every included loan. Batch membership, dates, payer and collateral handovers remain correct; unchanged loans still match their source records.")
    request_key = forms.CharField(max_length=40, widget=forms.HiddenInput)
    review_token = forms.CharField(required=False, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(required=False, label="I checked every revised receipt, settlement and the combined total. This records past facts and makes no new collection, refund or collateral handover.")


class BatchReceiptForm(CorrectionForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ("reason", "request_key", "review_token", "confirmed", "settlement_cash_paid", "settlement_interest_offset"):
            del self.fields[key]
        self.fields["settlement_cash_received"].label = "Actual cash received at closure"
        self.fields["settlement_confirmed_unchanged"].label = "The original release date, number and collateral handover remain correct. I checked the actual closure cash above."

    def facts(self):
        values = dict(self.cleaned_data)
        values["date"] = values["date"].isoformat() if values["date"] else None
        values["amount"] = str(values["amount"]) if values["amount"] is not None else None
        settlement = {key.removeprefix("settlement_"): values.pop(key) for key in list(values) if key.startswith("settlement_")}
        settlement["cash_received"] = str(settlement["cash_received"]) if settlement.get("cash_received") is not None else None
        settlement.update(cash_paid="0", interest_offset="0")
        values["settlement"] = settlement
        return values


@loans_action_required(LOANS_ADMIN_ACTION)
@require_http_methods(["GET", "POST"])
@never_cache
def correction(request, batch_pk):
    batch = get_object_or_404(m.PawnReleaseBatch, pk=batch_pk, workspace=request.loans_workspace)
    financial = batch_financial_review(batch)
    data = request.POST if request.method == "POST" else None
    header = _style(BatchCorrectionForm(data, initial={"request_key": uuid4().hex,
        "total_received": format(financial["total"], ".2f")}))
    selections = set(data.getlist("changed_loans")) if data is not None else set()
    rows, known_ids = [], set()
    for line in financial["lines"]:
        loan = line.release.loan
        known_ids.add(str(loan.pk))
        events, active, blockers = dependencies(loan, batch_id=batch.pk)
        selected = str(loan.pk) in selections
        form = BatchReceiptForm(data if selected else None, prefix=f"loan_{loan.pk}",
            receipts=[e for e in events if e.event_kind == "REPAYMENT"],
            settlement=next((e for e in active if e.event_kind == "RELEASE_RECEIPT"), line.release.loan_event))
        rows.append(dict(loan=loan, line=line, form=form, selected=selected, blockers=blockers))
    review = None
    if data is not None:
        valid = header.is_valid()
        if not selections <= known_ids:
            header.add_error(None, "One selected loan is not in this batch.")
            valid = False
        for row in rows:
            if row["selected"]:
                valid = row["form"].is_valid() and valid
        if valid:
            values = {key: value for key, value in header.cleaned_data.items() if key not in ("review_token", "confirmed")}
            values["total_received"] = str(values["total_received"])
            values["loans"] = [dict(loan_id=row["loan"].pk, correction=row["form"].facts() if row["selected"] else None) for row in rows]
            try:
                if data.get("action") == "confirm":
                    created = record_batch_correction(batch.pk, actor=request.user, data=values,
                        review_token=header.cleaned_data["review_token"], confirmed=header.cleaned_data["confirmed"])
                    messages.success(request, "Batch history correction recorded." if created else "This batch correction was already recorded; no duplicate was created.")
                    return redirect("workspace_loans:release_batch_detail", workspace_slug=request.workspace.slug, batch_pk=batch.pk)
                review, token = preview_batch_correction(batch.pk, actor=request.user, data=values)
                header.data = header.data.copy()
                header.data["review_token"] = token
            except (ValueError, ValidationError) as exc:
                header.add_error(None, str(exc))
    return render(request, "loans/batches/correction.html", dict(batch=batch, form=header, rows=rows, review=review))
