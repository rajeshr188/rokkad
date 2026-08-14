"""Ordinary Django adapters for PawnLoan auction actions."""

import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.forms import (
    PawnAuctionCompletionForm, PawnAuctionInitiateForm, PawnReversalForm,
    PawnTransitionReasonForm,
)
from apps.tenant_apps.loans.models import PawnLoanAuction
from apps.tenant_apps.loans.services import (
    PawnAuctionError, cancel_pawn_loan_auction, complete_pawn_loan_auction,
    initiate_pawn_loan_auction, reverse_pawn_loan_auction,
    start_pawn_loan_auction,
)


def _pawn_auction_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoanAuction.objects.select_related("loan", "loan__workspace", "accounting_event__outbox").prefetch_related("items__collateral_item"),
        pk=pk, workspace=request.loans_workspace,
    )


def _pawn_loan_for_workspace(request, pk):
    from apps.tenant_apps.loans.models import PawnLoan
    return get_object_or_404(PawnLoan, pk=pk, workspace=request.loans_workspace)


def _render_action(request, loan, form, title, description, extra_context=None):
    context={"loan": loan, "form": form, "action_label": title, "description": description}
    context.update(extra_context or {})
    return render(request, "loans/pawn/action_form.html", context)

@loans_setup_required
def pawn_loan_auction_initiate(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    form = PawnAuctionInitiateForm(
        request.POST or None,
        initial={"request_key": uuid.uuid4().hex},
    )
    if request.method == "POST" and form.is_valid():
        try:
            auction = initiate_pawn_loan_auction(
                loan.pk,
                scheduled_date=form.cleaned_data["scheduled_date"],
                channel=form.cleaned_data["channel"],
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} initiated and notice queued.")
            return redirect("loans:pawn_loan_detail", pk=loan.pk)
    return _render_action(
        request,
        loan,
        form,
        "Initiate auction recovery",
        "Administrator-only. The loan must be overdue and all collateral must remain in the vault.",
    )


@loans_setup_required
@require_POST
def pawn_loan_auction_start(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    try:
        start_pawn_loan_auction(auction.pk, actor=request.user)
    except (PawnAuctionError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Auction {auction.auction_number} started.")
    return redirect("loans:pawn_loan_detail", pk=auction.loan_id)


@loans_setup_required
def pawn_loan_auction_cancel(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnTransitionReasonForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            cancel_pawn_loan_auction(
                auction.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} cancelled.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Cancel auction",
        "An initiated or in-progress auction can be cancelled. A reason is required.",
        {"auction": auction},
    )


@loans_setup_required
def pawn_loan_auction_complete(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnAuctionCompletionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            complete_pawn_loan_auction(
                auction.pk,
                recovery_amount=form.cleaned_data["recovery_amount"],
                buyer_name=form.cleaned_data["buyer_name"],
                buyer_reference=form.cleaned_data["buyer_reference"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} completed and recovery queued through DEA.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Complete auction recovery",
        "Recovery must exactly clear the canonical debt. Shortfall and surplus workflows fail closed.",
        {"auction": auction},
    )


@loans_setup_required
def pawn_loan_auction_reverse(request, auction_pk):
    auction = _pawn_auction_for_workspace(request, auction_pk)
    form = PawnReversalForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            reverse_pawn_loan_auction(
                auction.pk,
                reason=form.cleaned_data["reason"],
                actor=request.user,
            )
        except (PawnAuctionError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"Auction {auction.auction_number} reversed.")
            return redirect("loans:pawn_loan_detail", pk=auction.loan_id)
    return _render_action(
        request,
        auction.loan,
        form,
        "Reverse auction recovery",
        "Administrator-only. Accounting and custody are restored through compensating evidence.",
        {"auction": auction},
    )

