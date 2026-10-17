"""Borrower correction through the ordinary Workspace loan detail."""

from uuid import uuid4

from django import forms
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION, loans_action_required
from apps.tenant_apps.party.models import Party
from apps.tenant_apps.party.widgets import PartyAutocompleteWidget
from apps.tenant_apps.loans.services.borrower_corrections import (
    borrower_correction_blockers,
    preview_borrower_correction,
    record_borrower_correction,
)


class BorrowerCorrectionForm(forms.Form):
    borrower = forms.ModelChoiceField(
        queryset=Party.objects.none(),
        widget=PartyAutocompleteWidget(
            attrs={
                "data-placeholder": "Search by name, party code, phone, relation, or email"
            },
            select2_options={"width": "100%"},
        ),
        label="Correct customer",
    )
    reference = forms.CharField(
        max_length=160, label="Supporting agreement / book reference"
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
        label="I checked the loan agreement and confirm the correct borrower. This corrects a selection mistake; it does not transfer the loan to another person.",
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        field = self.fields["borrower"]
        field.queryset = Party.objects.filter(
            workspace=workspace, status=Party.PartyStatus.ACTIVE
        ).order_by("display_name", "party_code")
        field.widget.data_url = reverse(
            "workspace_party:party_autocomplete", args=[workspace.slug]
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "form-check-input"
                    if isinstance(field, forms.BooleanField)
                    else "form-control"
                ),
            )


@loans_action_required(LOANS_ADMIN_ACTION)
@never_cache
def borrower_correction(request, pk):
    loan = get_object_or_404(
        m.PawnLoan.objects.select_related("borrower"),
        pk=pk,
        workspace=request.loans_workspace,
    )
    blockers = borrower_correction_blockers(loan)
    form = BorrowerCorrectionForm(
        request.POST if request.method == "POST" else None,
        workspace=request.loans_workspace,
        initial=dict(borrower=loan.borrower_id, request_key=uuid4().hex),
    )
    review = None
    if request.method == "POST" and form.is_valid():
        data = dict(
            borrower_id=form.cleaned_data["borrower"].pk,
            **{
                key: form.cleaned_data[key]
                for key in ("reference", "reason", "request_key")
            },
        )
        try:
            if request.POST.get("action") == "confirm":
                _, created = record_borrower_correction(
                    loan.pk,
                    actor=request.user,
                    data=data,
                    review_token=form.cleaned_data["review_token"],
                    confirmed=form.cleaned_data["confirmed"],
                )
                messages.success(
                    request,
                    (
                        "Borrower correction recorded."
                        if created
                        else "This borrower correction was already recorded."
                    ),
                )
                return redirect(
                    "workspace_loans:pawn_loan_detail",
                    workspace_slug=request.workspace.slug,
                    pk=loan.pk,
                )
            review, token = preview_borrower_correction(
                loan.pk, actor=request.user, data=data
            )
            form.data = form.data.copy()
            form.data["review_token"] = token
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
    from apps.tenant_apps.loans.selectors.correction_guidance import (
        correction_next_steps,
    )

    return render(
        request,
        "loans/pawn/borrower_correction.html",
        dict(
            loan=loan,
            form=form,
            review=review,
            blockers=blockers,
            correction_next_steps=correction_next_steps(loan, blockers),
        ),
    )
