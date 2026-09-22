"""License creation, renewal evidence and loan-series setup forms."""

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.tenant_apps.loans.models import LoanLicense, LoanSeries


LICENSE_LABELS = {
    "name": _("License name"), "license_number": _("License number"),
    "issuing_authority": _("Issuing authority"), "issued_on": _("Valid from"),
    "expires_on": _("Valid until"), "notes": _("Notes"),
    "supporting_document": _("Supporting document"),
}


class LoanLicenseForm(forms.ModelForm):
    supporting_document = forms.FileField(
        required=False,
        help_text=_("PDF, PNG, or JPEG up to 10 MB. Required for a new license; optional when amending one."),
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.png,.jpg,.jpeg"}),
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
        self.fields["issued_on"].required = True
        self.fields["expires_on"].required = True
        if not self.instance.pk:
            self.fields["supporting_document"].required = True
        self.fields["name"].help_text = _("A short name staff can recognize, such as Main branch license.")
        for name, field in self.fields.items():
            field.label = LICENSE_LABELS[name]
            field.widget.attrs.setdefault("class", "form-control")


class LoanLicenseRenewalForm(forms.Form):
    license_number = forms.CharField(max_length=100)
    issuing_authority = forms.CharField(max_length=255, required=False)
    issued_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    expires_on = forms.DateField(widget=forms.DateInput(attrs={"type": "date"}))
    notes = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))
    supporting_document = forms.FileField(
        help_text=_("Renewal evidence is required. PDF, PNG, or JPEG up to 10 MB."),
        widget=forms.ClearableFileInput(attrs={"accept": ".pdf,.png,.jpg,.jpeg"}),
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
        for name, field in self.fields.items():
            field.label = LICENSE_LABELS[name]
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        issued_on = cleaned.get("issued_on")
        expires_on = cleaned.get("expires_on")
        if issued_on and expires_on and expires_on < issued_on:
            self.add_error("expires_on", _("Expiry date cannot precede issue date."))
        return cleaned


class LoanSeriesSetupForm(forms.ModelForm):
    pawn_loan_prefix = forms.CharField(max_length=24, initial="PL-", label=_("Loan number prefix"), help_text=_("Text before the loan counter, for example PL-A-."))
    release_prefix = forms.CharField(max_length=24, initial="RL-", label=_("Release number prefix"), help_text=_("Text before the separate release counter, for example RL-A-."))
    number_width = forms.IntegerField(min_value=1, max_value=12, initial=5, label=_("Counter digits"), help_text=_("Leading zeros fill this width: 5 displays counter 1 as 00001."))
    maximum_number = forms.IntegerField(min_value=1, initial=10000, label=_("Last counter number"), help_text=_("When the counter reaches this limit, open another series. Numbers are never reused."))

    class Meta:
        model = LoanSeries
        fields = ("name", "code", "is_active")
        labels = {"name": _("Series name"), "code": _("Series code"), "is_active": _("Active series")}
        help_texts = {"code": _("A short code unique within this license, such as A."), "is_active": _("An active series still needs a valid license and available numbers.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            css_class = "form-check-input" if name == "is_active" else "form-control"
            field.widget.attrs.setdefault("class", css_class)
