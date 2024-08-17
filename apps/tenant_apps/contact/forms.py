import datetime

from django import forms
from django.apps import apps
# from product.models import PricingTier
from django.conf import settings
from django.core.exceptions import NON_FIELD_ERRORS
from django_select2 import forms as s2forms
from import_export.formats import base_formats
from slick_reporting.forms import BaseReportForm
from crispy_forms.helper import FormHelper 
from crispy_forms.layout import Submit, Button,HTML
from .models import (Address, Contact, Customer, CustomerPic,
                     CustomerRelationship, Proof, RelationType)
from django.urls import reverse

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
        # fields = "__all__"
        exclude = [
            "gender",
            "pic",
            "relatedas",
            "relatedto",
            "customer_type",
            "religion",
        ]

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
        # if self.cleaned_data["customer_type"] == "S":
        #     filters["customer_type"] = 'S'
        # elif self.cleaned_data["gender"] == "M":
        #     filters["gender"] = 'M'
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
        customer_id = kwargs.pop('customer_id',None)
        super().__init__(*args, **kwargs)
        # default_pricing_tier = PricingTier.objects.get(name="Default")
        # self.fields["pricing_tier"].initial = default_pricing_tier
        self.helper = FormHelper()
        if customer_id:
            self.helper.attrs = {
                'hx-post': reverse('contact_customer_update', args=[customer_id]),
            }
            cancel_url = reverse('contact_customer_detail', args=[customer_id])
            cancel_button = Button(
                'cancel',
                'Cancel',
                css_class='btn btn-danger',
                **{
                    'hx-get': cancel_url,
                    'hx-target': '#content',
                }
            )

        else:
            self.helper.attrs = {
                'hx-post': reverse('contact_customer_create'),
                'hx-target': '#content',
                
            }
            cancel_url = reverse('contact_customer_list')
            cancel_button = Button(
                'cancel',
                'Cancel',
                css_class='btn btn-danger',
                **{
                    'hx-get': cancel_url,
                    'hx-target': '#content',
                    'hx-vals':'{"use_block":"content"}',
                }
            )

        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-success'))
        self.helper.add_input(cancel_button)


class CustomerPicForm(forms.ModelForm):
    class Meta:
        model = CustomerPic
        fields = ["is_default"]


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

    def __init__(self, *args, **kwargs):
        customer_id = kwargs.pop('customer_id',None)
        address_id = kwargs.pop('address_id',None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        # self.helper.form_method = 'post'
        
        if address_id:
            self.helper.attrs = {
            'hx-post': reverse('customer_address_update', args=[customer_id, address_id]) ,
            'hx-target':"closest li",
            'hx-swap': 'outerHTML',
            }
            cancel_url = reverse('customer_address_detail', args=[address_id])
            cancel_button = Button(
                'cancel',
                'Cancel',
                css_class='btn btn-danger',
                **{
                    'hx-get': cancel_url,
                    'hx-target': 'closest li',
                    'hx-swap': 'outerHTML'
                }
            )
        else:
            self.helper.attrs = {
            'hx-post': reverse('customer_address_create', args=[customer_id]),
            'hx-target': 'this',
            'hx-swap': 'outerHTML',
            }
            cancel_button = Button(
                'cancel', 'Cancel', css_class='btn btn-danger', onclick="this.closest('form').remove()"
            )
            # cancel_button = Button(
            #     'cancel', 'Cancel', css_class='btn btn-danger', 
            #     **{
            #         '_':'on click remove closest form',
            #     }
            # )
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-success'))
        self.helper.add_input(cancel_button)
    

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

    def __init__(self, *args, **kwargs):
        customer_id = kwargs.pop('customer_id',None)
        contact_id = kwargs.pop('contact_id',None)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        if contact_id:
            self.helper.attrs = {
            'hx-post': reverse('contact_update', args=[customer_id, contact_id]),
            'hx-target':"closest li",
            'hx-swap': 'outerHTML',
            }
            cancel_url = reverse('customer_contact_detail', args=[contact_id])
            cancel_button = Button(
                'cancel',
                'Cancel',
                css_class='btn btn-danger',
                **{
                    'hx-get': cancel_url,
                    'hx-target': 'closest li',
                    'hx-swap': 'outerHTML'
                }
            )
        else:
            self.helper.attrs = {
            'hx-post': reverse('contact_create', args=[customer_id]),
            'hx-target': 'this',
            'hx-swap': 'outerHTML',
            }
            cancel_button = Button(
                'cancel', 'Cancel', css_class='btn btn-danger', onclick="this.closest('form').remove()"
            )
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-success'))
        self.helper.add_input(cancel_button)


class ProofForm(forms.ModelForm):
    class Meta:
        model = Proof
        fields = [
            "proof_type",
            "proof_no",
            "doc",
            "customer",
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
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.attrs = {
            'hx-post': reverse('contact_customer_merge'),
            'hx-target': '#form',
        }
        self.helper.add_input(Submit('submit', 'Merge', css_class='btn btn-success'))
        self.helper.add_input(Button('cancel', 'Cancel', css_class='btn btn-danger', onclick="this.closest('form').remove()"))
        

class CustomerRelationshipForm(forms.ModelForm):
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
        fields = ["relationship","related_customer",]

    def __init__(self, *args, **kwargs):
        customer_id = kwargs.pop('customer_id', None)
        instance = kwargs.pop('instance', None)
        super().__init__(*args, **kwargs)

        # Debugging: Print customer_id and instance
        print(f"customer_id: {customer_id}")
        print(f"instance: {instance}")

        # If from_customer_id is provided, exclude it from the queryset
        if customer_id:
            self.fields["related_customer"].queryset = Customer.objects.exclude(
                pk=customer_id
            )
        self.helper = FormHelper()
        if instance:
            self.helper.attrs = {
            'hx-post': reverse('update_relationship', args=[customer_id, instance.id]),
            'hx-target': 'this',
            
        }
        else:
            self.helper.attrs = {
            'hx-post': reverse('create_relationship', args=[customer_id]),
            'hx-target': '#relations',
            'hx-swap': 'afterbegin',
        }
        self.helper.add_input(Submit('submit', 'Save', css_class='btn btn-success'))
        self.helper.add_input(Button('cancel', 'Cancel', css_class='btn btn-danger', onclick="this.closest('form').remove()"))
