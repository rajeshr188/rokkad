from uuid import uuid4
from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import loans_action_required
from apps.tenant_apps.loans.services.transaction_reviews import preview_transaction_review, confirm_transaction_review


class TransactionReviewForm(forms.Form):
    through_date = forms.DateField(label="Paper activity checked through", widget=forms.DateInput(attrs={"type": "date"}))
    confirmed_complete = forms.TypedChoiceField(label="Result of checking the records", coerce=lambda value: value == "complete",
        choices=(("complete", "All transactions through this date are entered"), ("incomplete", "Activity is missing or unresolved")))
    source_reference = forms.CharField(max_length=500, label="Paper book / receipts checked, or missing activity", widget=forms.Textarea(attrs={"rows": 3}))
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput())
    review_token = forms.CharField(required=False, widget=forms.HiddenInput())
    acknowledged = forms.BooleanField(required=False, label="I checked the source records and the displayed loan activity.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-check-input" if isinstance(field.widget, forms.CheckboxInput) else "form-control"


@loans_action_required("data.edit")
@never_cache
def review_transactions(request, pk):
    loan = get_object_or_404(m.PawnLoan, pk=pk, workspace=request.loans_workspace)
    form = TransactionReviewForm(request.POST if request.method == "POST" else None,
        initial=dict(request_key=uuid4().hex, through_date=timezone.localdate()))
    review = None
    if request.method == "POST" and form.is_valid():
        data = {k: v for k, v in form.cleaned_data.items() if k not in ("review_token", "acknowledged")}
        try:
            if request.POST.get("action") == "confirm":
                _, created = confirm_transaction_review(loan.pk, actor=request.user, **form.cleaned_data)
                messages.success(request, "Transaction review recorded." if created else "This transaction review was already recorded.")
                return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.workspace.slug, pk=loan.pk)
            review, token = preview_transaction_review(loan.pk, actor=request.user, **data)
            form.data = form.data.copy()
            form.data["review_token"] = token
        except ValueError as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/transaction_review.html", dict(loan=loan, form=form, review=review,
        past_reviews=loan.transaction_reviews.select_related("reviewed_by").order_by("-pk")[:20]))
