"""One ordinary closing entry point; existing services retain posting authority."""
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from apps.tenant_apps.loans.access import loans_action_required
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services.entry_purpose import default_entry_purpose
from apps.tenant_apps.loans.services.paper_closures import transition_for


@loans_action_required("loan.release")
@require_http_methods(["GET", "POST"])
@never_cache
def close(request, pk):
    loan = get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)
    purpose = (request.POST if request.method == "POST" else request.GET).get("purpose")
    if purpose is None and request.method == "GET":
        review = loan.transaction_reviews.order_by("-pk").first()
        commitment = transition_for(request.loans_workspace)
        if (review and review.future_capture == "ROKKAD_ONLY") or (commitment and (commitment.retired or (
                commitment.system_first_date and commitment.system_first_date <= timezone.localdate()))):
            purpose = "CURRENT"
        else:
            purpose = "PAPER" if default_entry_purpose(workspace=request.loans_workspace,
                series_id=loan.series_id) == "PAPER" else "CURRENT"
    if purpose not in ("CURRENT", "PAPER"):
        return HttpResponseBadRequest("Choose current collection/return or recording a completed settlement.")
    if purpose == "PAPER":
        from .recorded_servicing import closure
        return closure(request, pk)
    from .pawn_release_actions import pawn_loan_release_full
    return pawn_loan_release_full(request, pk)
