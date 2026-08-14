from django import template

register = template.Library()


@register.filter
def get_item_field(item, name):
    value = getattr(item, name, "")
    return "" if value is None else value
