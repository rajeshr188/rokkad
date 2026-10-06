"""Read-only HTMX suggestion for a draft collateral row."""
from decimal import Decimal, ROUND_DOWN

from django import forms
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate
from apps.tenant_apps.loans.selectors.origination_rates import origination_quote_cutoff
from apps.tenant_apps.loans.models import LoanSeries
from apps.tenant_apps.loans.domain import ValuationMethod
from apps.tenant_apps.loans.domain.valuation_freshness import evidence_freshness
from apps.tenant_apps.loans.services.origination_settings import maximum_quote_age_days
from apps.tenant_apps.loans.domain.collateral_economics import _selected_value
from apps.tenant_apps.loans.services.economic_policies import resolve_pawn_loan_economic_policy
from django.utils import timezone


class AppraisalSuggestionForm(forms.Form):
    metal = forms.ChoiceField(choices=[("GOLD", "Gold"), ("SILVER", "Silver")])
    gross_weight = forms.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    net_weight = forms.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    purity = forms.DecimalField(max_digits=7, decimal_places=4, min_value=Decimal("0.0001"), max_value=100)
    as_of = forms.DateField()
    request_key = forms.IntegerField(min_value=0)
    series = forms.IntegerField(min_value=1, required=False)
    appraisal = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0, required=False)
    principal = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0, required=False)

    def clean(self):
        data = super().clean()
        if data.get("net_weight") and data.get("gross_weight") and data["net_weight"] > data["gross_weight"]:
            raise forms.ValidationError("Net weight cannot exceed gross weight.")
        return data


@loans_workspace_required
@require_GET
def collateral_appraisal_suggestion(request):
    if not request.loans_workspace_access.can("data.edit"):
        request.loans_workspace_access.require("data.create")
    form = AppraisalSuggestionForm(request.GET)
    context = {"request_key": request.GET.get("request_key", ""), "message": "Enter valid weights, purity, and loan date to get a suggestion."}
    if form.is_valid():
        data = form.cleaned_data
        lookup = get_latest_commodity_valuation_rate(commodity_code=data["metal"], as_of=origination_quote_cutoff(data["as_of"]), currency="INR", purity="24k")
        if lookup.status == RATE_FOUND and lookup.rate.buying_rate > 0:
            value = (lookup.rate.buying_rate * data["net_weight"] * data["purity"] / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            if value <= Decimal("9999999999999999.99"):
                context.update(value=format(value, ".2f"), rate=lookup.rate, message="")
            else:
                context["message"] = "The calculated amount is too large. Check weights and rate."
        else:
            context["message"] = "No usable INR pure-metal buying price per gram on or before the loan date. Check Metal prices for this loan above. A manual appraisal alone does not satisfy a policy requiring a metal price."
        if data.get("series"):
            series = get_object_or_404(LoanSeries, pk=data["series"], workspace=request.loans_workspace)
            try:
                policy = resolve_pawn_loan_economic_policy(workspace_id=request.loans_workspace.pk,
                    license_id=series.license_id, series_id=series.pk, as_of_date=data["as_of"])
                context["ltv_percent"] = policy.maximum_ltv_ratio * 100
                method = ValuationMethod(policy.valuation_method)
                calculated = None
                if lookup.status == RATE_FOUND and lookup.rate.buying_rate > 0:
                    calculated = (lookup.rate.buying_rate * data["net_weight"] * data["purity"] / 100).quantize(policy.currency_quantum, rounding=ROUND_DOWN)
                if method != ValuationMethod.LATEST_APPRAISAL:
                    limit = maximum_quote_age_days(request.loans_workspace.pk)
                    status, _ = evidence_freshness(value=lookup.rate.buying_rate if calculated is not None else None,
                        effective_date=timezone.localdate(lookup.rate.effective_at) if calculated is not None else None,
                        as_of_date=timezone.localdate(), maximum_age_days=limit)
                    if status != "CURRENT" or lookup.rate.effective_at > timezone.now():
                        raise ValueError(f"A positive metal price no older than {limit} calendar days is needed to suggest the maximum loan.")
                appraisal = data.get("appraisal")
                if appraisal is None and context.get("value"):
                    appraisal = Decimal(context["value"])
                selected = _selected_value("item", method=method, calculated=calculated, appraisal=appraisal)
                maximum = (selected * policy.maximum_ltv_ratio).quantize(policy.currency_quantum, rounding=ROUND_DOWN)
                context.update(maximum_principal=maximum, selected_value=selected,
                    above_limit=data.get("principal") is not None and data["principal"] > maximum)
            except ValueError as exc:
                context["ltv_message"] = str(exc)
    response = render(request, "loans/pawn/_appraisal_suggestion.html", context)
    response["Cache-Control"] = "no-store"
    return response
