"""Small operator forms over existing scoped policy services."""

from django import forms
from django.utils import timezone

from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, LoanEntryPreference
from .economic_forms import PawnEconomicConfigurationForm, GroupedPolicyForm


class BusinessLendingTermsForm(PawnEconomicConfigurationForm):
    # Keep the old wire field for open forms/reviews; new UI has a separate action.
    groups = tuple(
        (title, tuple(name for name in names if name != "default_entry_purpose"))
        for title, names in PawnEconomicConfigurationForm.groups
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["default_entry_purpose"].widget = forms.HiddenInput()


class LendingScopeForm(GroupedPolicyForm, forms.Form):
    license = forms.ModelChoiceField(
        queryset=LoanLicense.objects.none(),
        required=False,
        label="Licence (optional)",
        empty_label="Business default",
    )
    series = forms.ModelChoiceField(
        queryset=LoanSeries.objects.none(),
        required=False,
        label="Register (optional)",
        empty_label="All registers in this scope",
    )
    effective_from = forms.DateField(
        initial=timezone.localdate,
        label="Applies from",
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["license"].queryset = LoanLicense.objects.filter(
            workspace=workspace
        )
        self.fields["series"].queryset = (
            LoanSeries.objects.filter(workspace=workspace)
            .select_related("license")
            .prefetch_related("number_sequences")
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                (
                    "form-select"
                    if isinstance(field, forms.ChoiceField)
                    else "form-control"
                ),
            )

    def clean(self):
        data = super().clean()
        license, series = data.get("license"), data.get("series")
        if series:
            if license and series.license_id != license.pk:
                self.add_error("series", "Choose a register under this licence.")
            data["license"] = series.license
        return data


class LendingRatesForm(LendingScopeForm):
    gold_monthly_interest_rate = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        min_value=0,
        max_value=100,
        label="Gold monthly interest (%)",
    )
    silver_monthly_interest_rate = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        min_value=0,
        max_value=100,
        label="Silver monthly interest (%)",
    )
    bronze_monthly_interest_rate = forms.DecimalField(
        required=False,
        max_digits=9,
        decimal_places=6,
        min_value=0,
        max_value=100,
        label="Bronze monthly interest (%)",
    )
    groups = (
        ("Scope and date", ("license", "series", "effective_from")),
        (
            "Change only these rates; blank metals keep their current rates",
            (
                "gold_monthly_interest_rate",
                "silver_monthly_interest_rate",
                "bronze_monthly_interest_rate",
            ),
        ),
    )


class LendingTermsAmendForm(LendingScopeForm):
    default_tenure_months = forms.IntegerField(
        required=False, min_value=1, max_value=600, label="Standard tenure (months)"
    )
    advance_interest_periods = forms.IntegerField(
        required=False,
        min_value=0,
        max_value=12,
        label="Months of interest collected upfront",
    )
    groups = (
        ("Scope and date", ("license", "series", "effective_from")),
        (
            "Change only these terms; blanks keep the applicable value",
            ("default_tenure_months", "advance_interest_periods"),
        ),
    )


class LoanEntryPreferenceForm(LendingScopeForm):
    purpose = forms.ChoiceField(
        choices=LoanEntryPreference._meta.get_field("purpose").choices,
        label="Default New loan screen",
    )
    groups = (("Scope", ("license", "series")), ("Entry preference", ("purpose",)))

    def __init__(self, *args, **kwargs):
        kwargs["initial"] = dict(
            kwargs.get("initial") or {}, effective_from=timezone.localdate()
        )
        super().__init__(*args, **kwargs)
        self.fields["effective_from"].widget = forms.HiddenInput()


class LendingTermsPreviewForm(LendingScopeForm):
    groups = (("View the effective terms", ("license", "series", "effective_from")),)
