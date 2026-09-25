from django.core import signing
from django.http import Http404, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.widgets import LoanBorrowerAutocompleteWidget


@loans_workspace_required
@never_cache
@require_GET
def loan_borrower_autocomplete(request):
    widget = LoanBorrowerAutocompleteWidget(data_url=request.path)
    try:
        url = signing.loads(request.GET.get("field_id", ""), salt=widget.token_salt,
                            max_age=widget.token_max_age)
    except signing.BadSignature as exc:
        raise Http404("Invalid or expired borrower search token.") from exc
    if url != request.path:
        raise Http404("Borrower search token belongs to another URL.")
    term = request.GET.get("term", "").strip()[:255]
    try:
        page = int(request.GET.get("page", "1"))
        if not 1 <= page <= 10000:
            raise ValueError
    except ValueError as exc:
        raise Http404("Invalid search page.") from exc
    if len(term) < 2:
        return JsonResponse({"results": [], "more": False})
    queryset = widget.get_queryset().filter(workspace=request.loans_workspace)
    queryset = widget.filter_queryset(request, term, queryset)
    start = (page - 1) * widget.max_results
    # Fetch one extra match instead of COUNTing every matching customer.
    matches = list(queryset[start:start + widget.max_results + 1])
    return JsonResponse({"results": [widget.result_from_instance(party, request)
        for party in matches[:widget.max_results]], "more": len(matches) > widget.max_results})
