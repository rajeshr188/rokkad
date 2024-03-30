import datetime

from django import forms
from django.apps import apps

# from product.models import PricingTier
from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS
from django_select2 import forms as s2forms
from import_export.formats import base_formats

from .models import (
    Address,
    Contact,
    Customer,
    CustomerRelationship,
    Proof,
    RelationType,
)


class ExportForm(forms.Form):
    model_name = forms.ChoiceField(
        choices=[
            (model.__name__, model.__name__)
            for app in settings.TENANT_APPS
            for model in apps.get_app_config(app.split(".")[-1]).models.values()
        ]
    )
    export_format = forms.ChoiceField(
        choices=[
            (fmt().get_title(), fmt().get_title())
            for fmt in [
                base_formats.CSV,
                base_formats.JSON,
                base_formats.XLS,
                base_formats.HTML,
            ]
        ]
    )


class ImportForm(forms.Form):
    model_name = forms.ChoiceField(
        choices=[
            (model.__name__, model.__name__)
            for app in settings.TENANT_APPS
            for model in apps.get_app_config(app.split(".")[-1]).models.values()
        ]
    )
    import_file = forms.FileField()


class CustomerWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        "name__icontains",
        "relatedas__icontains",
        "relatedto__icontains",
        "contactno__phone_number__icontains",
    ]


from slick_reporting.forms import BaseReportForm


class CustomerReportForm(BaseReportForm, forms.ModelForm):
    start_date = forms.DateField(
        required=False,
        label="Start Date",
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    end_date = forms.DateField(
        required=False, label="End Date", widget=forms.DateInput(attrs={"type": "date"})
    )

    class Meta:
        model = Customer
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # default_pricing_tier = PricingTier.objects.get(name="Default")
        # self.fields["pricing_tier"].initial = default_pricing_tier
        self.fields["start_date"].initial = datetime.date.today()
        self.fields["end_date"].initial = datetime.date.today()

    def get_filters(self):
        # return the filters to be used in the report
        # Note: the use of Q filters and kwargs filters
        filters = {}
        q_filters = []
        # if self.cleaned_data["secure"] == "secure":
        #     filters["is_secure"] = True
        # elif self.cleaned_data["secure"] == "non-secure":
        #     filters["is_secure"] = False
        # if self.cleaned_data["method"]:
        #     filters["method"] = self.cleaned_data["method"]
        # if self.cleaned_data["response"]:
        #     filters["response"] = self.cleaned_data["response"]
        # if self.cleaned_data["other_people_only"]:
        #     q_filters.append(~Q(user=self.request.user))

        return q_filters, filters

    def get_start_date(self):
        return self.cleaned_data["start_date"]

    def get_end_date(self):
        return self.cleaned_data["end_date"]


class CustomerForm(forms.ModelForm):
    # pricing_tier = forms.ModelChoiceField(queryset=PricingTier.objects.all())
    name = forms.CharField(
        widget=forms.TextInput(attrs={"autofocus": True}),
    )

    class Meta:
        model = Customer
        fields = [
            "customer_type",
            "name",
            "pic",
            "relatedas",
            "relatedto",
            # "pricing_tier",
        ]
        error_messages = {
            NON_FIELD_ERRORS: {
                "unique_together": "%(model_name)s's %(field_labels)s are not unique.",
            }
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # default_pricing_tier = PricingTier.objects.get(name="Default")
        # self.fields["pricing_tier"].initial = default_pricing_tier


class AddressForm(forms.ModelForm):
    class Meta:
        model = Address
        fields = [
            "doorno",
            "street",
            "area",
            "zipcode",
        ]
        widgets = {
            "street": forms.Textarea(attrs={"rows": 3}),
            "doorno": forms.TextInput(attrs={"autofocus": True}),
        }
        exclude = [
            "created_at",
            "last_updated",
        ]

    # def __init__(self, *args, **kwargs):
    #     super(AddressForm, self).__init__(*args, **kwargs)
    #     self.fields["Customer"].queryset = Customer.objects.all()


class ContactForm(forms.ModelForm):
    # phone_number = PhoneNumberField(region="IN")

    class Meta:
        model = Contact
        fields = [
            "contact_type",
            "phone_number",
            # "customer",
        ]
        widgets = {
            "phone_number": forms.TextInput(attrs={"autofocus": True}),
        }


class ProofForm(forms.ModelForm):
    class Meta:
        model = Proof
        fields = [
            "proof_type",
            "proof_no",
            "doc",
            "Customer",
        ]

    def __init__(self, *args, **kwargs):
        super(ProofForm, self).__init__(*args, **kwargs)
        self.fields["Customer"].queryset = Customer.objects.all()


class CustomerMergeForm(forms.Form):
    original = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(
            select2_options={
                "width": "100%",
            }
        ),
    )
    duplicate = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(
            select2_options={
                "width": "100%",
            }
        ),
    )


class CustomerRelationshipForm(forms.Form):
    relationship = forms.ChoiceField(choices=RelationType.choices)
    related_customer = forms.ModelChoiceField(
        queryset=Customer.objects.all(),
        widget=CustomerWidget(
            select2_options={
                "width": "100%",
            }
        ),
    )

    class Meta:
        model = CustomerRelationship
        fields = [
            "relationship",
            "related_customer",
        ]

    def __init__(self, *args, customer_id=None, **kwargs):
        super().__init__(*args, **kwargs)
        # If from_customer_id is provided, exclude it from the queryset
        if customer_id:
            self.fields["related_customer"].queryset = Customer.objects.exclude(
                pk=customer_id.id
            )
