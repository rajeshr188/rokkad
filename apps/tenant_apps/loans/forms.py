from django import forms

from apps.tenant_apps.loans.domain import CollateralMetal
from apps.tenant_apps.loans.models import LoanLicense, LoanSeries, PawnCollateralItem
from apps.tenant_apps.party.models import Party


class LoanLicenseForm(forms.ModelForm):
    class Meta:
        model = LoanLicense
        fields = (
            "name",
            "license_number",
            "issuing_authority",
            "issued_on",
            "expires_on",
            "notes",
        )
        widgets = {
            "issued_on": forms.DateInput(attrs={"type": "date"}),
            "expires_on": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class LoanSeriesSetupForm(forms.ModelForm):
    pawn_loan_prefix = forms.CharField(max_length=24, initial="PL-")
    release_prefix = forms.CharField(max_length=24, initial="RL-")
    number_width = forms.IntegerField(min_value=1, max_value=12, initial=5)
    maximum_number = forms.IntegerField(min_value=1, initial=10000)

    class Meta:
        model = LoanSeries
        fields = ("name", "code", "is_active")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = "form-check-input" if name == "is_active" else "form-control"
            field.widget.attrs.setdefault("class", css_class)


class PawnDraftForm(forms.Form):
    borrower = forms.ModelChoiceField(queryset=Party.objects.none())
    license = forms.ModelChoiceField(queryset=LoanLicense.objects.none())
    series = forms.ModelChoiceField(queryset=LoanSeries.objects.none())
    principal_amount = forms.DecimalField(max_digits=18, decimal_places=2, min_value=0.01)
    monthly_interest_rate = forms.DecimalField(max_digits=9, decimal_places=6, min_value=0)
    loan_date = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    tenure_months = forms.IntegerField(min_value=1, initial=3)

    def __init__(self, *args, workspace, instance=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["borrower"].queryset = Party.objects.filter(
            status=Party.PartyStatus.ACTIVE
        ).order_by("display_name", "party_code")
        self.fields["license"].queryset = LoanLicense.objects.filter(
            workspace=workspace
        ).order_by("license_number")
        self.fields["series"].queryset = LoanSeries.objects.filter(
            license__workspace=workspace
        ).select_related("license").order_by("license__license_number", "code")
        if instance is not None and not self.is_bound:
            self.initial.update(
                {
                    "borrower": instance.borrower_id,
                    "license": instance.license_id,
                    "series": instance.series_id,
                    "principal_amount": instance.principal_amount,
                    "monthly_interest_rate": instance.monthly_interest_rate,
                    "loan_date": instance.loan_date,
                    "tenure_months": instance.tenure_months,
                }
            )
            self.fields["license"].disabled = True
            self.fields["series"].disabled = True
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if isinstance(field, forms.ModelChoiceField) else "form-control")

    def clean(self):
        cleaned = super().clean()
        license = cleaned.get("license")
        series = cleaned.get("series")
        if license and series and series.license_id != license.pk:
            self.add_error("series", "Series must belong to the selected license.")
        return cleaned


class PawnCollateralDraftForm(forms.ModelForm):
    class Meta:
        model = PawnCollateralItem
        fields = (
            "description",
            "metal",
            "gross_weight",
            "net_weight",
            "purity_percentage",
            "latest_appraised_value",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["metal"].choices = [
            (item.value, item.name.title()) for item in CollateralMetal
        ]
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-select" if field is self.fields["metal"] else "form-control")


PawnCollateralDraftFormSet = forms.formset_factory(
    PawnCollateralDraftForm,
    extra=1,
    can_delete=True,
    min_num=1,
    validate_min=True,
)
