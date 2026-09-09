"""Read-only HTMX suggestion for a draft collateral row."""
from decimal import Decimal, ROUND_DOWN

from django import forms
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate


class AppraisalSuggestionForm(forms.Form):
    metal = forms.ChoiceField(choices=[("GOLD", "Gold"), ("SILVER", "Silver")])
    gross_weight = forms.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    net_weight = forms.DecimalField(max_digits=14, decimal_places=4, min_value=Decimal("0.0001"))
    purity = forms.DecimalField(max_digits=7, decimal_places=4, min_value=Decimal("0.0001"), max_value=100)
    as_of = forms.DateField()
    request_key = forms.IntegerField(min_value=0)

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
        lookup = get_latest_commodity_valuation_rate(commodity_code=data["metal"], as_of=data["as_of"], currency="INR", purity="24k")
        if lookup.status == RATE_FOUND and lookup.rate.buying_rate > 0:
            value = (lookup.rate.buying_rate * data["net_weight"] * data["purity"] / Decimal("100")).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
            if value <= Decimal("9999999999999999.99"):
                context.update(value=format(value, ".2f"), rate=lookup.rate, message="")
            else:
                context["message"] = "The calculated amount is too large. Check weights and rate."
        else:
            context["message"] = "No usable INR 24K buying rate on or before the loan date. Add a buying rate in Rates or enter an appraisal manually."
    response = render(request, "loans/pawn/_appraisal_suggestion.html", context)
    response["Cache-Control"] = "no-store"
    return response
