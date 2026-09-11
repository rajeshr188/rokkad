"""License creation, renewal evidence and loan-series setup forms."""

from django import forms

from apps.tenant_apps.loans.models import LoanLicense, LoanSeries


class LoanLicenseForm(forms.ModelForm):
    supporting_document = forms.FileField(
        required=False,
        help_text="PDF, PNG, or JPEG up to 10 MB.",
    )

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
        if not self.instance.pk:
            self.fields["supporting_document"].required = True
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")


class LoanLicenseRenewalForm(forms.Form):
    license_number = forms.CharField(max_length=100)
    issuing_authority = forms.CharField(max_length=255, required=False)
    issued_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    expires_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    supporting_document = forms.FileField(
        help_text="Renewal evidence is required. PDF, PNG, or JPEG up to 10 MB."
    )

    def __init__(self, *args, license, **kwargs):
        kwargs.setdefault(
            "initial",
            {
                "license_number": license.license_number,
                "issuing_authority": license.issuing_authority,
                "notes": license.notes,
            },
        )
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        issued_on = cleaned.get("issued_on")
        expires_on = cleaned.get("expires_on")
        if issued_on and expires_on and expires_on < issued_on:
            self.add_error("expires_on", "Expiry date cannot precede issue date.")
        return cleaned


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
