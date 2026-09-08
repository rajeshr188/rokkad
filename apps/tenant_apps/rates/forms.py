from django import forms

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Div, HTML, Layout, Row, Submit

from apps.tenancy.context import current_workspace_id

from .models import Rate, RateSource


class RateForm(forms.ModelForm):
    class Meta:
        model = Rate
        fields = "__all__"
        widgets = {
            "buying_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
            "selling_rate": forms.NumberInput(attrs={"step": "0.01", "min": "0"}),
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
        self.fields["buying_rate"].help_text = "Buying rate for the selected metal and purity."
        self.fields["selling_rate"].help_text = "Selling rate for the selected metal and purity."
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            HTML(
                '<div class="border rounded bg-light p-3 mb-3">'
                '<div class="fw-semibold">Metal rate details</div>'
                '<div class="small text-muted">Workspace reference rates for supported metals.</div>'
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


class RateSourceForm(forms.ModelForm):
    class Meta:
        model = RateSource
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["name"].widget.attrs.update({"placeholder": "Local market, jeweller, exchange, etc."})
        self.fields["location"].widget.attrs.update({"placeholder": "City or branch"})
        self.fields["tax_included"].help_text = "Enable when quoted rates already include tax."
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
