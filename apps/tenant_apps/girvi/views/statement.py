import logging

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import GivenLoan, Statement, StatementItem
from ..selectors import build_statement_detail_read_model
from .access import girvi_workspace_required


logger = logging.getLogger(__name__)


@girvi_workspace_required
def verification_session_list(request):
    sessions = Statement.objects.all()
    return render(
        request,
        "girvi/statement/statement_list.html",
        context={"sessions": sessions},
    )


@girvi_workspace_required
def verification_session_create(request):
    v_session = Statement.objects.create(created_by=request.user)
    return redirect(v_session.get_absolute_url())


@girvi_workspace_required
def verification_session_toggle(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    statement.toggle_complete(completed_by=request.user)
    if statement.is_complete:
        messages.success(request, f"Verification Session {statement} Completed")
    else:
        messages.success(request, f"Verification Session {statement} Reopened")
    return redirect(statement.get_absolute_url())


@girvi_workspace_required
def verification_session_detail(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    read_model = build_statement_detail_read_model(statement)

    return render(
        request,
        "girvi/statement/statement_detail.html",
        context=read_model,
    )


# def complete_verification_session(request, pk):
#     statement = get_object_or_404(Statement, pk=pk)

#     summary = statement.mark_complete(completed_by=request.user)
#     messages.warning(request, f"Found {summary['missing_count']} missing loans")
#     messages.warning(request, f"Found {summary['released_present_count']} released loans still present")

#     return redirect(statement.get_absolute_url())


@girvi_workspace_required
def statement_delete(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    statement.delete()
    messages.error(request, f"Verification Session {statement} Deleted")
    return HttpResponse("")


from django.template.loader import render_to_string


@girvi_workspace_required
def statement_item_add(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    if request.method == "POST":
        loan_id = request.POST.get("loan_id")
        try:
            loan = GivenLoan.objects.get(loan_id=loan_id)
        except GivenLoan.DoesNotExist:
            # Handle the error, e.g., log it, return a custom response, etc.
            loan = None

        if loan:
            if not loan.is_released:
                item = StatementItem.objects.create(statement=statement, loan=loan)
                messages.success(request, f"Added {loan} to {statement}")

            else:
                item = StatementItem.objects.create(
                    statement=statement,
                    loan=loan,
                    descrepancy_found=True,
                    descrepancy_note="Loan already released",
                )
                messages.error(request, f"Loan {loan_id} already released.")
                logger.info(
                    "Statement item discrepancy recorded",
                    extra={"statement_item_id": item.pk, "loan_id": loan_id},
                )
            # Construct the HTML snippet using the item attributes
            # item_html = f"""
            # <li class="list-group-item d-flex justify-content-between align-items-center">
            #     {item.loan}
            #     {'(Discrepancy: ' + item.descrepancy_note + ')' if item.descrepancy_found else ''}
            # </li>
            # """
            item_html = render_to_string(
                "girvi/statement/statement_item_detail.html", {"item": item}
            )
            return HttpResponse(item_html)
        else:
            item_html = f"""
            <li class="list-group-item">
                {loan_id}
                Not found
            </li>
            """
            return HttpResponse(item_html)
    return HttpResponse("")


@girvi_workspace_required
def statement_item_delete(request, pk):
    item = get_object_or_404(StatementItem, pk=pk)
    item.delete()
    messages.error(request, f"Item {item} Deleted")
    return HttpResponse("")
