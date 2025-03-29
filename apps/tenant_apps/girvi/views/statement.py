from django.contrib import messages
from django.db.models import Count, F
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Loan, Statement, StatementItem


def verification_session_list(request):
    sessions = Statement.objects.all()
    return render(
        request,
        "girvi/statement/statement_list.html",
        context={"sessions": sessions},
    )


def verification_session_create(request):
    v_session = Statement.objects.create(created_by=request.user)
    return redirect(v_session.get_absolute_url())


def verification_session_toggle(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    statement.toggle_complete(completed_by=request.user)
    if statement.is_complete:
        messages.success(request, f"Verification Session {statement} Completed")
    else:
        messages.success(request, f"Verification Session {statement} Reopened")
    return redirect(statement.get_absolute_url())


def verification_session_detail(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    # form = StatementItemForm(statement=statement)

    statement_items = statement.statementitem_set.select_related("loan").all()

    summary = {}
    if statement.completed:
        summary["dc"] = statement_items.filter(descrepancy_found=True)
        summary["descrepancy_loans"] = statement.statementitem_set.aggregate(
            total=Count("pk"),
            discrepancy=Count("pk", filter=F("descrepancy_found")),
        )
        summary["missing_loans"] = Loan.objects.unreleased().exclude(
            loan_id__in=statement_items.values_list("loan__loan_id", flat=True)
        )
        summary["unreleased"] = Loan.objects.unreleased()

    return render(
        request,
        "girvi/statement/statement_detail.html",
        context={
            "statement": statement,
            "items": statement_items,
            "summary": summary,
            # "form": form,
        },
    )


# def complete_verification_session(request, pk):
#     statement = get_object_or_404(Statement, pk=pk)

#     summary = statement.mark_complete(completed_by=request.user)
#     messages.warning(request, f"Found {summary['missing_count']} missing loans")
#     messages.warning(request, f"Found {summary['released_present_count']} released loans still present")

#     return redirect(statement.get_absolute_url())


def statement_delete(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    statement.delete()
    messages.error(request, f"Verification Session {statement} Deleted")
    return HttpResponse("")


from django.template.loader import render_to_string


def statement_item_add(request, pk):
    statement = get_object_or_404(Statement, pk=pk)
    if request.method == "POST":
        loan_id = request.POST.get("loan_id")
        try:
            loan = Loan.objects.get(loan_id=loan_id)
        except Loan.DoesNotExist:
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
                print(item)
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


def statement_item_delete(request, pk):
    item = get_object_or_404(StatementItem, pk=pk)
    item.delete()
    messages.error(request, f"Item {item} Deleted")
    return HttpResponse("")
