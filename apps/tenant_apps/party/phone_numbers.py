"""Phone entry and display; stored Party contact values remain E.164 strings."""

import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from phonenumber_field.formfields import PhoneNumberField
from phonenumber_field.phonenumber import PhoneNumber, to_python
from phonenumber_field.widgets import RegionalPhoneNumberWidget


PHONE_CONTACT_TYPES = frozenset(("PHONE", "MOBILE", "WHATSAPP"))
PHONE_INPUT = re.compile(r"[\d\s+().-]+")
PHONE_HELP = _("India is the default. Enter a mobile number or a landline with its area code. For another country, start with + and the country code.")


def display_phone(value):
    """Format valid numbers without hiding or rewriting invalid legacy values."""
    if not value:
        return ""
    if isinstance(value, str) and not PHONE_INPUT.fullmatch(value):
        return value
    try:
        number = to_python(value, region="IN")
    except (TypeError, ValueError):
        return value
    return number.as_international if number and number.is_valid() else value


class PartyPhoneWidget(RegionalPhoneNumberWidget):
    def format_value(self, value):
        return display_phone(value)


class PartyPhoneNumberField(PhoneNumberField):
    """Use library validation while avoiding silent loss of extension text."""

    def __init__(self, **kwargs):
        kwargs.setdefault("region", "IN")
        kwargs.setdefault("help_text", PHONE_HELP)
        kwargs.setdefault("widget", PartyPhoneWidget(region="IN", attrs={
            "class": "form-control", "inputmode": "tel", "autocomplete": "tel",
            "placeholder": "+91 98765 43210",
        }))
        super().__init__(**kwargs)

    def to_python(self, value):
        if isinstance(value, str) and value.strip() and not PHONE_INPUT.fullmatch(value):
            raise ValidationError(_("Enter a valid phone number using digits and a country or area code. Put extensions or notes in the contact label."), code="invalid")
        return super().to_python(value)

    def validate(self, value):
        super().validate(value)
        if isinstance(value, PhoneNumber) and value.extension:
            raise ValidationError(_("Put the extension in the contact label, not the phone number."), code="invalid")
