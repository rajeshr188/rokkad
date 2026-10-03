from django import template

from apps.tenant_apps.party.phone_numbers import PHONE_CONTACT_TYPES, display_phone

register = template.Library()
register.filter("phone_display", display_phone)


@register.filter
def contact_display(contact):
    if contact.contact_type in PHONE_CONTACT_TYPES:
        return display_phone(contact.value)
    return contact.value
