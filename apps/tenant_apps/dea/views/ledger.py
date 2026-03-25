import logging

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.contrib.auth.decorators import login_required

from apps.tenant_apps.dea.models import ledger
from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..forms import LedgerForm, LedgerStatementForm, LedgerTransactionForm
from ..models import (
    JournalEntry,
    Ledger,
    LedgerStatement,
    LedgerTransaction,
    LedgerBalance,
)
from ..utils.currency import Balance, Money

logger = logging.getLogger(__name__)


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


# @for_htmx(use_block="content")
# def ledger_list(request):
#     # Get all ledgers with their balances in one query
#     # ledgers = (Ledger.objects
#     #            .select_related('AccountType', 'ledgerbalance')
#     #            .order_by('tree_id','lft','AccountType__AccountType', 'name'))
#     # Get all ledgers and prefetch their balances instead of select_related
#     ledgers = (Ledger.objects
#                .select_related('AccountType')
#                .prefetch_related('ledgerbalance')
#                .order_by('tree_id', 'lft'))
#     return TemplateResponse(request, "dea/ledger_list.html", {"ledgers": ledgers})


# @login_required
@for_htmx(use_block="content")
def ledger_list(request):
    # Get all ledger balances from view, ordered by tree structure
    ledger_balances = LedgerBalance.objects.select_related(
        "ledgerno", "AccountType"
    ).order_by("ledgerno__tree_id", "ledgerno__lft", "currency")

    # Group balances by ledger and create Balance objects
    ledgers_with_balances = {}
    for lb in ledger_balances:
        if lb.ledgerno_id not in ledgers_with_balances:
            ledgers_with_balances[lb.ledgerno_id] = {
                "ledger": lb.ledgerno,
                "name": lb.ledger_name,
                "account_type": lb.AccountType,
                "opening_balance": Balance(),
                "credits": Balance(),
                "debits": Balance(),
                "current_balance": Balance(),
            }

        # Convert each amount to Money and add to respective Balance objects
        entry = ledgers_with_balances[lb.ledgerno_id]
        entry["opening_balance"] += Balance([Money(lb.opening_balance, lb.currency)])
        entry["credits"] += Balance([Money(lb.total_credit_sum, lb.currency)])
        entry["debits"] += Balance([Money(lb.total_debit_sum, lb.currency)])
        entry["current_balance"] += Balance([Money(lb.current_balance, lb.currency)])

    context = {"ledgers": ledgers_with_balances.values()}

    return TemplateResponse(request, "dea/ledger_list.html", context)


# @login_required
@for_htmx(use_block="content")
def trial_balance(request, as_of=None):
    """
    Generate trial balance showing debit/credit totals per account type
    """
    # Get all ledger balances grouped by account type
    balances = LedgerBalance.objects.select_related("ledgerno", "AccountType").order_by(
        "AccountType__AccountType", "ledger_name", "currency"
    )

    # Group balances by account type
    trial_balance = {
        "assets": {"type": "Asset", "entries": []},
        "liabilities": {"type": "Liability", "entries": []},
        "income": {"type": "Revenue", "entries": []},
        "expenses": {"type": "Expense", "entries": []},
        "totals": {"debit": Balance(), "credit": Balance()},
    }

    # Process each balance entry
    for entry in balances:
        money = Money(entry.current_balance, entry.currency)
        account_type = entry.AccountType.AccountType
        balance_entry = {
            "ledger": entry.ledger_name,
            "currency": entry.currency,
            "debit": Money(0, entry.currency),
            "credit": Money(0, entry.currency),
        }

        # Place amount in correct column based on account type and balance
        if account_type in ["Asset", "Expense"]:
            if money.amount > 0:
                balance_entry["debit"] = money
                trial_balance["totals"]["debit"] += Balance([money])
            else:
                balance_entry["credit"] = abs(money)
                trial_balance["totals"]["credit"] += Balance([abs(money)])
        else:  # Liability, Revenue
            if money.amount > 0:
                balance_entry["credit"] = money
                trial_balance["totals"]["credit"] += Balance([money])
            else:
                balance_entry["debit"] = abs(money)
                trial_balance["totals"]["debit"] += Balance([abs(money)])

        # Add to appropriate section
        if account_type == "Asset":
            trial_balance["assets"]["entries"].append(balance_entry)
        elif account_type == "Liability":
            trial_balance["liabilities"]["entries"].append(balance_entry)
        elif account_type == "Revenue":
            trial_balance["income"]["entries"].append(balance_entry)
        elif account_type == "Expense":
            trial_balance["expenses"]["entries"].append(balance_entry)

    return TemplateResponse(
        request, "dea/trial_balance.html", {"trial_balance": trial_balance}
    )


# @login_required
def balance_sheet(request, as_of=None):
    """Generate balance sheet showing assets, liabilities and equity"""

    balances = LedgerBalance.objects.select_related("ledgerno", "AccountType").order_by(
        "AccountType__AccountType", "ledger_name", "currency"
    )

    statement = {
        "assets": {
            "current": {"entries": [], "total": Balance()},
            "fixed": {"entries": [], "total": Balance()},
            "total": Balance(),
        },
        "liabilities": {
            "current": {"entries": [], "total": Balance()},
            "long_term": {"entries": [], "total": Balance()},
            "total": Balance(),
        },
        "equity": {"entries": [], "total": Balance()},
    }

    for entry in balances:
        money = Money(entry.current_balance, entry.currency)
        account_type = entry.AccountType.AccountType

        if account_type == "Asset":
            if entry.ledgerno.is_current_asset:
                statement["assets"]["current"]["entries"].append(
                    {"ledger": entry.ledger_name, "balance": money}
                )
                statement["assets"]["current"]["total"] += Balance([money])
            else:
                statement["assets"]["fixed"]["entries"].append(
                    {"ledger": entry.ledger_name, "balance": money}
                )
                statement["assets"]["fixed"]["total"] += Balance([money])
            statement["assets"]["total"] += Balance([money])

        elif account_type == "Liability":
            if entry.ledgerno.is_current_liability:
                statement["liabilities"]["current"]["entries"].append(
                    {"ledger": entry.ledger_name, "balance": money}
                )
                statement["liabilities"]["current"]["total"] += Balance([money])
            else:
                statement["liabilities"]["long_term"]["entries"].append(
                    {"ledger": entry.ledger_name, "balance": money}
                )
                statement["liabilities"]["long_term"]["total"] += Balance([money])
            statement["liabilities"]["total"] += Balance([money])

        elif account_type == "Equity":
            statement["equity"]["entries"].append(
                {"ledger": entry.ledger_name, "balance": money}
            )
            statement["equity"]["total"] += Balance([money])

    return TemplateResponse(request, "dea/balance_sheet.html", {"statement": statement})


# @login_required
def income_statement(request, from_date=None, to_date=None):
    """Generate income statement (P&L) for a period"""

    balances = (
        LedgerBalance.objects.select_related("ledgerno", "AccountType")
        .filter(AccountType__AccountType__in=["Revenue", "Expense"])
        .order_by("AccountType__AccountType", "ledger_name", "currency")
    )

    statement = {
        "revenue": {"entries": [], "total": Balance()},
        "expenses": {"entries": [], "total": Balance()},
        "net_income": Balance(),
    }

    for entry in balances:
        money = Money(entry.current_balance, entry.currency)
        if entry.AccountType.AccountType == "Revenue":
            statement["revenue"]["entries"].append(
                {
                    "ledger": entry.ledger_name,
                    "balance": abs(money),  # Revenue is normally negative
                }
            )
            statement["revenue"]["total"] += Balance([abs(money)])
        else:  # Expense
            statement["expenses"]["entries"].append(
                {"ledger": entry.ledger_name, "balance": money}
            )
            statement["expenses"]["total"] += Balance([money])

    # Calculate net income
    statement["net_income"] = (
        statement["revenue"]["total"] - statement["expenses"]["total"]
    )

    return TemplateResponse(
        request, "dea/income_statement.html", {"statement": statement}
    )


@login_required
def profit_loss(request, from_date=None, to_date=None):
    """
    Generate Profit & Loss statement showing:
    - Revenue by type
    - Direct expenses (COGS)
    - Gross profit
    - Operating expenses
    - Operating profit
    - Other income/expenses
    - Net profit
    """

    # Get all revenue and expense accounts
    balances = (
        LedgerBalance.objects.select_related("ledgerno", "AccountType")
        .filter(AccountType__AccountType__in=["Revenue", "Expense"])
        .order_by("AccountType__AccountType", "ledger_name", "currency")
    )

    statement = {
        "revenue": {
            "operating": {"entries": [], "total": Balance()},
            "other": {"entries": [], "total": Balance()},
            "total": Balance(),
        },
        "expenses": {
            "direct": {"entries": [], "total": Balance()},  # COGS
            "operating": {"entries": [], "total": Balance()},
            "other": {"entries": [], "total": Balance()},
            "total": Balance(),
        },
        "gross_profit": Balance(),
        "operating_profit": Balance(),
        "net_profit": Balance(),
    }

    # Process each balance entry
    for entry in balances:
        money = Money(abs(entry.current_balance), entry.currency)
        category = entry.AccountType.AccountType

        if category == "Revenue":
            if entry.ledgerno.is_operating_revenue:
                statement["revenue"]["operating"]["entries"].append(
                    {"ledger": entry.ledger_name, "amount": money}
                )
                statement["revenue"]["operating"]["total"] += Balance([money])
            else:
                statement["revenue"]["other"]["entries"].append(
                    {"ledger": entry.ledger_name, "amount": money}
                )
                statement["revenue"]["other"]["total"] += Balance([money])
            statement["revenue"]["total"] += Balance([money])

        elif category == "Expense":
            if entry.ledgerno.is_direct_expense:
                statement["expenses"]["direct"]["entries"].append(
                    {"ledger": entry.ledger_name, "amount": money}
                )
                statement["expenses"]["direct"]["total"] += Balance([money])
            elif entry.ledgerno.is_operating_expense:
                statement["expenses"]["operating"]["entries"].append(
                    {"ledger": entry.ledger_name, "amount": money}
                )
                statement["expenses"]["operating"]["total"] += Balance([money])
            else:
                statement["expenses"]["other"]["entries"].append(
                    {"ledger": entry.ledger_name, "amount": money}
                )
                statement["expenses"]["other"]["total"] += Balance([money])
            statement["expenses"]["total"] += Balance([money])

    # Calculate profits
    statement["gross_profit"] = (
        statement["revenue"]["operating"]["total"]
        - statement["expenses"]["direct"]["total"]
    )

    statement["operating_profit"] = (
        statement["gross_profit"] - statement["expenses"]["operating"]["total"]
    )

    statement["net_profit"] = (
        statement["operating_profit"]
        + statement["revenue"]["other"]["total"]
        - statement["expenses"]["other"]["total"]
    )

    return TemplateResponse(
        request,
        "dea/profit_loss.html",
        {"statement": statement, "from_date": from_date, "to_date": to_date},
    )


# @login_required
def cash_flow_statement(request, from_date=None, to_date=None):
    """Generate cash flow statement showing operating, investing and financing activities"""

    cash_ledgers = LedgerBalance.objects.select_related(
        "ledgerno", "AccountType"
    ).filter(
        ledgerno__name__icontains="cash"  # Or your cash account identifier
    )

    statement = {
        "operating": {"entries": [], "total": Balance()},
        "investing": {"entries": [], "total": Balance()},
        "financing": {"entries": [], "total": Balance()},
        "net_change": Balance(),
        "opening_balance": Balance(),
        "closing_balance": Balance(),
    }

    # Get opening balances
    for cash in cash_ledgers:
        statement["opening_balance"] += Balance(
            [Money(cash.opening_balance, cash.currency)]
        )
        statement["closing_balance"] += Balance(
            [Money(cash.current_balance, cash.currency)]
        )

    statement["net_change"] = (
        statement["closing_balance"] - statement["opening_balance"]
    )

    return TemplateResponse(request, "dea/cash_flow.html", {"statement": statement})


def ledger_detail(request, pk):
    ledger = get_object_or_404(Ledger, id=pk)
    ls_created = (
        ledger.ledgerstatements.latest().created
        if ledger.ledgerstatements.exists()
        else None
    )
    dtxns = ledger.dtxns(since=ls_created).select_related(
        "journal_entry", "journal_entry__voucher"
    )
    ctxns = ledger.ctxns(since=ls_created).select_related(
        "journal_entry", "journal_entry__voucher"
    )
    logger.warn(f" in views:ledger_detail: {ledger} {dtxns} {ctxns}")
    cr_aleg_txns = ledger.aleg_txns(xacttypecode="Cr", since=ls_created)
    dr_aleg_txns = ledger.aleg_txns(xacttypecode="Dr", since=ls_created)
    return render(
        request,
        "dea/ledger_detail.html",
        {
            "object": ledger,
            "dtxns": dtxns,
            "ctxns": ctxns,
            "cr_aleg_txns": cr_aleg_txns,
            "dr_aleg_txns": dr_aleg_txns,
        },
    )


def ledger_create(request):
    if request.method == "POST":
        form = LedgerForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Ledger created successfully!")
            return HttpResponse(status=204, headers={"HX-Trigger": "ledgerListChanged"})
    else:
        form = LedgerForm()
    return render(request, "partials/crispy_form.html", {"form": form})


def ledger_update(request, ledger_id):
    ledger = get_object_or_404(Ledger, id=ledger_id)
    if request.method == "POST":
        form = LedgerForm(request.POST, instance=ledger)
        if form.is_valid():
            form.save()
            messages.success(request, "Ledger updated successfully!")
            return HttpResponse(status=204, headers={"HX-Trigger": "ledgerListChanged"})
    else:
        form = LedgerForm(instance=ledger)
    return render(request, "ledger_update.html", {"form": form})


def ledger_save(request, pk=None):
    if pk:
        ledger = get_object_or_404(Ledger, id=pk)
        form = LedgerForm(request.POST or None, instance=ledger)
        verb = "updated"
    else:
        form = LedgerForm(request.POST or None)
        verb = "created"

    if request.method == "POST":
        if form.is_valid():
            form.save()
            messages.success(request, "Ledger {verb} successfully!")
            return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})

    return render(request, "partials/crispy_form.html", {"form": form})


def ledger_delete(request, ledger_id):
    ledger = get_object_or_404(Ledger, id=ledger_id)
    ledger.delete()
    messages.success(request, "Ledger deleted successfully!")
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})


def ledger_statement_list(request):
    ledger_statements = LedgerStatement.objects.all()
    return render(
        request,
        "dea/ledgerstatement_list.html",
        {"object_list": ledger_statements},
    )


def ledger_statement_detail(request, ledger_statement_id):
    ledger_statement = get_object_or_404(LedgerStatement, id=ledger_statement_id)
    return render(
        request, "ledgerstatement_detail.html", {"ledger_statement": ledger_statement}
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
            ledger_transaction = form.save(commit=False)
            ledger_transaction.journal_entry = journal_entry
            ledger_transaction.save()
            messages.success(request, "Ledger transaction created successfully!")
            return HttpResponse(status=200, headers={"HX-Trigger": "listChanged"})
    else:
        form = LedgerTransactionForm(
            initial={"journal_entry": journal_entry}, journalentry_id=journal_entry.id
        )
    return render(request, "partials/crispy_form.html", {"form": form})


def ledger_transaction_update(request, pk):
    ledger_transaction = get_object_or_404(LedgerTransaction, id=pk)
    if request.method == "POST":
        form = LedgerTransactionForm(request.POST, instance=ledger_transaction)
        if form.is_valid():
            # ledger_transaction = form.save(commit=False)
            # ledger_transaction.journal_entry = journal_entry
            ledger_transaction.save()
            messages.success(request, "Ledger transaction updated successfully!")
            return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})
    else:
        form = LedgerTransactionForm(instance=ledger_transaction)
    return render(request, "partials/crispy_form.html", {"form": form})


def ledger_transaction_delete(request, pk):
    ledger_transaction = get_object_or_404(LedgerTransaction, id=pk)
    ledger_transaction.delete()
    messages.success(request, "Ledger transaction deleted successfully!")
    return HttpResponse(status=204, headers={"HX-Trigger": "listChanged"})


import io
import re

import openpyxl
from django import forms
from django.views import View


def extract_name(upistring):
    # Check if the input is None or an empty string
    if not upistring:
        return None

    # Define the regex pattern
    pattern = r"UPI-(.*?)-.*?@"

    # Search for the pattern in the input string
    match = re.search(pattern, upistring)

    # If a match is found, return the extracted name
    if match:
        return match.group(1)
    else:
        return None


class UploadFileForm(forms.Form):
    file = forms.FileField()


class FileUploadView(View):
    def get(self, request):
        form = UploadFileForm()
        return render(request, "dea/upload.html", {"form": form})

    #   process gopi sheet
    # def post(self, request):
    #     form = UploadFileForm(request.POST, request.FILES)
    #     if form.is_valid():
    #         file = request.FILES['file']
    #         wb = openpyxl.load_workbook(file)
    #         ws = wb.active

    #         # Initialize Faker
    #         fake = Faker()
    #         # Read each row and generate a list of dictionaries
    #         data = []
    #         for row in ws.iter_rows(min_row=2, values_only=True):  # Skip the header row
    #             voucher_date = row[0]
    #             ledger_name = row[1] if row[1] else fake.name()
    #             voucher_type = row[2]
    #             ledger_amount = row[3]
    #             receipt_ledger = row[4]
    #             ledger_amount_dr_cr = "Cr"  # Assuming Cr for all rows
    #             item_name = row[5]
    #             billed_quantity = row[6]
    #             item_rate = row[7]
    #             # print(voucher_date, ledger_name, voucher_type, ledger_amount, item_name, billed_quantity, item_rate)
    #             if voucher_type == "Sales" or voucher_type == "Purchase" and item_name:
    #                 row_data = [
    #                     voucher_date, voucher_type, ledger_name, ledger_amount, "Dr" if voucher_type =="Sales" else "Cr", "", "", "", "", "", "Item Invoice"
    #                 ]

    #                 second_row_data = [
    #                     "", "", voucher_type, ledger_amount - (ledger_amount * 0.03), "Cr"  if voucher_type =="Sales" else "Dr", item_name, billed_quantity, item_rate, "gms", billed_quantity*item_rate, ""
    #                 ]

    #                 cgst_data = [
    #                     "", "", "Tax - CGST @ 1.5%", ledger_amount * 0.015,"Cr"  if voucher_type =="Sales" else "Dr", "", "", "", "", "", ""
    #                 ]

    #                 sgst_data = [
    #                     "", "",  "Tax - SGST @ 1.5%", ledger_amount * 0.015, "Cr"  if voucher_type =="Sales" else "Dr", "", "", "", "", "", ""
    #                 ]
    #                 data.append(row_data)
    #                 data.append(second_row_data)
    #                 data.append(cgst_data)
    #                 data.append(sgst_data)
    #                 if receipt_ledger and voucher_type == "Sales":
    #                     receipt_ledger_data = [
    #                         voucher_date, "Receipt",ledger_name, ledger_amount, "Cr", "", "", "", "", "", ""
    #                     ]

    #                     receipt_as = [
    #                         "", "", receipt_ledger, ledger_amount, "Dr", "", "", "", "", "", ""
    #                     ]
    #                     data.append(receipt_ledger_data)
    #                     data.append(receipt_as)
    #                 else:
    #                     payment_ledger_data = [
    #                         voucher_date, "Payment",ledger_name, ledger_amount, "Dr", "", "", "", "", "", ""
    #                     ]

    #                     payment_as = [
    #                         "", "", receipt_ledger, ledger_amount, "Cr", "", "", "", "", "", ""
    #                     ]
    #                     data.append(payment_ledger_data)
    #                     data.append(payment_as)
    #         print(data)
    #         # Create a new workbook and worksheet
    #         new_wb = openpyxl.Workbook()
    #         new_ws = new_wb.active
    #         new_ws.title = "Processed Data"

    #         # Define headers
    #         headers = [
    #             "Voucher Date", "Voucher Type Name","Ledger Name", "Ledger Amount", "Ledger Amount Dr/Cr",
    #             "Item Name", "Billed Quantity", "Item Rate", "Item Rate per", "Item Amount", "Change Mode"
    #         ]
    #         new_ws.append(headers)

    #         # Write data to the new worksheet
    #         for row_data in data:
    #             # print(row_data)
    #             new_ws.append(row_data)

    #         # Save the new workbook to a BytesIO object
    #         output = io.BytesIO()
    #         new_wb.save(output)
    #         output.seek(0)

    #         # Return the new Excel file as a response
    #         response = HttpResponse(output, content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    #         response['Content-Disposition'] = 'attachment; filename="processed_data.xlsx"'
    #         return response
    #     return render(request, 'dea/upload.html', {'form': form})

    def post(self, request):
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            file = request.FILES["file"]
            wb = openpyxl.load_workbook(file)
            ws = wb.active

            # Read each row and generate a list of dictionaries
            data = []
            for row in ws.iter_rows(
                min_row=22, values_only=True
            ):  # Skip the header row
                print(row)
                voucher_date = row[0]
                ledger_name = extract_name(row[1])
                refno = row[2]

                withdrawal_amt = row[4]
                deposit_amt = row[5]  # Assuming Cr for all rows
                voucher_type = row[7]
                item_name = row[8]
                item_rate = row[9]
                ledger_amount = (
                    withdrawal_amt
                    if voucher_type in ["Sales", "Payment"]
                    else deposit_amt
                )
                billed_quantity = ledger_amount / item_rate if item_rate else 0
                receipt_ledger = "HDFC_BANK"
                # print(voucher_date, ledger_name, voucher_type, ledger_amount, item_name, billed_quantity, item_rate)
                if voucher_type == "Sales" or voucher_type == "Purchase" and item_name:
                    row_data = [
                        voucher_date,
                        voucher_type,
                        ledger_name,
                        ledger_amount,
                        "Dr" if voucher_type == "Sales" else "Cr",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "Item Invoice",
                    ]

                    second_row_data = [
                        "",
                        "",
                        voucher_type,
                        ledger_amount - (ledger_amount * 0.03),
                        "Cr" if voucher_type == "Sales" else "Dr",
                        item_name,
                        billed_quantity,
                        item_rate,
                        "gms",
                        billed_quantity * item_rate
                        - (billed_quantity * item_rate * 0.3),
                        "",
                    ]

                    cgst_data = [
                        "",
                        "",
                        "Tax - CGST @ 1.5%",
                        ledger_amount * 0.015,
                        "Cr" if voucher_type == "Sales" else "Dr",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]

                    sgst_data = [
                        "",
                        "",
                        "Tax - SGST @ 1.5%",
                        ledger_amount * 0.015,
                        "Cr" if voucher_type == "Sales" else "Dr",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                    ]
                    data.append(row_data)
                    data.append(second_row_data)
                    data.append(cgst_data)
                    data.append(sgst_data)
                    if voucher_type == "Sales":
                        receipt_ledger_data = [
                            voucher_date,
                            "Receipt",
                            ledger_name,
                            ledger_amount,
                            "Cr",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]

                        receipt_as = [
                            "",
                            "",
                            receipt_ledger,
                            ledger_amount,
                            "Dr",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]
                        data.append(receipt_ledger_data)
                        data.append(receipt_as)
                    else:
                        payment_ledger_data = [
                            voucher_date,
                            "Payment",
                            ledger_name,
                            ledger_amount,
                            "Dr",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]

                        payment_as = [
                            "",
                            "",
                            receipt_ledger,
                            ledger_amount,
                            "Cr",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]
                        data.append(payment_ledger_data)
                        data.append(payment_as)
            print(data)
            # Create a new workbook and worksheet
            new_wb = openpyxl.Workbook()
            new_ws = new_wb.active
            new_ws.title = "Processed Data"

            # Define headers
            headers = [
                "Voucher Date",
                "Voucher Type Name",
                "Ledger Name",
                "Ledger Amount",
                "Ledger Amount Dr/Cr",
                "Item Name",
                "Billed Quantity",
                "Item Rate",
                "Item Rate per",
                "Item Amount",
                "Change Mode",
            ]
            new_ws.append(headers)

            # Write data to the new worksheet
            for row_data in data:
                # print(row_data)
                new_ws.append(row_data)

            # Save the new workbook to a BytesIO object
            output = io.BytesIO()
            new_wb.save(output)
            output.seek(0)

            # Return the new Excel file as a response
            response = HttpResponse(
                output,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response[
                "Content-Disposition"
            ] = 'attachment; filename="processed_data.xlsx"'
            return response
        return render(request, "dea/upload.html", {"form": form})
