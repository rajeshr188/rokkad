from django import forms
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.tenancy.context import current_workspace_id

from .models import Rate, RateSource


class RateForm(forms.ModelForm):
    effective_at = forms.DateTimeField(required=False, initial=timezone.now,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
        help_text=_("When this price applied, in local time. Leave blank to use now for a new quote."))

    class Meta:
        model = Rate
        fields = ("rate_source", "metal", "currency", "purity", "buying_rate", "selling_rate", "effective_at", "reason")
        widgets = {
            "buying_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "selling_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        workspace_id = current_workspace_id()
        self.fields["rate_source"].queryset = (
            RateSource.objects.filter(workspace_id=workspace_id)
            if workspace_id is not None
            else RateSource.objects.none()
        )
        self.fields["purity"].help_text = _("Loans uses INR Pure metal buying prices for gold and silver. Enter the item's actual purity on the loan.")
        self.fields["reason"].required = bool(self.instance.pk)
        self.fields["reason"].help_text = _("Required for corrections. The previous quote remains in history.")
        for name in ("buying_rate", "selling_rate"):
            self.fields[name].help_text = _("Currency per gram of the selected purity.")
        labels = {"rate_source": _("Rate source"), "metal": _("Metal"), "currency": _("Currency"),
                  "purity": _("Quote purity"), "buying_rate": _("Buying price per gram"),
                  "selling_rate": _("Selling price per gram"), "effective_at": _("Effective at"), "reason": _("Reason / notes")}
        for name, field in self.fields.items():
            field.label = labels[name]
            field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"
        for name in ("metal", "currency", "purity"):
            self.fields[name].choices = [(value, _(label)) for value, label in self.fields[name].choices]
        self.fields["rate_source"].empty_label = _("Select a rate source")
        self.fields["reason"].widget = forms.Textarea(attrs={"rows": 3, "class": "form-control"})

    def clean_effective_at(self):
        return self.cleaned_data.get("effective_at") or (self.instance.effective_at if self.instance.pk else timezone.now())


class RateWithdrawalForm(forms.Form):
    reason = forms.CharField(max_length=500, label=_("Reason for withdrawal"), widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class RateSourceForm(forms.ModelForm):
    class Meta:
        model = RateSource
        fields = ("name", "location", "tax_included")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"placeholder": _("Local market, jeweller, exchange, etc.")})
        self.fields["location"].widget.attrs.update({"placeholder": _("City or branch")})
        self.fields["tax_included"].help_text = _("Describes the source's published prices only. Rate entry requires tax-exclusive prices; no automatic tax conversion is performed.")
        for name, field in self.fields.items():
            field.label = {"name": _("Source name"), "location": _("Location"), "tax_included": _("Source publishes prices including tax")}[name]
            field.widget.attrs["class"] = "form-check-input" if isinstance(field, forms.BooleanField) else "form-control"


class RateListForm(forms.Form):
    q = forms.CharField(required=False, max_length=100, label=_("Search sources or notes"), widget=forms.TextInput(attrs={"class": "form-control", "type": "search"}))
    metal = forms.ChoiceField(required=False, label=_("Metal"), choices=[("", _("All metals")), *((value, _(label)) for value, label in Rate.Metal.choices)], widget=forms.Select(attrs={"class": "form-select"}))
