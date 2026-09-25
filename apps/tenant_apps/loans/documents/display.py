"""Presentation-only date formatting; source payloads keep ISO values."""
from datetime import date, datetime


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
