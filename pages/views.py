from datetime import date, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Sum, F, Exists, Q, OuterRef
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import TemplateView
from moneyed import Money
from openpyxl import load_workbook

from apps.onboarding.decorators import onboarding_required
from apps.orgs.decorators import roles_required
from apps.orgs.models import Company, CompanyInvitation, Membership
from apps.tenant_apps.contact.models import Customer
from apps.tenant_apps.contact.services import (
    active_customers,
    get_customers_by_type,
    get_customers_by_year,
)
from apps.tenant_apps.dea.models import (
    AccountStatement,
    AccountTransaction,
    JournalEntry,
    Ledger,
    LedgerTransaction,
    TransactionType_DE,
    TransactionType_Ext,
)
from apps.tenant_apps.dea.utils.currency import Balance
from apps.tenant_apps.girvi.models import License, GivenLoan, LoanItem, Release
from apps.tenant_apps.girvi.services import *
from apps.tenant_apps.purchase.models import Payment, Purchase
from apps.tenant_apps.sales.models import Invoice, Receipt

from .forms import MaxxFileUploadForm


class HomePageView(TemplateView):
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("dashboard")
        return super().dispatch(request, *args, **kwargs)

    def get_template_names(self):
        return ["pages/home.html"]


class TenantPageView(TemplateView):
    template_name = "pages/tenant.html"


@login_required
@onboarding_required
def Dashboard(request):
    """
    Smart landing page - routes user to appropriate destination.

    Decision tree:
    1. Has valid workspace selected → workspace_dashboard
    2. Has memberships → workspace_selector (choose workspace)
    3. No memberships → workspace_create (create first workspace)
    """
    user = request.user
    profile = user.profile

    # Check if user has valid selected workspace
    if profile.workspace and profile.workspace.schema_name != "public":
        try:
            # Verify membership still valid
            user.memberships.get(company=profile.workspace)
            # Direct to workspace dashboard with workspace_id
            return redirect("workspace_dashboard", workspace_id=profile.workspace.id)
        except Membership.DoesNotExist:
            # Clear invalid workspace
            profile.workspace = None
            profile.save()

    # Check if user has any workspaces
    memberships = user.memberships.filter(company__is_deleted=False)

    if memberships.exists():
        # Show workspace selector
        return redirect("workspace_selector")
    else:
        # No workspaces - prompt to create
        messages.info(request, "Let's create your first workspace!")
        return redirect("workspace_create")


# ============================================================================
# DEPRECATED: company_dashboard has been moved to apps.orgs.views.workspace_dashboard
# This function remains for backward compatibility only
# ============================================================================


@roles_required(["Owner", "Admin", "Member"])
def company_dashboard(request):
    """
    DEPRECATED: Use workspace_dashboard in apps.orgs.views instead.

    This view redirects to the new workspace_dashboard.
    Kept for backward compatibility with existing URL references.
    """
    if (
        request.user.profile.workspace
        and request.user.profile.workspace.schema_name == "public"
    ):
        return redirect("dashboard")

    # Redirect to new workspace_dashboard view
    workspace = request.user.profile.workspace
    if workspace:
        return redirect("workspace_dashboard", workspace_id=workspace.id)
    else:
        return redirect("workspace_selector")


# ============================================================================
# LEGACY: These views have been moved to apps/orgs/views.py for better organization
# - workspace_selector(), team_invitations(), workspace_select()
# - subscription_required() decorator
# ============================================================================


class AboutPageView(TemplateView):
    template_name = "pages/about.html"


class PrivacyPolicy(TemplateView):
    template_name = "pages/privacy_policy.html"


class CancellationAndRefund(TemplateView):
    template_name = "pages/cancellation_and_refund.html"


class TermsAndConditions(TemplateView):
    template_name = "pages/terms_and_conditions.html"


class ContactPageView(TemplateView):
    template_name = "pages/contact.html"


class HelpPageView(TemplateView):
    template_name = "pages/help.html"


class FaqPageView(TemplateView):
    template_name = "pages/faq.html"


def create_purchase_data(file):
    wb = load_workbook(file)
    sheet = wb.active
    # List of headers you want
    headers = [
        "Invoice No",
        "Vou Date",
        "Account Name",
        "Amount",
        "Chrgd.Wgt",
        "Pure Balance",
    ]  # replace with your headers
    # Get the second row values (headers in the Excel file)
    excel_headers = [cell.value for cell in sheet[2]]
    # Get the index of each header in your list
    header_indices = {header: excel_headers.index(header) for header in headers}

    purchases_data = []
    for row in sheet.iter_rows(min_row=5, values_only=True):
        if all(
            cell is None for cell in row
        ):  # Stop reading when an empty row is encountered
            break
        values = {header: row[index] for header, index in header_indices.items()}

        supplier, created = Customer.objects.get_or_create(name=values["Account Name"])
        purchases_data.append(
            Purchase(
                voucher_date=values["Vou Date"],
                voucher_no=values["Invoice No"],
                supplier=supplier,
                balance_gold=Money(values["Pure Balance"], "USD"),
                balance_cash=Money(values["Amount"], "INR"),
            )
        )  # replace field1, field2, field3 with your actual field names
    instances = Purchase.objects.bulk_create(purchases_data)
    return instances


def create_sales_data(file):
    wb = load_workbook(file)
    sheet = wb.active
    # List of headers you want
    headers = [
        "Invoice No",
        "Vou Date",
        "Account Name",
        "Amount",
        "Chrgd.Wgt",
        "Pure Balance",
    ]  # replace with your headers
    # Get the second row values (headers in the Excel file)
    excel_headers = [cell.value for cell in sheet[2]]
    # Get the index of each header in your list
    header_indices = {header: excel_headers.index(header) for header in headers}

    sales_data = []
    for row in sheet.iter_rows(min_row=5, values_only=True):
        if all(
            cell is None for cell in row
        ):  # Stop reading when an empty row is encountered
            break
        values = {header: row[index] for header, index in header_indices.items()}
        # {'Vou Date': datetime.datetime(2024, 4, 14, 0, 0), 'Account Name': 'Karuna Padaved', 'Amount': 0, 'Chrgd.Wgt': 6.674}

        customer, created = Customer.objects.get_or_create(name=values["Account Name"])
        balance_cash = Money(values["Amount"] or 0, "INR")
        balance_gold = Money(values["Pure Balance"] or 0, "USD")
        sales_data.append(
            Invoice(
                voucher_date=values["Vou Date"],
                voucher_no=values["Invoice No"],
                customer=customer,
                balance_cash=balance_cash,
                balance_gold=balance_gold,
            )
        )  # replace field1, field2, field3 with your actual field names
    instances = Invoice.objects.bulk_create(sales_data)
    return instances


def create_payment_data(file):
    wb = load_workbook(file)
    sheet = wb.active
    # List of headers you want
    headers = [
        "Ref No",
        "Vou Date",
        "Account Name",
        "Gold",
        "Silver",
        "Rate",
        "Conversion Value",
        "Amount",
    ]  # replace with your headers
    # Get the second row values (headers in the Excel file)
    excel_headers = [cell.value for cell in sheet[2]]
    # Get the index of each header in your list
    header_indices = {header: excel_headers.index(header) for header in headers}
    payment_data = []
    for row in sheet.iter_rows(min_row=4, values_only=True):
        if all(
            cell is None for cell in row
        ):  # Stop reading when an empty row is encountered
            break
        values = {header: row[index] for header, index in header_indices.items()}
        supplier, created = Customer.objects.get_or_create(name=values["Account Name"])

        if values["Gold"] is not None:
            total = Money(values["Gold"], "USD")
        elif values["Amount"] is not None:
            total = Money(values["Amount"], "INR")
        else:
            total = Money(0, "USD")

        payment_data.append(
            Payment(
                voucher_date=values["Vou Date"],
                voucher_no=values["Ref No"],
                supplier=supplier,
                total=total,
            )
        )  # replace field1, field2, field3 with your actual field names
    instances = Payment.objects.bulk_create(payment_data)
    return instances


def create_receipt_data(file):
    wb = load_workbook(file)
    sheet = wb.active
    # List of headers you want
    headers = [
        "Ref No",
        "Vou Date",
        "Account Name",
        "Gold",
        "Silver",
        "Rate",
        "Conversion Value",
        "Amount",
    ]  # replace with your headers
    # Get the second row values (headers in the Excel file)
    excel_headers = [cell.value for cell in sheet[2]]
    # Get the index of each header in your list
    header_indices = {header: excel_headers.index(header) for header in headers}
    receipt_data = []
    for row in sheet.iter_rows(min_row=4, values_only=True):
        if all(
            cell is None for cell in row
        ):  # Stop reading when an empty row is encountered
            break
        values = {header: row[index] for header, index in header_indices.items()}

        customer, created = Customer.objects.get_or_create(name=values["Account Name"])
        if values["Conversion Value"] is not None:
            weight = values["Gold"]
            rate = values["Rate"]
            total = Money(values["Gold"], "USD")
            receipt = Receipt(
                voucher_date=values["Vou Date"],
                voucher_no=values["Ref No"],
                customer=customer,
                weight=weight,
                touch=100,
                rate=rate,
                convert=True,
                amount=Money(values["Amount"] or 0, "INR"),
                total=total,
            )
        else:
            if values["Amount"] is not None:
                total = Money(values["Amount"], "INR")
            elif values["Gold"] is not None:
                total = Money(values["Gold"], "USD")
            receipt = Receipt(
                voucher_date=values["Vou Date"],
                voucher_no=values["Ref No"],
                customer=customer,
                total=total,
            )
        receipt_data.append(
            receipt
        )  # replace field1, field2, field3 with your actual field names
    instances = Receipt.objects.bulk_create(receipt_data)
    return instances


def create_debtors_data(file):
    wb = load_workbook(file)
    sheet = wb.active

    account_data = []
    # Fetch all accounts and store them in a dictionary
    # accounts = {account.name: account for account in Account.objects.all()}
    for row in sheet.iter_rows(min_row=9, values_only=True):
        if all(
            cell is None for cell in row
        ):  # Stop reading when an empty row is encountered
            break

        name = row[1]  # Column B is the 2nd column, but Python uses 0-based indexing
        customer, created = Customer.objects.get_or_create(name=name, customer_type="W")

        if not hasattr(customer, "account"):
            customer.save()

        # cash_debit = row[5]  # Column C
        # cash_credit = row[6]  # Column D
        # gold_debit = row[7]  # Column E
        # gold_credit = row[8]  # Column F
        cash_debit = row[7]  # Column C
        cash_credit = row[15]  # Column D
        gold_debit = row[21]  # Column E
        gold_credit = row[23]  # Column F
        print(customer, cash_debit, cash_credit, gold_debit, gold_credit)
        if cash_credit is not None:
            cash = Money(-cash_credit, "INR")
        elif cash_debit is not None:
            cash = Money(cash_debit, "INR")
        else:
            cash = Money(0, "INR")
        if gold_credit is not None:
            gold = Money(-gold_credit, "USD")
        elif gold_debit is not None:
            gold = Money(gold_debit, "USD")
        else:
            gold = Money(0, "USD")
        balance = Balance([cash, gold])
        tc = Balance(0, "INR")
        td = Balance(0, "INR")
        account_data.append(
            AccountStatement(
                AccountNo=customer.account,
                ClosingBalance=balance.monies(),
                TotalCredit=tc.monies(),
                TotalDebit=td.monies(),
            )
        )  # replace field1, field2, field3 with your actual field names
    AccountStatement.objects.bulk_create(account_data)


def create_creditors_data(file):
    wb = load_workbook(file)
    sheet = wb.active

    account_data = []
    # Fetch all accounts and store them in a dictionary
    # accounts = {account.name: account for account in Account.objects.all()}
    for row in sheet.iter_rows(min_row=4, values_only=True):
        if all(
            cell is None for cell in row
        ):  # Stop reading when an empty row is encountered
            break

        name = row[1]  # Column B is the 2nd column, but Python uses 0-based indexing
        customer, created = Customer.objects.get_or_create(name=name, customer_type="S")
        if not hasattr(customer, "account"):
            customer.save()

        cash_debit = row[5]  # Column C
        cash_credit = row[6]  # Column D
        gold_debit = row[7]  # Column E
        gold_credit = row[8]  # Column F
        # print(cash_debit,cash_credit,gold_debit,gold_credit)
        if cash_credit is not None:
            cash = Money(cash_credit, "INR")
        elif cash_debit is not None:
            cash = Money(-cash_debit, "INR")
        else:
            cash = Money(0, "INR")
        if gold_credit is not None:
            gold = Money(gold_credit, "USD")
        elif gold_debit is not None:
            gold = Money(-gold_debit, "USD")
        else:
            gold = Money(0, "USD")
        balance = Balance([cash, gold])
        tc = Balance(0, "INR")
        td = Balance(0, "INR")
        account_data.append(
            AccountStatement(
                AccountNo=customer.account,
                ClosingBalance=balance.monies(),
                TotalCredit=tc.monies(),
                TotalDebit=td.monies(),
            )
        )  # replace field1, field2, field3 with your actual field names
    AccountStatement.objects.bulk_create(account_data)


# def handle_import(data,model):
#     wb = load_workbook(file)
#     sheet = wb.active

#     purchases_data = []
#     for row in sheet.iter_rows(min_row=5, values_only=True):
#         if all(cell is None for cell in row):  # Stop reading when an empty row is encountered
#             break

#         date = row[6]  # Column G is the 7th column, but Python uses 0-based indexing
#         supplier = row[7]  # Column H
#         balance_gold = row[16]  # Column Q

#         supplier,created = Customer.objects.get_or_create(name=supplier, customer_type="S")
#         balance_gold = Money(balance_gold, 'USD')
#         purchases_data.append(Purchase(supplier=supplier, balance_gold = balance_gold))  # replace field1, field2, field3 with your actual field names


#     with transaction.atomic():
#         # Step 1: Create a list of JournalEntry instances
#         purchases = Purchase.objects.bulk_create(purchases_data)
#         journal_entries = [JournalEntry(content_object=purchase) for purchase in purchases]

#         # Step 2: Bulk create the JournalEntry instances
#         created_journal_entries = JournalEntry.objects.bulk_create(journal_entries)

#         ledger_transactions = []
#         account_transactions = []

#         # Create a dictionary to cache Ledger instances
#         ledgers = {}

#         # Step 3: For each JournalEntry instance, get the LedgerTransaction and AccountTransaction data
#         for journal_entry, purchase in zip(created_journal_entries, purchases):
#             lt_data, at_data = purchase.get_transactions()

#             for lt in lt_data:
#                 # Fetch the Ledger instance from the database if it's not already in the cache
#                 for key in ['ledgerno', 'ledgerno_dr']:
#                     if lt[key] not in ledgers:
#                         ledgers[lt[key]] = Ledger.objects.get(name=lt[key])
#                     lt[key] = ledgers[lt[key]]

#                 ledger_transaction = LedgerTransaction(journal_entry=journal_entry, **lt)
#                 ledger_transactions.append(ledger_transaction)

#             for at in at_data:
#                  # Fetch the Ledger instance from the database if it's not already in the cache
#                 if at['ledgerno'] not in ledgers:
#                     ledgers[at['ledgerno']] = Ledger.objects.get(name=at['ledgerno'])
#                 at['ledgerno'] = ledgers[at['ledgerno']]

#                 at["XactTypeCode"] = TransactionType_DE.objects.get(XactTypeCode=at["XactTypeCode"])
#                 at["XactTypeCode_ext"] = TransactionType_Ext.objects.get(XactTypeCode_ext=at["XactTypeCode_ext"])
#                 account_transaction = AccountTransaction(journal_entry=journal_entry, **at)
#                 account_transactions.append(account_transaction)

#         # Step 4: Bulk create the LedgerTransaction and AccountTransaction instances
#         lts = LedgerTransaction.objects.bulk_create(ledger_transactions)
#         ats = AccountTransaction.objects.bulk_create(account_transactions)
#         print(f"lts:{len(lts)} , ats:{len(ats)}")


def handle_import(instances):
    with transaction.atomic():
        journal_entries = [
            JournalEntry(content_object=instance) for instance in instances
        ]
        created_journal_entries = JournalEntry.objects.bulk_create(journal_entries)
        ledger_transactions = []
        account_transactions = []
        ledgers = {}
        for journal_entry, instance in zip(created_journal_entries, instances):
            lt_data, at_data = instance.get_transactions()
            # print(lt_data,at_data)
            for lt in lt_data:
                for key in ["ledgerno", "ledgerno_dr"]:
                    if lt[key] not in ledgers:
                        ledgers[lt[key]] = Ledger.objects.get(name=lt[key])
                    lt[key] = ledgers[lt[key]]
                ledger_transaction = LedgerTransaction(
                    journal_entry=journal_entry, **lt
                )
                ledger_transactions.append(ledger_transaction)
            for at in at_data:
                if at["ledgerno"] not in ledgers:
                    ledgers[at["ledgerno"]] = Ledger.objects.get(name=at["ledgerno"])
                at["ledgerno"] = ledgers[at["ledgerno"]]
                at["XactTypeCode"] = TransactionType_DE.objects.get(
                    XactTypeCode=at["XactTypeCode"]
                )
                at["XactTypeCode_ext"] = TransactionType_Ext.objects.get(
                    XactTypeCode_ext=at["XactTypeCode_ext"]
                )
                account_transaction = AccountTransaction(
                    journal_entry=journal_entry, **at
                )
                account_transactions.append(account_transaction)
        LedgerTransaction.objects.bulk_create(ledger_transactions)
        AccountTransaction.objects.bulk_create(account_transactions)


def maxx_files_upload(request):
    if request.method == "POST":
        form = MaxxFileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            model = form.cleaned_data["model"]
            file = form.cleaned_data["file"]
            if model == "Purchase":
                data = create_purchase_data(file)
                handle_import(data)
            elif model == "Sales":
                data = create_sales_data(file)
                handle_import(data)
            elif model == "Payment":
                data = create_payment_data(file)
                handle_import(data)
            elif model == "Receipt":
                data = create_receipt_data(file)
                handle_import(data)
            elif model == "Debtors":
                create_debtors_data(file)
            elif model == "Creditors":
                create_creditors_data(file)

            return HttpResponse("File uploaded & imported successfully")
    else:
        form = MaxxFileUploadForm()
    return render(request, "pages/maxx_files_upload.html", {"form": form})


# def handle_import(file, model, field_mapping):
#     wb = load_workbook(file)
#     sheet = wb.active
#     data = []
#     for row in sheet.iter_rows(min_row=5, values_only=True):
#         if all(cell is None for cell in row):  # Stop reading when an empty row is encountered
#             break
#         row_data = {}
#         for field, column in field_mapping.items():
#             row_data[field] = row[column]
#         data.append(model(**row_data))

#     with transaction.atomic():
#         instances = model.objects.bulk_create(data)
#         journal_entries = [JournalEntry(content_object=instance) for instance in instances]
#         created_journal_entries = JournalEntry.objects.bulk_create(journal_entries)
#         ledger_transactions = []
#         account_transactions = []
#         ledgers = {}
#         for journal_entry, instance in zip(created_journal_entries, instances):
#             lt_data, at_data = instance.get_transactions()
#             for lt in lt_data:
#                 for key in ['ledgerno', 'ledgerno_dr']:
#                     if lt[key] not in ledgers:
#                         ledgers[lt[key]] = Ledger.objects.get(name=lt[key])
#                     lt[key] = ledgers[lt[key]]
#                 ledger_transaction = LedgerTransaction(journal_entry=journal_entry, **lt)
#                 ledger_transactions.append(ledger_transaction)
#             for at in at_data:
#                 if at['ledgerno'] not in ledgers:
#                     ledgers[at['ledgerno']] = Ledger.objects.get(name=at['ledgerno'])
#                 at['ledgerno'] = ledgers[at['ledgerno']]
#                 at["XactTypeCode"] = TransactionType_DE.objects.get(XactTypeCode=at["XactTypeCode"])
#                 at["XactTypeCode_ext"] = TransactionType_Ext.objects.get(XactTypeCode_ext=at["XactTypeCode_ext"])
#                 account_transaction = AccountTransaction(journal_entry=journal_entry, **at)
#                 account_transactions.append(account_transaction)
#         lts = LedgerTransaction.objects.bulk_create(ledger_transactions)
#         ats = AccountTransaction.objects.bulk_create(account_transactions)
#         print(f"lts:{len(lts)} , ats:{len(ats)}")


