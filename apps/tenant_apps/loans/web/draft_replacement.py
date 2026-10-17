"""Review a replacement preparation draft using the ordinary writer."""

from uuid import uuid4

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import loans_action_required
from apps.tenant_apps.loans.services.draft_replacement import (
    preview_draft_replacement,
    replace_draft,
)
from apps.tenant_apps.loans.services.origination_summary import (
    replacement_origination_summary,
)


class ReplacementForm(forms.Form):
    series = forms.ModelChoiceField(
        queryset=m.LoanSeries.objects.none(), label="Correct register / series"
    )
    product_version = forms.ModelChoiceField(
        queryset=m.LoanProductVersion.objects.none(), label="Correct loan product"
    )
    loan_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    tenure_months = forms.IntegerField(min_value=1, max_value=600)
    reason = forms.CharField(max_length=500, widget=forms.Textarea(attrs={"rows": 2}))
    request_key = forms.UUIDField(widget=forms.HiddenInput)
    review_token = forms.CharField(required=False, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(
        required=False,
        label="I checked the replacement terms and number. Cancel the original draft and keep its history.",
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.tenant_apps.loans.selectors.series import running_series

        self.fields["series"].queryset = running_series(workspace)
        self.fields["product_version"].queryset = m.LoanProductVersion.objects.filter(
            product__workspace=workspace, product__is_active=True, status="ACTIVE"
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "form-check-input"
                    if isinstance(field, forms.BooleanField)
                    else (
                        "form-select"
                        if isinstance(field, forms.ModelChoiceField)
                        else "form-control"
                    )
                ),
            )


@loans_action_required("data.edit")
@loans_action_required("data.create")
@require_http_methods(["GET", "POST"])
@never_cache
def replacement(request, pk):
    loan = get_object_or_404(m.PawnLoan, pk=pk, workspace=request.loans_workspace)
    form = ReplacementForm(
        request.POST if request.method == "POST" else None,
        workspace=request.loans_workspace,
        initial=dict(
            series=loan.series_id,
            product_version=loan.product_version_id,
            loan_date=loan.loan_date,
            tenure_months=loan.tenure_months,
            request_key=uuid4(),
        ),
    )
    preview = None
    if request.method == "POST" and form.is_valid():
        values = dict(
            series_id=form.cleaned_data["series"].pk,
            product_version_id=form.cleaned_data["product_version"].pk,
            **{
                key: form.cleaned_data[key]
                for key in ("loan_date", "tenure_months", "reason", "request_key")
            },
        )
        try:
            if request.POST.get("action") == "confirm":
                result, created = replace_draft(
                    loan.pk,
                    actor=request.user,
                    values=values,
                    token=form.cleaned_data["review_token"],
                    confirmed=form.cleaned_data["confirmed"],
                )
                messages.success(
                    request,
                    (
                        "Replacement draft created; original draft retained and cancelled."
                        if created
                        else "This replacement was already recorded."
                    ),
                )
                return redirect(
                    "workspace_loans:pawn_loan_detail",
                    workspace_slug=request.workspace.slug,
                    pk=result.pk,
                )
            preview, token = preview_draft_replacement(
                loan.pk, actor=request.user, values=values
            )
            preview["agreement"] = replacement_origination_summary(preview, values)
            form.data = form.data.copy()
            form.data["review_token"] = token
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
    return render(
        request,
        "loans/pawn/draft_replacement.html",
        dict(loan=loan, form=form, preview=preview),
    )
