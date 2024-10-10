from operator import attrgetter

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Case, F, IntegerField, Sum, Value, When, Window
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django_tables2 import RequestConfig
from django_tables2.export.export import TableExport

from apps.tenant_apps.dea.utils.currency import Balance
from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..filters import AccountFilter
from ..forms import AccountForm, AccountStatementForm, AccountTransactionForm
from ..models import (
    Account,
    Accountbalance,
    AccountStatement,
    AccountTransaction,
    JournalEntry,
    MoneyField,
)
from ..tables import AccountTable


def set_acc_ob(request, pk):
    # if this is a POST request we need to process the form data
    if request.method == "POST":
        # create a form instance and populate it with data from the request:
        form = AccountStatementForm(request.POST)
        # check whether it's valid:
        if form.is_valid():
            # process the data in form.cleaned_data as required
            # ...
            # redirect to a new URL:
            form.save()
            return redirect("/")

    # if a GET (or any other method) we'll create a blank form
    else:
        form = AccountStatementForm()

    return render(request, "dea/set_acc_ob.html", {"form": form})


@transaction.atomic()
def audit_acc(request, pk):
    acc = get_object_or_404(Account, pk=pk)
    acc.audit()
    return redirect(acc)


@login_required
def account_list(request):
    context = {}
    f = AccountFilter(
        request.GET,
        queryset=Account.objects.select_related(
            "accountbalance",
            "contact",
            "AccountType_Ext",
        ).order_by("contact__name"),
    )
    table = AccountTable(f.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    export_format = request.GET.get("_export", None)
    if TableExport.is_valid_format(export_format):
        # TODO speed up the table export using celery

        exporter = TableExport(
            export_format,
            table,
            exclude_columns=("actions",),
            dataset_kwargs={"title": "AccountsBalance"},
        )
        return exporter.response(f"table.{export_format}")
    context["filter"] = f
    context["table"] = table
    return render(request, "dea/account_list.html", context)


@login_required
def get_customer_balance(request):
    customer = request.GET.get("customer")
    acc = get_object_or_404(Account, contact__pk=customer)
    # Construct the HTML for the Bootstrap 5 alert
    alert_html = f"""
    <div class="alert alert-info" role="alert">
        <h4 class="alert-heading">Customer Balance</h4>
        
        <p>Balance: {acc.current_balance()}</p>
    </div>
    """
    return HttpResponse(alert_html)


@login_required
@for_htmx(use_block="content")
def account_detail(request, pk=None):
    acc = get_object_or_404(Account, pk=pk)
    acctype = acc.AccountType_Ext.XactTypeCode.XactTypeCode
    accountbalance = acc.accountbalance
    ct = {}
    ct["object"] = acc
    ct["accountbalance"] = accountbalance
    ct["opening_balance"] = accountbalance.get_ob()
    ct["closing_balance"] = accountbalance.get_currbal()

    txns = acc.txns(since=accountbalance.ls_created or None)

    # Convert the queryset to a list
    account_transactions_list = list(txns)

    # Sort the list in Python using the voucher_Date attribute of the content_object
    # account_transactions_list.sort(
    #     key=lambda x: attrgetter("journal_entry.content_object.voucher_date")(x)
    # )

    running_totals = []
    running_total = Balance()

    for txn in account_transactions_list:
        if acctype == "Cr":
            if txn.XactTypeCode_id == "Cr":
                running_total -= Balance([txn.amount])
            else:
                running_total += Balance([txn.amount])
        else:
            if txn.XactTypeCode_id == "Cr":
                running_total += Balance([txn.amount])
            else:
                running_total -= Balance([txn.amount])

        running_totals.append(running_total + accountbalance.get_ob())
    ct["running_totals"] = running_totals
    ct["raw"] = account_transactions_list

    return TemplateResponse(
        request, "dea/account_detail.html", {"object": acc, "ct": ct}
    )


def account_delete(request, pk):
    account = get_object_or_404(Account, pk=pk)
    if request.method == "POST":
        account.delete()
        return HttpResponseRedirect("/accounts/")
    return render(request, "account_confirm_delete.html", {"account": account})


def accountstatement_list(request):
    accountstatements = AccountStatement.objects.all()
    return render(
        request, "accountstatement_list.html", {"accountstatements": accountstatements}
    )


def accountstatement_detail(request, pk):
    accountstatement = get_object_or_404(AccountStatement, pk=pk)
    return render(
        request, "accountstatement_detail.html", {"accountstatement": accountstatement}
    )


def accountstatement_delete(request, pk):
    accountstatement = get_object_or_404(AccountStatement, pk=pk)
    if request.method == "POST":
        accountstatement.delete()
        return HttpResponseRedirect("/accountstatements/")
    return render(
        request,
        "accountstatement_confirm_delete.html",
        {"accountstatement": accountstatement},
    )


def accounttransaction_list(request):
    accounttransactions = AccountTransaction.objects.all()
    return render(
        request,
        "accounttransaction_list.html",
        {"accounttransactions": accounttransactions},
    )


def accounttransaction_detail(request, pk):
    accounttransaction = get_object_or_404(AccountTransaction, pk=pk)
    return render(
        request,
        "accounttransaction_detail.html",
        {"accounttransaction": accounttransaction},
    )


def accounttransaction_create(request, pk=None):
    journal_entry = get_object_or_404(JournalEntry, pk=pk)
    if request.method == "POST":
        form = AccountTransactionForm(
            request.POST, initial={"journal_entry": journal_entry}
        )
        if form.is_valid():
            accounttransaction = form.save(commit=False)
            accounttransaction.journal_entry = journal_entry
            accounttransaction.save()
            messages.success(request, "Account Transaction created successfully!")
            return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})
    else:
        form = AccountTransactionForm(
            initial={"journal_entry": journal_entry}, journalentry_id=journal_entry.id
        )
    return render(request, "partials/crispy_form.html", {"form": form})


def accounttransaction_update(request, pk):
    accounttransaction = get_object_or_404(AccountTransaction, pk=pk)
    if request.method == "POST":
        form = AccountTransactionForm(request.POST, instance=accounttransaction)
        if form.is_valid():
            accounttransaction = form.save(commit=False)
            accounttransaction.journal_entry = journal_entry
            accounttransaction.save()
            messages.success(request, "Account Transaction updated successfully!")
            return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})
    else:
        form = AccountTransactionForm(instance=accounttransaction)
    return render(request, "partials/crispy_form.html", {"form": form})


def accounttransaction_delete(request, pk):
    accounttransaction = get_object_or_404(AccountTransaction, pk=pk)
    if request.method == "POST":
        accounttransaction.delete()
        messages.success(request, "Account Transaction deleted successfully!")
        return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})
