"""Read-only policy guidance and a bounded, fictional simple-interest example."""
from datetime import date, timedelta
from decimal import Decimal

from django import forms
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.domain.interest import partial_period_fraction, calculate_period_interest
from apps.tenant_apps.loans.services.pawn_interest import _add_months
from .economic_forms import PawnEconomicConfigurationForm


class InterestExampleForm(forms.Form):
    principal = forms.DecimalField(label="Example principal (INR)", min_value=Decimal("0.01"),
        max_value=Decimal("999999999"), max_digits=11, decimal_places=2, initial=10000)
    monthly_rate = forms.DecimalField(label="Monthly interest (%)", min_value=0, max_value=100,
        max_digits=9, decimal_places=6, initial=3)
    start = forms.DateField(label="Loan date", initial=date(2026, 3, 1),
        widget=forms.DateInput(attrs={"type": "date"}))
    end = forms.DateField(label="Interest through (inclusive)", initial=date(2026, 4, 8),
        widget=forms.DateInput(attrs={"type": "date"}))
    method = forms.ChoiceField(label="After the first month", initial="STARTED_WEEKS",
        choices=PawnEconomicConfigurationForm.base_fields["partial_month_method"].choices)
    cutoff = forms.IntegerField(label="Slab cutoff (inclusive days)", min_value=1, max_value=30, initial=15)
    lower_fraction = forms.DecimalField(label="Slab month fraction", min_value=Decimal(".0001"),
        max_value=1, max_digits=5, decimal_places=4, initial=Decimal(".5"))
    advance_periods = forms.IntegerField(label="Months collected upfront", min_value=0, max_value=12, initial=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"

    def clean(self):
        values = super().clean()
        if values.get("start") and values.get("end"):
            if not 0 <= (values["end"] - values["start"]).days <= 730:
                self.add_error("end", "Choose a date on or after the loan date, within two years.")
        return values


def calculate_example(*, principal, monthly_rate, start, end, method, cutoff, lower_fraction, advance_periods):
    """Use the servicing engine's period, fraction and paise rounding functions."""
    if not 0 <= (end - start).days <= 730:
        raise ValueError("Example must cover at most two years.")
    _, monthly = calculate_period_interest(calculation_base=principal, monthly_interest_rate=monthly_rate,
        period_fraction=1, currency_quantum=Decimal(".01"))
    advance = monthly * advance_periods
    remaining_advance, total, rows = advance, Decimal(0), []
    period_start = start
    while period_start <= end:
        next_start = _add_months(period_start, 1)
        period_end = min(end, next_start - timedelta(days=1))
        days = (next_start - period_start).days
        elapsed = (period_end - period_start).days + 1
        fraction = partial_period_fraction(method=method, elapsed_days=elapsed, period_days=days,
            minimum_first_month=True, period_number=len(rows) + 1, cutoff_days=cutoff, lower_fraction=lower_fraction)
        _, calculated = calculate_period_interest(calculation_base=principal, monthly_interest_rate=monthly_rate,
            period_fraction=fraction, currency_quantum=Decimal(".01"))
        applied = min(remaining_advance, calculated)
        remaining_advance -= applied
        total += calculated
        rows.append(dict(number=len(rows)+1, start=period_start, end=period_end, days=days,
            elapsed=elapsed, fraction=fraction, calculated=calculated, advance=applied, additional=calculated-applied))
        period_start = next_start
    return dict(rows=rows, total=total, advance=advance, applied=advance-remaining_advance,
        additional=total-advance+remaining_advance, unused_advance=remaining_advance)


@loans_setup_required
@never_cache
@require_GET
def interest_policy_help(request):
    form = InterestExampleForm(request.GET if request.GET else None)
    result = calculate_example(**form.cleaned_data) if form.is_bound and form.is_valid() else None
    return render(request, "loans/setup/interest_help.html", {"form": form, "example": result})
