import re
from django.core.exceptions import ValidationError
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers import NumberParseException


def normalize_phone(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9+().\s-]{1,64}", value):
        raise ValidationError("Enter a valid phone number without extensions or notes.")
    try:
        number = PhoneNumber.from_string(value, region="IN")
    except NumberParseException as exc:
        raise ValidationError("Enter a valid phone number.") from exc
    if not number.is_valid() or number.extension:
        raise ValidationError("Enter a valid phone number without extensions or notes.")
    return number.as_e164
