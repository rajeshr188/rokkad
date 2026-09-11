"""Ordinary Django adapters for PawnLoan customer notices."""

import uuid

from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.tenant_apps.loans.access import loans_action_required
from apps.tenant_apps.loans.forms import PawnLoanNoticeForm
from apps.tenant_apps.loans.models import PawnLoan, PawnLoanNotice
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.loans.services import (
    PawnLoanNoticeError,
    create_pawn_loan_notice,
    retry_pawn_loan_notice,
)


def _pawn_loan_for_workspace(request, pk):
    return get_object_or_404(
        PawnLoan.objects.select_related("borrower", "license", "series").prefetch_related(
            "collateral_items", "loan_events"
        ),
        pk=pk,
        workspace=request.loans_workspace,
    )


def _safe_balance(loan):
    try:
        return get_pawn_loan_balance(loan.pk, as_of_date=timezone.localdate())
    except (ObjectDoesNotExist, ValidationError, ValueError):
        return None


@loans_action_required("data.edit")
def pawn_loan_notice_create(request, pk):
    loan = _pawn_loan_for_workspace(request, pk)
    requested_kind = request.GET.get("kind", "")
    allowed_kinds = {
        value for value, _label in PawnLoanNoticeForm.base_fields["notice_kind"].choices
    }
    form = PawnLoanNoticeForm(
        request.POST or None,
        initial={
            "request_key": uuid.uuid4().hex,
            "notice_kind": requested_kind if requested_kind in allowed_kinds else "",
        },
    )
    if request.method == "POST" and form.is_valid():
        try:
            notice = create_pawn_loan_notice(
                loan.pk,
                notice_kind=form.cleaned_data["notice_kind"],
                channel=form.cleaned_data["channel"],
                scheduled_for=form.cleaned_data.get("scheduled_for"),
                request_key=form.cleaned_data["request_key"],
                actor=request.user,
            )
        except (PawnLoanNoticeError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, f"{notice.get_notice_kind_display()} queued through Notify.")
            return redirect("workspace_slug_loan_detail", workspace_slug=request.loans_workspace.slug, pk=loan.pk)
    return render(
        request,
        "loans/pawn/action_form.html",
        {
            "loan": loan,
            "form": form,
            "action_label": "Create loan notice",
            "description": "Review and confirm the immutable notice source. Loans owns the intent; Notify owns templates, provider delivery, and attempts.",
            "balance": _safe_balance(loan),
            "notice_preview": True,
            "form_action": reverse("workspace_loans:pawn_loan_notice_create", kwargs={
                "workspace_slug": request.loans_workspace.slug, "pk": loan.pk,
            }),
        },
    )


@loans_action_required("data.edit")
@require_POST
def pawn_loan_notice_retry(request, pk, notice_pk):
    loan = _pawn_loan_for_workspace(request, pk)
    notice = get_object_or_404(
        PawnLoanNotice,
        pk=notice_pk,
        loan=loan,
        workspace=request.loans_workspace,
    )
    try:
        result = retry_pawn_loan_notice(notice.pk, actor=request.user)
    except (PawnLoanNoticeError, ValidationError, ValueError) as exc:
        messages.error(request, str(exc))
    else:
        if result.delivery.status == "SENT":
            messages.success(request, "PawnLoan notice sent.")
        elif result.delivery.status == "FAILED":
            messages.error(request, result.delivery.failure_reason or "Notice delivery failed.")
        else:
            messages.info(request, "PawnLoan notice remains queued.")
    return redirect("workspace_slug_loan_detail", workspace_slug=request.loans_workspace.slug, pk=loan.pk)
