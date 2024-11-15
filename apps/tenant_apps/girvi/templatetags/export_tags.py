# templatetags/export_tags.py
from django import template
import django_tables2 as django_tables2_tags

register = template.Library()

@register.simple_tag(takes_context=True)
def export_url_with_params(context, format):
    """Generate export URL with current filter parameters"""
    url = django_tables2_tags.export_url(format)
    params = context['request'].GET.urlencode()
    if params:
        return f"{url}?{params}"
    return url