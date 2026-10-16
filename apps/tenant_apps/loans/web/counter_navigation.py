"""Workspace-local navigation context; never an authority or financial input."""
from functools import wraps
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.urls import resolve, reverse, Resolver404

FILTERS = {'q', 'borrower', 'borrower_q', 'state', 'records', 'license', 'series',
           'loan_date_from', 'loan_date_to', 'page', 'queue', 'period', 'start', 'end', 'section', 'amounts'}


def counter_return(request, *, from_page=False):
    workspace = request.workspace
    candidate = request.get_full_path() if from_page else (
        request.GET.get('return_to') or request.POST.get('return_to', ''))
    if not candidate or len(candidate) > 4096 or any(ord(c) < 32 for c in candidate) or '\\' in candidate:
        return ''
    try:
        parts = urlsplit(candidate)
    except ValueError:
        return ''
    allowed = {reverse('workspace_loans:pawn_loan_list', args=[workspace.slug]),
               reverse('workspace_loans:overdue_payments', args=[workspace.slug]),
               reverse('workspace_slug_dashboard', args=[workspace.slug])}
    if parts.scheme or parts.netloc or parts.path not in allowed:
        return ''
    query = urlencode([(k, v) for k, v in parse_qsl(parts.query)
                       if k in FILTERS and (k != 'section' or v == 'full')])
    return parts.path + ('?' + query if query else '')


def with_counter_return(url, request, *, from_page=False):
    origin = counter_return(request, from_page=from_page)
    if not origin:
        return url
    parts = urlsplit(url)
    query = [(k, v) for k, v in parse_qsl(parts.query) if k != 'return_to']
    return urlunsplit(parts._replace(query=urlencode([*query, ('return_to', origin)])))


def preserve_counter_return(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        response = view(request, *args, **kwargs)
        if response.status_code == 302 and counter_return(request):
            destination = urlsplit(response['Location'])
            try:
                match = resolve(destination.path)
            except Resolver404:
                return response
            if (not destination.scheme and not destination.netloc
                    and match.url_name in {'pawn_loan_detail', 'workspace_slug_loan_detail',
                        'pawn_loan_review_disburse', 'pawn_loan_record_completed_payout'}
                    and match.kwargs.get('workspace_slug') == request.workspace.slug):
                response['Location'] = with_counter_return(response['Location'], request)
        return response
    return wrapped
