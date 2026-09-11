"""FundingLoan read pages and immutable document delivery."""

import uuid

from django.http import Http404
from django.shortcuts import render
from django.utils import timezone

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.web.funding_forms import (
    FundingCollateralReturnForm,
    FundingCorrectionForm,
    FundingLoanActivationForm,
    FundingLoanCancellationForm,
    FundingLoanClosureForm,
    FundingLoanRepaymentForm,
)
from apps.tenant_apps.loans.models import FundingLoan, FundingLoanEvent, FundingReturn
from apps.tenant_apps.loans.selectors import (
    FundingLoanSelectorError,
    get_funding_loan_detail,
    get_funding_loan_draft_inputs,
    get_funding_loan_integrity_findings,
    get_funding_loan_summaries,
    get_funding_settlement_readiness,
)
from apps.tenant_apps.loans.services import (
    FundingLoanDocumentService,
    PawnLoanDocumentService,
)


@loans_setup_required
def funding_loan_read_console(request):
    return render(
        request,
        "loans/setup/funding/list.html",
        {
            "funding_loans": get_funding_loan_summaries(),
            "findings": get_funding_loan_integrity_findings(),
        },
    )


def _funding_document_loan(request, pk):
    try:
        return FundingLoan.objects.select_related(
            "workspace", "lender", "terms_snapshot", "pledge"
        ).get(pk=pk, workspace=request.loans_workspace)
    except FundingLoan.DoesNotExist as exc:
        raise Http404("FundingLoan was not found in the active workspace.") from exc


@loans_setup_required
def funding_loan_agreement_pdf(request, pk):
    loan = _funding_document_loan(request, pk)
    if not hasattr(loan, "terms_snapshot") or not hasattr(loan, "pledge"):
        raise Http404("Funding agreement is available only after activation.")
    detail = get_funding_loan_detail(pk)
    return PawnLoanDocumentService.build_pdf_response(
        FundingLoanDocumentService.render_agreement(loan, detail)
    )


@loans_setup_required
def funding_loan_repayment_receipt_pdf(request, pk, event_pk):
    loan = _funding_document_loan(request, pk)
    try:
        event = loan.events.get(pk=event_pk, event_kind="REPAYMENT")
    except FundingLoanEvent.DoesNotExist as exc:
        raise Http404("Funding repayment evidence was not found.") from exc
    return PawnLoanDocumentService.build_pdf_response(
        FundingLoanDocumentService.render_repayment_receipt(event)
    )


@loans_setup_required
def funding_loan_return_receipt_pdf(request, pk, return_pk):
    loan = _funding_document_loan(request, pk)
    try:
        funding_return = loan.returns.prefetch_related(
            "items__pledge_item__collateral_item__loan"
        ).get(pk=return_pk)
    except FundingReturn.DoesNotExist as exc:
        raise Http404("Funding return evidence was not found.") from exc
    return PawnLoanDocumentService.build_pdf_response(
        FundingLoanDocumentService.render_return_receipt(funding_return)
    )


@loans_setup_required
def funding_loan_statement_pdf(request, pk):
    loan = _funding_document_loan(request, pk)
    if not hasattr(loan, "terms_snapshot"):
        raise Http404("Funding statement is available only after activation.")
    detail = get_funding_loan_detail(pk)
    return PawnLoanDocumentService.build_pdf_response(
        FundingLoanDocumentService.render_statement(loan, detail)
    )


@loans_setup_required
def funding_loan_read_detail(request, pk):
    try:
        detail = get_funding_loan_detail(pk)
    except FundingLoanSelectorError as exc:
        raise Http404(str(exc)) from exc
    draft = None
    if detail.summary.state == "DRAFT":
        draft = get_funding_loan_draft_inputs(pk)
    settlement = None
    if detail.summary.state in {"ACTIVE", "SETTLEMENT_PENDING"}:
        settlement = get_funding_settlement_readiness(pk, detail=detail)
    return render(
        request,
        "loans/setup/funding/detail.html",
        {
            "detail": detail,
            "draft": draft,
            "settlement": settlement,
            "activation_form": FundingLoanActivationForm(),
            "cancellation_form": FundingLoanCancellationForm(),
            "closure_form": FundingLoanClosureForm(),
            "correction_form": FundingCorrectionForm(
                initial={
                    "effective_date": timezone.localdate(),
                    "request_key": uuid.uuid4(),
                }
            ),
            "repayment_form": FundingLoanRepaymentForm(
                initial={
                    "effective_date": timezone.localdate(),
                    "request_key": uuid.uuid4(),
                }
            ),
            "return_form": FundingCollateralReturnForm(
                collateral_rows=detail.collateral,
                initial={
                    "effective_date": timezone.localdate(),
                    "request_key": uuid.uuid4(),
                },
            ),
        },
    )
