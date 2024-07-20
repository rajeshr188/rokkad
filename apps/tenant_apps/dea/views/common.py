from django.db.models import Sum
from django.shortcuts import render
from django_tables2 import RequestConfig
from django_tables2.export.export import TableExport

from ..filters import LedgerTransactionFilter
from ..models import (AccountType, Balance, Ledger, Ledgerbalance,
                      LedgerTransaction)
from ..tables import JournalEntriesTable, LedgerTransactionTable


def home(request):
    context = {}
    balancesheet = {}
    lb = Ledgerbalance.objects.all()
    account_type = AccountType.objects.all()

    for i in account_type:
        ledgers = i.ledgers.all()
        total = Balance()
        for j in ledgers:
            total = total + j.ledgerbalance.get_currbal()
        balancesheet[i.AccountType] = total

    balancesheet["assets"] = lb.filter(ledgerno__AccountType__AccountType="Asset")
    # # Get the balance sheet data
    # # balancesheet = lb.balancesheet()

    balancesheet["equity"] = lb.filter(ledgerno__AccountType__AccountType="Equity")
    ta = Balance()
    tl = Balance()
    ti = Balance()
    te = Balance()
    for i in lb:
        if i.ledgerno.AccountType.AccountType == "Asset":
            ta = ta + (i.get_currbal())
        elif i.ledgerno.AccountType.AccountType == "Liability":
            tl = tl + abs(i.get_currbal())
        elif i.ledgerno.AccountType.AccountType == "Income":
            ti = ti + abs(i.get_currbal())
        elif i.ledgerno.AccountType.AccountType == "Expense":
            te = te + abs(i.get_currbal())
    pnloss = {}
    pnloss["income"] = lb.filter(ledgerno__AccountType__AccountType="Income")
    pnloss["expense"] = lb.filter(ledgerno__AccountType__AccountType="Expense")
    context["ta"] = ta
    context["tl"] = tl
    context["ti"] = ti
    context["te"] = te
    balancesheet["liabilities"] = lb.filter(
        ledgerno__AccountType__AccountType="Liability"
    )
    context["pnloss"] = pnloss

    context["balancesheet"] = balancesheet
    context["ledger"] = lb

    return render(request, "dea/home.html", {"data": context})


def generalledger(request):
    context = {}
    f = LedgerTransactionFilter(
        request.GET,
        queryset=LedgerTransaction.objects.select_related(
            "ledgerno", "ledgerno_dr", "journal_entry"
        ).order_by("-created"),
    )
    table = LedgerTransactionTable(f.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    export_format = request.GET.get("_export", None)
    context["filter"] = f
    context["table"] = table
    return render(request, "dea/gl.html", context)


def daybook(request):
    try:
        latest_stmt = LedgerStatement.objects.latest()
    except:
        print("no ledger statements")
    return HttpResponse(status=404)
