"""
Improved base forms for the contact app.
This demonstrates best practices for form organization.
Add this as: apps/tenant_apps/contact/base_forms.py
"""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Row, Column, Submit, Button, HTML, Field
from django import forms
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField as BasePhoneNumberField

from .utils import ValidationHelpers


class BaseHTMXForm(forms.ModelForm):
    """
    Base form class for HTMX integration.
    Handles common HTMX setup and CSS classes.

    Usage:
        class CustomerForm(BaseHTMXForm):
            class Meta:
                model = Customer
                fields = ['name', 'email']
    """

    def __init__(self, *args, **kwargs):
        # Extract HTMX parameters
        self.htmx_post_url = kwargs.pop("htmx_post_url", None)
        self.htmx_target = kwargs.pop("htmx_target", "#modal-content")
        self.htmx_swap = kwargs.pop("htmx_swap", "innerHTML")
        self.show_cancel = kwargs.pop("show_cancel", True)
        self.cancel_action = kwargs.pop(
            "cancel_action", "dismiss"
        )  # 'dismiss', 'remove', 'redirect'

        super().__init__(*args, **kwargs)

        # Apply Bootstrap classes to all fields
        self._apply_bootstrap_classes()

        # Setup FormHelper
        self._setup_crispy_helper()

    def _apply_bootstrap_classes(self):
        """Apply Bootstrap 5 classes to all form fields"""
        for field_name, field in self.fields.items():
            if isinstance(field.widget, (forms.Select, forms.RadioSelect)):
                field.widget.attrs["class"] = "form-select"
            elif isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
            elif isinstance(field.widget, forms.Textarea):
                field.widget.attrs["class"] = "form-control"
                if "rows" not in field.widget.attrs:
                    field.widget.attrs["rows"] = 3
            else:
                field.widget.attrs["class"] = "form-control"

    def _setup_crispy_helper(self):
        """Setup Crispy Forms helper with HTMX attributes"""
        self.helper = FormHelper()
        self.helper.form_method = "post"
        self.helper.form_class = "form-horizontal"

        # Add HTMX attributes if provided
        if self.htmx_post_url:
            self.helper.attrs = {
                "hx-post": self.htmx_post_url,
                "hx-target": self.htmx_target,
                "hx-swap": self.htmx_swap,
                "novalidate": "novalidate",  # Let server handle validation with HTMX
            }

        # Add buttons
        self._add_buttons()

    def _add_buttons(self):
        """Add submit and cancel buttons"""
        # Submit button
        self.helper.add_input(
            Submit(
                "submit",
                _("Save"),
                css_class="btn btn-primary btn-lg",
                onclick="this.disabled=true",
            )
        )

        # Cancel button
        if self.show_cancel:
            if self.cancel_action == "dismiss":
                cancel_button = Button(
                    "cancel",
                    _("Cancel"),
                    css_class="btn btn-secondary btn-lg",
                    **{"data-bs-dismiss": "modal"}
                )
            elif self.cancel_action == "remove":
                cancel_button = Button(
                    "cancel",
                    _("Cancel"),
                    css_class="btn btn-secondary btn-lg",
                    **{"hx-on": 'click: this.closest("form").remove()'}
                )
            else:
                cancel_button = Button(
                    "cancel",
                    _("Cancel"),
                    css_class="btn btn-secondary btn-lg",
                )

            self.helper.add_input(cancel_button)


class IndianPhoneNumberField(BasePhoneNumberField):
    """
    Custom phone number field specifically tuned for Indian numbers.
    Provides better validation and error messages.
    """

    default_error_messages = {
        "invalid": _("Enter a valid Indian phone number (10 digits starting with 6-9)"),
        "incomplete": _("Phone number is incomplete"),
        "invalid_idd_code": _("International dialing code for India is +91"),
    }

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("region", "IN")
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        """Convert and validate phone number"""
        if not value:
            return None

        # Try to validate using parent class first
        try:
            return super().to_python(value)
        except forms.ValidationError:
            # If parent validation fails, try to provide helpful error
            is_valid, formatted, error = ValidationHelpers.validate_phone(value)
            if is_valid:
                return formatted
            raise forms.ValidationError(error)


class CustomerFormBase(BaseHTMXForm):
    """Base customer form with common fields"""

    class Meta:
        fields = [
            "customer_type",
            "first_name",
            "last_name",
            "gender",
            "dob",
            "email",
            "active",
        ]
        widgets = {
            "dob": forms.DateInput(attrs={"type": "date"}),
            "email": forms.EmailInput(attrs={"type": "email"}),
        }


class AddressFormBase(BaseHTMXForm):
    """Base address form with validation"""

    zip_code = forms.CharField(
        max_length=10,
        required=True,
        validators=[ValidationHelpers.PINCODE_REGEX],
        help_text=_("Enter 6-digit Indian pincode"),
    )

    class Meta:
        fields = [
            "door_number",
            "street",
            "area",
            "city",
            "state",
            "country",
            "zip_code",
            "is_default",
        ]
        widgets = {
            "street": forms.Textarea(attrs={"rows": 3}),
        }


class ContactFormBase(BaseHTMXForm):
    """Base contact form with Indian phone validation"""

    phone_number = IndianPhoneNumberField(
        help_text=_("Example: +919876543210 or 9876543210"),
        strip=True,
    )

    class Meta:
        fields = ["contact_type", "phone_number", "is_default", "is_verified"]


class ProofFormBase(BaseHTMXForm):
    """Base proof form with document validation"""

    proof_number = forms.CharField(
        max_length=30,
        label=_("Proof Number"),
        help_text=_("Aadhar/PAN/DL number"),
    )

    class Meta:
        fields = ["proof_type", "proof_number", "document", "is_verified"]
        widgets = {
            "document": forms.FileInput(attrs={"accept": ".pdf,.jpg,.jpeg,.png"}),
        }

    def clean(self):
        super().clean()
        cleaned_data = super().clean()

        proof_type = cleaned_data.get("proof_type")
        proof_number = cleaned_data.get("proof_number")

        if proof_type and proof_number:
            is_valid, error = ValidationHelpers.validate_proof_number(
                proof_type, proof_number
            )
            if not is_valid:
                self.add_error("proof_number", error)


class RelationshipFormBase(BaseHTMXForm):
    """Base relationship form"""

    class Meta:
        fields = ["relationship", "related_customer"]


# Form layouts can be organized like this:


class CustomerFormLayout:
    """Define layout for customer forms"""

    @staticmethod
    def get_layout():
        return Layout(
            HTML('<h6 class="text-muted mb-3">{% trans "Personal Information" %}</h6>'),
            Row(
                Column("first_name", css_class="col-md-6"),
                Column("last_name", css_class="col-md-6"),
            ),
            Row(
                Column("customer_type", css_class="col-md-6"),
                Column("gender", css_class="col-md-6"),
            ),
            Row(
                Column("dob", css_class="col-md-6"),
                Column("email", css_class="col-md-6"),
            ),
            "active",
        )


class AddressFormLayout:
    """Define layout for address forms"""

    @staticmethod
    def get_layout():
        return Layout(
            HTML('<h6 class="text-muted mb-3">{% trans "Address Details" %}</h6>'),
            "door_number",
            "street",
            Row(
                Column("area", css_class="col-md-6"),
                Column("city", css_class="col-md-6"),
            ),
            Row(
                Column("state", css_class="col-md-6"),
                Column("country", css_class="col-md-6"),
            ),
            "zip_code",
            Row(
                Column("is_default", css_class="col-md-6"),
                Column("is_verified", css_class="col-md-6"),
            ),
        )


# Example: How to use these forms

"""
# In your views.py
from .base_forms import CustomerFormBase

class CustomerCreateView(CreateView):
    model = Customer
    form_class = CustomerFormBase
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['htmx_post_url'] = reverse('contact_customer_create')
        kwargs['htmx_target'] = '#modal-content'
        return kwargs

# In your template
{% load crispy_forms_field %}
<form method="post" {% include 'includes/form_attrs.html' %}>
    {% csrf_token %}
    {% crispy form %}
</form>
"""
