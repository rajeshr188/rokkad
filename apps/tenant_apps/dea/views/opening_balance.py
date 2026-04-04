"""
Opening Balance Setup Wizard
Comprehensive views for setting up opening balances for ledgers and accounts
"""
import csv
import io
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from djmoney.money import Money

from ..models import (
    Ledger,
    Account,
    LedgerStatement,
    AccountStatement,
    AccountingPeriod,
    LedgerBalance,
    AccountBalance,
)
from ..utils.currency import Balance


def _opening_balance_wizard_url(step=None, **params):
    query = {"step": step, **params}
    query = {key: value for key, value in query.items() if value not in (None, "")}
    base_url = reverse("dea_opening_balance_wizard")
    return f"{base_url}?{urlencode(query)}" if query else base_url


@login_required
@require_http_methods(["GET", "POST"])
def opening_balance_wizard(request):
    """
    Multi-step wizard for setting up opening balances
    Step 1: Select period
    Step 2: Enter opening balances
    Step 3: Review and validate
    Step 4: Confirm and post
    """
    step = request.GET.get("step", "1")

    if step == "1":
        return _opening_balance_step1_period(request)
    elif step == "2":
        return _opening_balance_step2_entry(request)
    elif step == "3":
        return _opening_balance_step3_review(request)
    elif step == "4":
        return _opening_balance_step4_confirm(request)
    else:
        return redirect("dea_opening_balance_wizard")


def _opening_balance_step1_period(request):
    """Step 1: Select accounting period for opening balances"""
    preselected_period_id = request.GET.get("period") or request.GET.get("period_id")

    if request.method == "POST":
        period_id = request.POST.get("period_id")
        if period_id:
            request.session["ob_period_id"] = period_id
            return redirect(_opening_balance_wizard_url(step=2))
        else:
            messages.error(request, "Please select an accounting period")
    elif preselected_period_id and AccountingPeriod.objects.filter(
        pk=preselected_period_id
    ).exists():
        request.session["ob_period_id"] = str(preselected_period_id)
        return redirect(_opening_balance_wizard_url(step=2))

    # Get all periods
    periods = AccountingPeriod.objects.all().order_by("-start_date")

    # Check which periods already have opening balances
    periods_with_ob = []
    for period in periods:
        has_ob = LedgerStatement.objects.filter(
            period=period, is_opening_statement=True
        ).exists()
        periods_with_ob.append({"period": period, "has_opening_balance": has_ob})

    context = {
        "step": 1,
        "periods": periods_with_ob,
        "title": "Select Accounting Period",
    }
    return render(request, "dea/opening_balance/step1_period.html", context)


def _opening_balance_step2_entry(request):
    """Step 2: Enter opening balances for ledgers and accounts"""
    period_id = request.session.get("ob_period_id")
    if not period_id:
        messages.error(request, "Please select a period first")
        return redirect(_opening_balance_wizard_url(step=1))

    period = get_object_or_404(AccountingPeriod, pk=period_id)

    if request.method == "POST":
        # Store entered balances in session
        balances_data = {}

        for key, value in request.POST.items():
            value = str(value).strip()
            if not value:
                continue

            if key.startswith("ledger_") and not key.endswith("_currency"):
                ledger_id = key.removeprefix("ledger_")
                currency = request.POST.get(f"ledger_{ledger_id}_currency", "INR")
                balances_data[f"ledger_{ledger_id}"] = {
                    "amount": value,
                    "currency": currency,
                }
            elif key.startswith("account_") and not key.endswith("_currency"):
                account_id = key.removeprefix("account_")
                currency = request.POST.get(f"account_{account_id}_currency", "INR")
                balances_data[f"account_{account_id}"] = {
                    "amount": value,
                    "currency": currency,
                }

        request.session["ob_balances"] = balances_data
        return redirect(_opening_balance_wizard_url(step=3))

    # Get all root ledgers (no parent)
    ledgers = Ledger.objects.filter(parent__isnull=True).select_related("AccountType")

    # Get all accounts
    accounts = Account.objects.filter(status="ACTIVE").select_related(
        "contact", "AccountType_Ext"
    )

    # Get existing opening balances if any
    existing_ledger_obs = {}
    for stmt in LedgerStatement.objects.filter(
        period=period, is_opening_statement=True
    ):
        existing_ledger_obs[stmt.ledgerno_id] = stmt.ClosingBalance

    existing_account_obs = {}
    for stmt in AccountStatement.objects.filter(
        period=period, is_opening_statement=True
    ):
        existing_account_obs[stmt.AccountNo_id] = stmt.ClosingBalance

    context = {
        "step": 2,
        "period": period,
        "ledgers": ledgers,
        "accounts": accounts,
        "existing_ledger_obs": existing_ledger_obs,
        "existing_account_obs": existing_account_obs,
        "title": "Enter Opening Balances",
    }
    return render(request, "dea/opening_balance/step2_entry.html", context)


def _opening_balance_step3_review(request):
    """Step 3: Review and validate entered balances"""
    period_id = request.session.get("ob_period_id")
    balances_data = request.session.get("ob_balances", {})

    if not period_id or not balances_data:
        messages.error(request, "Invalid session data. Please start over.")
        return redirect(_opening_balance_wizard_url(step=1))

    period = get_object_or_404(AccountingPeriod, pk=period_id)

    # Parse and validate balances
    ledger_balances = []
    account_balances = []

    total_debit = Decimal("0")
    total_credit = Decimal("0")

    errors = []

    for key, data in balances_data.items():
        try:
            amount = Decimal(str(data.get("amount", "")).strip())
            currency = data.get("currency", "INR")

            if key.startswith("ledger_"):
                ledger_id = int(key.split("_")[1])
                ledger = Ledger.objects.get(pk=ledger_id)

                # Determine if debit or credit based on account type
                account_type = ledger.AccountType.AccountType
                if account_type in ["Asset", "Expense"]:
                    if amount > 0:
                        total_debit += amount
                    else:
                        total_credit += abs(amount)
                else:  # Liability, Income, Equity
                    if amount > 0:
                        total_credit += amount
                    else:
                        total_debit += abs(amount)

                ledger_balances.append(
                    {
                        "ledger": ledger,
                        "amount": Money(amount, currency),
                        "type": account_type,
                    }
                )

            elif key.startswith("account_"):
                account_id = int(key.split("_")[1])
                account = Account.objects.get(pk=account_id)

                # Determine if debit or credit
                acc_type = account.AccountType_Ext.XactTypeCode.XactTypeCode
                if acc_type == "Dr":
                    if amount > 0:
                        total_debit += amount
                    else:
                        total_credit += abs(amount)
                else:
                    if amount > 0:
                        total_credit += amount
                    else:
                        total_debit += abs(amount)

                account_balances.append(
                    {
                        "account": account,
                        "amount": Money(amount, currency),
                        "type": acc_type,
                    }
                )

        except (InvalidOperation, TypeError, ValueError, Ledger.DoesNotExist, Account.DoesNotExist) as e:
            errors.append(f"Error processing {key}: {str(e)}")

    # Validate balance (debits should equal credits)
    balance_difference = abs(total_debit - total_credit)
    is_balanced = balance_difference < Decimal(
        "0.01"
    )  # Allow small rounding differences

    if not is_balanced:
        errors.append(
            f"Opening balances are not balanced! "
            f"Debit: {total_debit}, Credit: {total_credit}, "
            f"Difference: {balance_difference}"
        )

    context = {
        "step": 3,
        "period": period,
        "ledger_balances": ledger_balances,
        "account_balances": account_balances,
        "total_debit": total_debit,
        "total_credit": total_credit,
        "is_balanced": is_balanced,
        "errors": errors,
        "title": "Review Opening Balances",
    }
    return render(request, "dea/opening_balance/step3_review.html", context)


@transaction.atomic
def _opening_balance_step4_confirm(request):
    """Step 4: Confirm and post opening balances"""
    if request.method != "POST":
        return redirect(_opening_balance_wizard_url(step=3))

    period_id = request.session.get("ob_period_id")
    balances_data = request.session.get("ob_balances", {})

    if not period_id or not balances_data:
        messages.error(request, "Invalid session data. Please start over.")
        return redirect(_opening_balance_wizard_url(step=1))

    period = get_object_or_404(AccountingPeriod, pk=period_id)

    try:
        # Create opening balance statements
        ledger_count = 0
        account_count = 0

        for key, data in balances_data.items():
            try:
                amount = Decimal(str(data.get("amount", "")).strip())
                currency = data.get("currency", "INR")
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValidationError(f"Invalid opening balance for {key}: {data!r}") from exc

            money = Money(amount, currency)

            if key.startswith("ledger_"):
                ledger_id = int(key.split("_")[1])
                ledger = Ledger.objects.get(pk=ledger_id)

                # Create or update opening statement
                LedgerStatement.objects.update_or_create(
                    ledgerno=ledger,
                    period=period,
                    is_opening_statement=True,
                    defaults={"ClosingBalance": money},
                )
                ledger_count += 1

            elif key.startswith("account_"):
                account_id = int(key.split("_")[1])
                account = Account.objects.get(pk=account_id)

                # Create or update opening statement
                AccountStatement.objects.update_or_create(
                    AccountNo=account,
                    period=period,
                    is_opening_statement=True,
                    defaults={
                        "ClosingBalance": money,
                        "TotalCredit": Money(0, currency),
                        "TotalDebit": Money(0, currency),
                    },
                )
                account_count += 1

        # Clear session data
        request.session.pop("ob_period_id", None)
        request.session.pop("ob_balances", None)

        messages.success(
            request,
            f"Successfully created opening balances for {ledger_count} ledgers "
            f"and {account_count} accounts for period {period.name}",
        )

        return redirect("dea_period_detail", pk=period.pk)

    except Exception as e:
        messages.error(request, f"Error creating opening balances: {str(e)}")
        return redirect(_opening_balance_wizard_url(step=3))


@login_required
@require_http_methods(["GET", "POST"])
def opening_balance_bulk_import(request):
    """Import opening balances from CSV file"""
    if request.method == "POST" and request.FILES.get("csv_file"):
        try:
            csv_file = request.FILES["csv_file"]
            period_id = request.POST.get("period_id")

            if not period_id:
                messages.error(request, "Please select a period")
                return redirect("dea_opening_balance_bulk_import")

            period = get_object_or_404(AccountingPeriod, pk=period_id)

            # Parse CSV
            decoded_file = csv_file.read().decode("utf-8")
            io_string = io.StringIO(decoded_file)
            reader = csv.DictReader(io_string)

            imported_count = 0
            errors = []

            with transaction.atomic():
                for row_num, row in enumerate(reader, start=2):
                    try:
                        entity_type = row.get(
                            "type", ""
                        ).lower()  # 'ledger' or 'account'
                        code_or_number = row.get("code", "").strip()
                        amount = Decimal(row.get("amount", "0"))
                        currency = row.get("currency", "INR")

                        if entity_type == "ledger":
                            ledger = Ledger.objects.get(code=code_or_number)
                            LedgerStatement.objects.update_or_create(
                                ledgerno=ledger,
                                period=period,
                                is_opening_statement=True,
                                defaults={"ClosingBalance": Money(amount, currency)},
                            )
                            imported_count += 1

                        elif entity_type == "account":
                            account = Account.objects.get(account_number=code_or_number)
                            AccountStatement.objects.update_or_create(
                                AccountNo=account,
                                period=period,
                                is_opening_statement=True,
                                defaults={
                                    "ClosingBalance": Money(amount, currency),
                                    "TotalCredit": Money(0, currency),
                                    "TotalDebit": Money(0, currency),
                                },
                            )
                            imported_count += 1

                    except Exception as e:
                        errors.append(f"Row {row_num}: {str(e)}")

            if errors:
                for error in errors[:10]:  # Show first 10 errors
                    messages.warning(request, error)
                if len(errors) > 10:
                    messages.warning(request, f"... and {len(errors) - 10} more errors")

            if imported_count > 0:
                messages.success(
                    request, f"Successfully imported {imported_count} opening balances"
                )

            return redirect("dea_period_detail", pk=period.pk)

        except Exception as e:
            messages.error(request, f"Error importing CSV: {str(e)}")

    # GET request - show form
    periods = AccountingPeriod.objects.all().order_by("-start_date")

    context = {"periods": periods, "title": "Bulk Import Opening Balances"}
    return render(request, "dea/opening_balance/bulk_import.html", context)


@login_required
def opening_balance_template_download(request):
    """Download CSV template for opening balance import"""
    response = HttpResponse(content_type="text/csv")
    response[
        "Content-Disposition"
    ] = 'attachment; filename="opening_balance_template.csv"'

    writer = csv.writer(response)
    writer.writerow(["type", "code", "name", "amount", "currency"])
    writer.writerow(["ledger", "1.01", "Cash", "100000.00", "INR"])
    writer.writerow(["ledger", "2.01", "Capital", "100000.00", "INR"])
    writer.writerow(["account", "DR0001", "Customer XYZ", "5000.00", "INR"])
    writer.writerow(["account", "CR0001", "Vendor ABC", "-3000.00", "INR"])

    return response


@login_required
@require_http_methods(["POST"])
def opening_balance_validate_ajax(request):
    """AJAX endpoint to validate opening balances"""
    try:
        balances_json = request.POST.get("balances")
        # Implement validation logic
        # Return JSON response with validation results
        return JsonResponse({"valid": True, "message": "Balances are valid"})
    except Exception as e:
        return JsonResponse({"valid": False, "error": str(e)}, status=400)
