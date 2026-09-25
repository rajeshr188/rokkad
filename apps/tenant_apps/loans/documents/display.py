"""Presentation-only formatting; financial evidence keeps unformatted values."""
from datetime import date, datetime
from decimal import Decimal


def display_money(value, *, grouping=False):
    amount = Decimal(str(value or "0"))
    if not amount.is_finite():
        raise ValueError("Money must be finite")
    text = format(amount, ".2f")
    if grouping:
        integer, fraction = text.split(".")
        sign = "-" if integer.startswith("-") else ""
        integer = integer.lstrip("-")
        groups = [integer[-3:]]
        integer = integer[:-3]
        while integer:
            groups.insert(0, integer[-2:])
            integer = integer[:-2]
        text = sign + ",".join(groups) + "." + fraction
    return text[:-3] if text.endswith(".00") else text


def collateral_description(item):
    description = item["description"]
    return description + (f" (Qty {item['quantity']})" if item.get("quantity") else "")


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
