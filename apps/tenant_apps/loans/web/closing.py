"""Closing selection is independent of loan origin; services retain posting authority."""

from django.http import HttpResponseBadRequest, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from apps.tenant_apps.loans.access import loans_action_required
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services.paper_closures import MAX_PAPER_LOANS
from apps.tenant_apps.loans.services.release_batches import MAX_BATCH_LOANS
from .counter_navigation import counter_return


def legacy_entry(request, *, purpose):
    """Old bookmarked entry URLs select a mode on the common screen."""
    query = request.GET.copy()
    query["purpose"] = purpose
    url = reverse(
        "workspace_loans:loan_closing_create",
        kwargs={"workspace_slug": request.loans_workspace.slug},
    )
    return redirect(f"{url}?{query.urlencode()}")


@loans_action_required("loan.release")
@require_http_methods(["GET", "POST"])
@never_cache
def create(request, *, loan_ids=None):
    data = request.POST if request.method == "POST" else request.GET
    purpose = data.get("purpose", "")
    if purpose not in ("", "CURRENT", "PAPER") or (
        request.method == "POST" and not purpose
    ):
        return HttpResponseBadRequest("Choose how the settlement is being recorded.")
    raw_ids = data.getlist("loans") if loan_ids is None else loan_ids
    limit = MAX_BATCH_LOANS if purpose == "CURRENT" else MAX_PAPER_LOANS
    try:
        ids = [int(pk) for pk in raw_ids]
        if len(ids) > limit or len(set(ids)) != len(ids) or any(pk <= 0 for pk in ids):
            raise ValueError
    except TypeError, ValueError:
        return HttpResponseBadRequest(f"Choose up to {limit} different loans.")
    loans = list(
        PawnLoan.objects.filter(workspace=request.loans_workspace, pk__in=ids)
        .select_related("borrower")
        .order_by("loan_number", "pk")
    )
    if len(loans) != len(ids):
        raise Http404("Selected loans were not found in this workspace.")
    if (
        request.method == "POST"
        and purpose == "CURRENT"
        and (len(ids) > 1 or data.get("quote_token"))
    ):
        from apps.tenant_apps.loans.services.release_batches import decode_quote

        try:
            evidence = decode_quote(
                data.get("quote_token", ""), workspace=request.loans_workspace
            )
            if sorted(ids) != sorted(row["loan_id"] for row in evidence["rows"]):
                raise ValueError(
                    "The selection changed. Review the selected loans again."
                )
        except ValueError as exc:
            return HttpResponseBadRequest(str(exc))
    context = {
        "is_unified_closing": True,
        "closing_purpose": purpose,
        "closure_purpose": purpose,
        "closing_selected_loans": loans,
        "closing_action_url": reverse(
            "workspace_loans:loan_closing_create",
            kwargs={"workspace_slug": request.loans_workspace.slug},
        ),
        "closing_max_loans": limit,
        "closing_return_to": counter_return(request),
    }
    if not purpose or not ids:
        if request.method == "POST":
            return HttpResponseBadRequest("Select at least one loan.")
        return render(request, "loans/closing/start.html", context)
    if purpose == "PAPER":
        from .paper_closures import create as completed

        return completed(request, closing_context=context)
    if len(ids) == 1:
        # Retain the ordinary single-loan interest concession and retry contract.
        from .pawn_release_actions import pawn_loan_release_full

        return pawn_loan_release_full(request, ids[0], closing_context=context)
    from .release_batches import create as current

    return current(request, closing_context=context)


@loans_action_required("loan.release")
@require_http_methods(["GET", "POST"])
@never_cache
def close(request, pk):
    get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)
    if request.method == "GET":
        return create(request, loan_ids=[pk])
    # Already-issued single-loan forms keep their original review tokens/retries.
    purpose = request.POST.get("purpose")
    if purpose == "PAPER":
        from .recorded_servicing import closure

        return closure(request, pk)
    if purpose == "CURRENT":
        from .pawn_release_actions import pawn_loan_release_full

        return pawn_loan_release_full(request, pk)
    return HttpResponseBadRequest("Choose current or completed settlement recording.")
