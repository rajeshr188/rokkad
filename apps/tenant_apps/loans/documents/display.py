"""Presentation-only date formatting; source payloads keep ISO values."""
from datetime import date, datetime
from decimal import Decimal


def display_money(value, *, grouping=False):
    amount = Decimal(str(value or "0"))
    text = format(amount, ",.2f" if grouping else ".2f")
    return text[:-3] if text.endswith(".00") else text


def display_date(value):
    if isinstance(value, datetime):
        from django.utils import timezone
        if timezone.is_aware(value):
            value = timezone.localtime(value)
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    text = str(value)
    if len(text) == 10 and text[4] == "-" and text[7] == "-":
        try:
            return date.fromisoformat(text).strftime("%d/%m/%Y")
        except ValueError:
            pass
    return text
