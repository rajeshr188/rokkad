"""Ordinary Django adapters for PawnLoan collateral release."""

import uuid

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.http import HttpResponseGone
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION, loans_action_required
from apps.tenant_apps.loans.forms import PawnFullReleaseForm
from apps.tenant_apps.loans.models import PawnLoan
from apps.tenant_apps.loans.services import (
    preview_pawn_loan_full_release,
    release_pawn_loan_in_full,
)


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items", "loan_events"
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _full_release_quote(loan):
    try:
        return preview_pawn_loan_full_release(loan.pk)
    except (ObjectDoesNotExist, ValidationError, ValueError) as exc:
        return {"error": str(exc), "minimum_settlement": None}


@loans_action_required("loan.release")
@never_cache
def pawn_loan_release_full(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    quote = _full_release_quote(loan)
    initial = {"request_key": uuid.uuid4().hex}
    minimum_settlement = (
        quote.get("minimum_settlement")
        if isinstance(quote, dict)
        else quote.minimum_settlement
    )
    if minimum_settlement is not None:
        # Event arithmetic can retain trailing scale beyond the form's cents.
        initial["settlement_amount"] = format(minimum_settlement, ".2f")
    form = PawnFullReleaseForm(request.POST if request.method == "POST" else None, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            concession = {}
            if form.cleaned_data.get("interest_concession") or form.cleaned_data.get("concession_reason"):
                concession = {"interest_concession": form.cleaned_data["interest_concession"],
                              "concession_reason": form.cleaned_data["concession_reason"]}
            result = release_pawn_loan_in_full(
                loan.pk,
                settlement_amount=form.cleaned_data["settlement_amount"],
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
                **concession,
            )
        except (ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(
                request,
                f"Release {result.release.release_number} completed: "
                f"{result.release.settlement_amount} collected, "
                f"{result.release.items.count()} collateral item(s) returned, "
                "loan closed.",
            )
            return redirect('workspace_loans:pawn_loan_detail', pk=loan.pk, workspace_slug=request.workspace.slug)
    return render(
        request,
        "loans/pawn/full_release.html",
        {
            "loan": loan,
            "form": form,
            "action_label": _("Full release"),
            "quote": quote,
            "quote_date": timezone.localdate(),
            "can_concede_interest": request.loans_workspace_access.can(LOANS_ADMIN_ACTION),
            "release_available": minimum_settlement is not None and not isinstance(quote, dict) and not quote.blockers,
        },
    )


@loans_action_required("loan.release")
def pawn_loan_release_partial(request, pk):
    _pawn_loan_for_workspace(request, pk)
    return HttpResponseGone(
        "Partial collateral release is no longer supported. "
        "Use full release or release and renew into a newly numbered PawnLoan."
    )
