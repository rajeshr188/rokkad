from django import forms
from django.utils import timezone

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Div, HTML, Layout, Row, Submit

from apps.tenancy.context import current_workspace_id

from .models import Rate, RateSource


class RateForm(forms.ModelForm):
    effective_at = forms.DateTimeField(required=False, initial=timezone.now,
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
        help_text="When this price applied, in local time. Leave blank to use now for a new quote.")

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
        self.fields["rate_source"].empty_label = "Select a rate source"
        self.fields["buying_rate"].label = "Buying price per gram"
        self.fields["selling_rate"].label = "Selling price per gram"
        self.fields["purity"].help_text = "Loans uses INR Pure metal buying prices for gold and silver. Enter the item's actual purity on the loan."
        self.fields["reason"].required = bool(self.instance.pk)
        self.fields["reason"].help_text = "Required for corrections. The previous quote remains in history."
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            HTML(
                '<div class="border rounded bg-light p-3 mb-3">'
                '<div class="fw-semibold">Metal rate details</div>'
                '<div class="small text-muted">Prices per gram, excluding tax and making charges. Convert prices per 10 grams or kilogram before entry. Source tax settings do not convert amounts.</div>'
                "</div>"
            ),
            Row(
                Column("rate_source", css_class="col-md-6"),
                Column("currency", css_class="col-md-3"),
                Column("purity", css_class="col-md-3"),
            ),
            Row(
                Column("metal", css_class="col-md-4"),
                Column("buying_rate", css_class="col-md-4"),
                Column("selling_rate", css_class="col-md-4"),
            ),
            "effective_at",
            "reason",
            Div(
                Submit("submit", "Save Rate", css_class="btn btn-primary"),
                HTML(
                    '<a class="btn btn-outline-secondary ms-2" href="{% url \'workspace_rates:rate_list\' request.workspace.slug %}">Cancel</a>'
                ),
                HTML(
                    '<a class="btn btn-link ms-2" href="{% url \'workspace_rates:ratesource_create\' request.workspace.slug %}">Add rate source</a>'
                ),
                css_class="d-flex flex-wrap align-items-center gap-1 mt-3",
            ),
        )

    def clean_effective_at(self):
        return self.cleaned_data.get("effective_at") or (self.instance.effective_at if self.instance.pk else timezone.now())


class RateWithdrawalForm(forms.Form):
    reason = forms.CharField(max_length=500, label="Reason for withdrawal", widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}))


class RateSourceForm(forms.ModelForm):
    class Meta:
        model = RateSource
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"placeholder": "Local market, jeweller, exchange, etc."})
        self.fields["location"].widget.attrs.update({"placeholder": "City or branch"})
        self.fields["tax_included"].help_text = "Describes the source's published prices only. Rate entry requires tax-exclusive prices; no automatic tax conversion is performed."
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            HTML(
                '<div class="border rounded bg-light p-3 mb-3">'
                '<div class="fw-semibold">Rate source</div>'
                '<div class="small text-muted">Create at least one source before adding metal rates.</div>'
                "</div>"
            ),
            Row(
                Column("name", css_class="col-md-6"),
                Column("location", css_class="col-md-6"),
            ),
            "tax_included",
            Div(
                Submit("submit", "Save Source", css_class="btn btn-primary"),
                HTML(
                    '<a class="btn btn-outline-secondary ms-2" href="{% url \'workspace_rates:ratesource_list\' request.workspace.slug %}">Cancel</a>'
                ),
                css_class="d-flex flex-wrap align-items-center gap-1 mt-3",
            ),
        )
