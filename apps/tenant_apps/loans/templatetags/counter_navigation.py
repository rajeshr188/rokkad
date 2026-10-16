from django import template
from django.urls import reverse

from apps.tenant_apps.loans.web.counter_navigation import counter_return, with_counter_return

register = template.Library()


@register.simple_tag(takes_context=True)
def counter_url(context, view_name, *args, from_page=False, **kwargs):
    return with_counter_return(reverse(view_name, args=args, kwargs=kwargs or None), context['request'], from_page=from_page)


@register.simple_tag(takes_context=True)
def counter_link(context, url):
    return with_counter_return(url, context['request'])


@register.simple_tag(takes_context=True)
def counter_back(context):
    request = context['request']
    return counter_return(request) or reverse('workspace_loans:pawn_loan_list', args=[request.workspace.slug])
