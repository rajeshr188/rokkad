from decimal import Decimal, InvalidOperation
from django import template

register = template.Library()


@register.filter
def indian_money(value):
    """Display rupees using lakh/crore grouping, preserving any actual paise."""
    if value is None or value == "":
        return ""
    from apps.tenant_apps.loans.documents.display import display_money
    try:
        return display_money(value, grouping=True)
    except (InvalidOperation, ValueError, TypeError):
        return value


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
