from django.db.models import Prefetch, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render
from django_tables2 import RequestConfig
from django_tables2.export.export import TableExport

from ..filters import LedgerTransactionFilter
from ..models import (AccountTransaction, AccountType, Balance, Ledger,
                      Ledgerbalance, LedgerTransaction)
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
    # ac_txns = AccountTransaction.objects.all().select_related("Account","ledgerno","XactTypeCode","journal_entry","XactTypeCode_ext")
    grouped_transactions = {}

    for transaction in f.qs:
        ledger_credit = transaction.ledgerno
        ledger_debit = transaction.ledgerno_dr

        if ledger_credit not in grouped_transactions:
            grouped_transactions[ledger_credit] = {"debit": [], "credit": []}
        if ledger_debit not in grouped_transactions:
            grouped_transactions[ledger_debit] = {"debit": [], "credit": []}

        grouped_transactions[ledger_credit]["credit"].append(transaction)
        grouped_transactions[ledger_debit]["debit"].append(transaction)
    context["grouped_transactions"] = grouped_transactions
    table = LedgerTransactionTable(f.qs)
    RequestConfig(request, paginate={"per_page": 10}).configure(table)
    export_format = request.GET.get("_export", None)
    context["filter"] = f
    context["table"] = table
    return render(request, "dea/gl.html", context)


def daybook(request):
    ledgers = Ledger.objects.filter(
        Q(debit_txns__isnull=False)
        | Q(credit_txns__isnull=False)
        | Q(aleg__isnull=False)
    ).distinct()
    grouped_transactions = {}

    for ledger in ledgers:
        # Initialize the dictionary for each ledger
        ls = ledger.ledgerstatements.latest("created")
        print(ls.created)
        grouped_transactions[ledger] = {"debit": [], "credit": []}

        # Add dtxns and ctxns to the grouped transactions
        grouped_transactions[ledger]["debit"].extend(ledger.dtxns(since=ls.created))
        grouped_transactions[ledger]["credit"].extend(ledger.ctxns(since=ls.created))

        # Add aleg_txns to the grouped transactions based on xacttypecode
        for txn in ledger.aleg_txns(xacttypecode="Dr", since=ls.created):
            grouped_transactions[ledger]["debit"].append(txn)
        for txn in ledger.aleg_txns(xacttypecode="Cr", since=ls.created):
            grouped_transactions[ledger]["credit"].append(txn)

    return render(
        request,
        "dea/daybook.html",
        {
            "grouped_transactions": grouped_transactions,
        },
    )
