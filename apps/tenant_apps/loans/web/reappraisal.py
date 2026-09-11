from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services.collateral_reappraisal import APPRAISAL_METHODS, record_collateral_reappraisal, reappraisal_reference


class CollateralReappraisalForm(forms.Form):
    appraised_value = forms.DecimalField(min_value=Decimal("0.0001"), max_digits=18, decimal_places=4, label="Reviewed appraisal value (INR)")
    method = forms.ChoiceField(choices=APPRAISAL_METHODS)
    evidence_reference = forms.CharField(max_length=255, help_text="Inspection reference or external report number; do not enter a public file URL.")
    review_notes = forms.CharField(widget=forms.Textarea(attrs={"rows": 3}), label="Reason and basis for this appraisal")
    expected_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"


@loans_workspace_required
@require_http_methods(["GET", "POST"])
def collateral_reappraisal(request, pk, item_pk):
    access = request.loans_workspace_access
    may_record = all(access.can(action) for action in ("data.edit", "loan.approve"))
    if request.method == "POST":
        for action in ("data.edit", "loan.approve"):
            access.require(action)
    loan = get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)
    item = get_object_or_404(loan.collateral_items, pk=item_pk, workspace=request.loans_workspace)
    latest = item.appraisals.order_by("-version").first()
    form = CollateralReappraisalForm(request.POST if request.method == "POST" else None,
        initial={"expected_version": latest.version if latest else 0})
    if request.method == "POST" and form.is_valid():
        try:
            record_collateral_reappraisal(loan_id=loan.pk, item_id=item.pk, actor=request.user, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, " ".join(exc.messages))
        else:
            return redirect("workspace_loans:pawn_loan_detail", workspace_slug=request.loans_workspace.slug, pk=loan.pk)
    response = render(request, "loans/pawn/reappraisal.html", {
        "loan": loan, "item": item, "form": form,
        "reference": reappraisal_reference(item, as_of=timezone.now()),
        "appraisals": item.appraisals.select_related("created_by").order_by("-version"),
        "can_record": may_record and loan.state == "ACTIVE" and item.custody_state in {"IN_VAULT", "WITH_FUNDING_LENDER"},
    })
    response["Cache-Control"] = "no-store"
    return response
