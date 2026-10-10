"""Saved, scoped business terms and an optional fictional worked example."""
from datetime import timedelta
from decimal import Decimal

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.domain.monthly_contract import anniversary
from apps.tenant_apps.loans.services.economic_policies import resolve_pawn_loan_fee_policies
from apps.tenant_apps.loans.services.setup_examples import calculate_setup_example


class SetupExampleForm(forms.Form):
    series = forms.ChoiceField(label=_("Numbering series"))
    metal = forms.ChoiceField(label=_("Collateral metal"), choices=(("GOLD", _("Gold")), ("SILVER", _("Silver"))))
    principal = forms.DecimalField(label=_("Example principal (INR)"), initial=10000,
        min_value=Decimal("0.01"), max_value=Decimal("999999999"), max_digits=11, decimal_places=2)
    closing_date = forms.DateField(label=_("Example closing date"), widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, rows, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["series"].choices = [("", _("Choose a series"))] + [
            (str(row["series"].pk), f'{row["series"].pawn_display_name} ({row["series"].license.license_number})') for row in rows]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"


def build_setup_review(*, workspace, setup, query):
    today, rows = setup["as_of_date"], setup["series_rows"]
    configured = [row for row in rows if row["policy"] and row["metals"]]
    initial = {"closing_date": anniversary(today, 1) + timedelta(days=1), "principal": 10000}
    if len(configured) == 1:
        initial.update(series=str(configured[0]["series"].pk), metal=configured[0]["metals"][0]["metal"])
    form = SetupExampleForm(query if "example" in query else initial if len(configured) == 1 else None, rows=rows, initial=initial)
    values = None
    if form.is_bound:
        if form.is_valid():
            values = form.cleaned_data
    elif len(configured) == 1:
        values = {**initial, "closing_date": initial["closing_date"]}
    selected, example, fees = None, None, ()
    if values:
        selected = next((row for row in rows if str(row["series"].pk) == str(values["series"])), None)
        metal = next((item for item in selected["metals"] if item["metal"] == values["metal"]), None) if selected else None
        if not selected or not selected["policy"] or not metal:
            form.add_error("metal", _("Save a calculation policy and an interest rate for this series and metal first."))
        else:
            fees = resolve_pawn_loan_fee_policies(workspace_id=workspace.pk,
                license_id=selected["series"].license_id, as_of_date=today)
            try:
                example = calculate_setup_example(policy=selected["policy"], monthly_rate=metal["rate"].monthly_interest_rate,
                    fees=fees, principal=Decimal(values["principal"]), start=today, end=values["closing_date"])
            except ValueError as exc:
                form.add_error(None, str(exc))
    return {"form": form, "selected": selected, "example": example, "fees": fees,
        "has_loans": PawnLoan.objects.filter(workspace=workspace).exists()}
