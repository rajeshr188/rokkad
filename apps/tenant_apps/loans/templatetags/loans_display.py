from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def compact_decimal(value):
    if value is None:
        return ""
    try:
        number = Decimal(str(value))
        if not number.is_finite():
            return ""
        text = format(number, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text
    except (InvalidOperation, ValueError):
        return value
