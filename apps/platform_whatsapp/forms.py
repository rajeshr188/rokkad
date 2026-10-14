from django import forms
from .phones import normalize_phone


class EnrollmentForm(forms.Form):
    phone = forms.CharField(max_length=64, label="Your WhatsApp number",
        help_text="India is the default. Include + and country code for another country.",
        widget=forms.TextInput(attrs={"class": "form-control", "inputmode": "tel", "autocomplete": "tel"}))
    def clean_phone(self):
        return normalize_phone(self.cleaned_data["phone"])


class PreferenceForm(forms.Form):
    workspace_slug = forms.SlugField(max_length=63, widget=forms.HiddenInput)
    contact_revision = forms.IntegerField(min_value=1, widget=forms.HiddenInput)
    setup = forms.BooleanField(required=False, label="Requested setup assistance")
    subscription = forms.BooleanField(required=False, label="Subscription confirmations and trial updates")
    service = forms.BooleanField(required=False, label="Important Rokkad service announcements")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for key in ("setup", "subscription", "service"):
            self.fields[key].widget.attrs["class"] = "form-check-input"


class PreviewForm(forms.Form):
    workspace_slug = forms.SlugField(max_length=63)
    category = forms.ChoiceField(choices=[("setup", "Setup"), ("subscription", "Subscription"), ("service", "Service")])


class SetupReviewForm(forms.Form):
    workspace_slug = forms.SlugField(max_length=63)


class SetupConfirmationForm(forms.Form):
    token = forms.CharField(max_length=4096)


class DeliveryPreviewForm(forms.Form):
    workspace_slug = forms.SlugField(max_length=63)
    delivery_id = forms.IntegerField(min_value=1)
