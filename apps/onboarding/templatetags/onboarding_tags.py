from django import template

from apps.onboarding.navigation import setup_navigation, setup_link

register = template.Library()


@register.simple_tag(takes_context=True)
def setup_navigation_context(context):
    return setup_navigation(context["request"])


@register.simple_tag(takes_context=True)
def setup_url(context, url, step=None):
    return setup_link(context["request"], url, step)
