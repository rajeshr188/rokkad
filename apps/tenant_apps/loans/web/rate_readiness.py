"""Read-only price preflight; loan commands retain authoritative validation."""

from django import forms
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.domain import ValuationMethod
from apps.tenant_apps.loans.models import LoanSeries
from apps.tenant_apps.loans.selectors.rate_readiness import get_metal_rate_readiness
from apps.tenant_apps.loans.services.economic_policies import resolve_pawn_loan_economic_policy


class RateReadinessForm(forms.Form):
    series = forms.IntegerField(min_value=1)
    as_of = forms.DateField()
    metals = forms.CharField(max_length=40)
    request_key = forms.IntegerField(min_value=0)

    def clean_metals(self):
        metals = tuple(dict.fromkeys(self.cleaned_data["metals"].split(",")))
        if not metals or any(metal not in {"GOLD", "SILVER"} for metal in metals):
            raise forms.ValidationError("Select gold or silver collateral.")
        return metals


@loans_workspace_required
@require_GET
def pawn_valuation_readiness(request):
    if not request.loans_workspace_access.can("data.edit"):
        request.loans_workspace_access.require("data.create")
    form = RateReadinessForm(request.GET)
    context = {
        "request_key": request.GET.get("request_key", ""), "ready": False,
        "message": "Select a series, loan date and collateral metal to check prices.",
    }
    if form.is_valid():
        values = form.cleaned_data
        series = get_object_or_404(LoanSeries, pk=values["series"], workspace=request.loans_workspace)
        try:
            policy = resolve_pawn_loan_economic_policy(
                workspace_id=request.loans_workspace.pk, license_id=series.license_id,
                as_of_date=values["as_of"],
            )
        except ValueError:
            context["message"] = "No calculation policy applies to this series and loan date. Review Economic Setup."
        else:
            needs_rates = policy.valuation_method != ValuationMethod.LATEST_APPRAISAL.value
            rows = get_metal_rate_readiness(
                workspace=request.loans_workspace, as_of_date=values["as_of"], metals=values["metals"],
            ) if needs_rates else []
            context.update(
                ready=not needs_rates or all(row["usable"] for row in rows),
                needs_rates=needs_rates, rows=rows, as_of=values["as_of"],
                message="" if needs_rates else "This policy uses staff appraisal only; a metal price is not required.",
            )
    response = render(request, "loans/pawn/_rate_readiness.html", context)
    response["Cache-Control"] = "no-store"
    return response
