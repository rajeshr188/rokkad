"""One ordinary correction form for an existing collateral identity."""

from uuid import uuid4
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION, loans_action_required
from apps.tenant_apps.loans.domain import CollateralMetal
from apps.tenant_apps.loans.services.collateral_corrections import (
    FIELDS,
    collateral_correction_blockers,
    item_details,
    preview_collateral_correction,
    record_collateral_correction,
)


class CollateralCorrectionForm(forms.Form):
    description = forms.CharField(max_length=255)
    quantity = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=10000,
        help_text="Piece count. Each row's weights are totals; they are not multiplied by quantity.",
    )
    metal = forms.ChoiceField(
        choices=[(value.value, value.value.title()) for value in CollateralMetal]
    )
    gross_weight = forms.DecimalField(
        required=False,
        max_digits=14,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        label="Gross weight (g)",
    )
    net_weight = forms.DecimalField(
        max_digits=14,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        label="Net weight (g)",
    )
    purity_percentage = forms.DecimalField(
        max_digits=7,
        decimal_places=4,
        min_value=Decimal("0.0001"),
        max_value=100,
        label="Purity (%)",
    )
    reference = forms.CharField(
        max_length=160, label="Supporting agreement / inspection / book reference"
    )
    reason = forms.CharField(
        max_length=500,
        widget=forms.Textarea(attrs={"rows": 3}),
        label="Reason for correction",
    )
    request_key = forms.CharField(max_length=80, widget=forms.HiddenInput)
    review_token = forms.CharField(required=False, widget=forms.HiddenInput)
    confirmed = forms.BooleanField(
        required=False,
        label="I checked these facts. This corrects an entry mistake, not an exchange, return or new pledge.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "form-check-input"
                    if isinstance(field, forms.BooleanField)
                    else (
                        "form-select"
                        if isinstance(field, forms.ChoiceField)
                        else "form-control"
                    )
                ),
            )


@loans_action_required(LOANS_ADMIN_ACTION)
@never_cache
def collateral_correction(request, pk, item_pk):
    loan = get_object_or_404(m.PawnLoan, pk=pk, workspace=request.loans_workspace)
    item = get_object_or_404(
        m.PawnCollateralItem, pk=item_pk, loan=loan, workspace=request.loans_workspace
    )
    blockers = collateral_correction_blockers(loan)
    form = CollateralCorrectionForm(
        request.POST if request.method == "POST" else None,
        initial=dict(item_details(item), request_key=uuid4().hex),
    )
    review = None
    if request.method == "POST" and form.is_valid():
        data = dict(
            item_id=item.pk,
            after={key: form.cleaned_data[key] for key in FIELDS},
            **{
                key: form.cleaned_data[key]
                for key in ("reference", "reason", "request_key")
            },
        )
        try:
            if request.POST.get("action") == "confirm":
                _, created = record_collateral_correction(
                    loan.pk,
                    actor=request.user,
                    data=data,
                    review_token=form.cleaned_data["review_token"],
                    confirmed=form.cleaned_data["confirmed"],
                )
                messages.success(
                    request,
                    (
                        "Collateral correction recorded."
                        if created
                        else "This collateral correction was already recorded."
                    ),
                )
                return redirect(
                    "workspace_loans:pawn_loan_detail",
                    workspace_slug=request.workspace.slug,
                    pk=loan.pk,
                )
            review, token = preview_collateral_correction(
                loan.pk, actor=request.user, data=data
            )
            form.data = form.data.copy()
            form.data["review_token"] = token
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
    changes = [
        dict(
            label=form.fields[key].label or key.replace("_", " ").capitalize(),
            before=review["before"][key],
            after=review["after"][key],
        )
        for key in FIELDS
        if review and review["before"][key] != review["after"][key]
    ]
    return render(
        request,
        "loans/pawn/collateral_correction.html",
        dict(
            loan=loan,
            item=item,
            form=form,
            blockers=blockers,
            review=review,
            changes=changes,
        ),
    )
