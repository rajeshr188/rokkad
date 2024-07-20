from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render

from ..forms import LedgerForm, LedgerStatementForm, LedgerTransactionForm
from ..models import JournalEntry, Ledger, LedgerStatement, LedgerTransaction


def set_ledger_ob(request, pk):
    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = LedgerStatementForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            # ...
            # redirect to a new URL:
            form.save()
            return redirect("/")

    # if a GET (or any other method) we'll create a blank form
    else:
        form = LedgerStatementForm()

    return render(request, "dea/set_ledger_ob.html", {"form": form})


@transaction.atomic()
def audit_ledger(request):
    ledgers = Ledger.objects.all()
    for l in ledgers:
        l.audit()
    return redirect("/dea")


def ledger_list(request):
    ledgers = Ledger.objects.all()
    return render(request, "dea/ledger_list.html", {"ledgers": ledgers})


def ledger_detail(request, pk):
    ledger = get_object_or_404(Ledger, id=pk)
    ls_created = (
        ledger.ledgerstatements.latest().created
        if ledger.ledgerstatements.exists()
        else None
    )
    dtxns = ledger.dtxns(since=ls_created).select_related("journal_entry__content_type")
    ctxns = ledger.ctxns(since=ls_created).select_related("journal_entry__content_type")
    return render(
        request,
        "dea/ledger_detail.html",
        {"object": ledger, "dtxns": dtxns, "ctxns": ctxns},
    )


def ledger_create(request):
    if request.method == "POST":
        form = LedgerForm(request.POST)
        if form.is_valid():
            form.save()
            return HttpResponse("Ledger created successfully!")
    else:
        form = LedgerForm()
    return render(request, "dea/ledger_form.html", {"form": form})


def ledger_update(request, ledger_id):
    ledger = get_object_or_404(Ledger, id=ledger_id)
    if request.method == "POST":
        form = LedgerForm(request.POST, instance=ledger)
        if form.is_valid():
            form.save()
            return HttpResponse("Ledger updated successfully!")
    else:
        form = LedgerForm(instance=ledger)
    return render(request, "ledger_update.html", {"form": form})


def ledger_delete(request, ledger_id):
    ledger = get_object_or_404(Ledger, id=ledger_id)
    ledger.delete()
    return HttpResponse("Ledger deleted successfully!")


def ledger_statement_list(request):
    ledger_statements = LedgerStatement.objects.all()
    return render(
        request,
        "dea/ledger_statement_list.html",
        {"ledger_statements": ledger_statements},
    )


def ledger_statement_detail(request, ledger_statement_id):
    ledger_statement = get_object_or_404(LedgerStatement, id=ledger_statement_id)
    return render(
        request, "ledger_statement_detail.html", {"ledger_statement": ledger_statement}
    )


def ledger_statement_delete(request, ledger_statement_id):
    ledger_statement = get_object_or_404(LedgerStatement, id=ledger_statement_id)
    ledger_statement.delete()
    return HttpResponse("Ledger statement deleted successfully!")


def ledger_transaction_list(request):
    ledger_transactions = LedgerTransaction.objects.all()
    return render(
        request,
        "ledger_transaction_list.html",
        {"ledger_transactions": ledger_transactions},
    )


def ledger_transaction_detail(request, ledger_transaction_id):
    ledger_transaction = get_object_or_404(LedgerTransaction, id=ledger_transaction_id)
    return render(
        request,
        "ledger_transaction_detail.html",
        {"ledger_transaction": ledger_transaction},
    )


def ledger_transaction_create(request, pk=None):
    journal_entry = get_object_or_404(JournalEntry, pk=pk)
    if request.method == "POST":
        form = LedgerTransactionForm(
            request.POST, initial={"journal_entry": journal_entry}
        )
        if form.is_valid():
            form.save()
            return HttpResponse("Ledger transaction created successfully!")
    else:
        form = LedgerTransactionForm(initial={"journal_entry": journal_entry})
    return render(request, "dea/ledgertransaction_form.html", {"form": form})


def ledger_transaction_update(request, ledger_transaction_id):
    ledger_transaction = get_object_or_404(LedgerTransaction, id=ledger_transaction_id)
    if request.method == "POST":
        form = LedgerTransactionForm(request.POST, instance=ledger_transaction)
        if form.is_valid():
            form.save()
            return HttpResponse("Ledger transaction updated successfully!")
    else:
        form = LedgerTransactionForm(instance=ledger_transaction)
    return render(request, "ledger_transaction_update.html", {"form": form})


def ledger_transaction_delete(request, ledger_transaction_id):
    ledger_transaction = get_object_or_404(LedgerTransaction, id=ledger_transaction_id)
    ledger_transaction.delete()
    return HttpResponse("Ledger transaction deleted successfully!")
