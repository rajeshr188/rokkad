"""
Bank Reconciliation Views

Provides views for bank statement reconciliation:
- List bank accounts
- View reconciliation details for an account
- Auto-match bank lines to GL transactions
- Manually match/unmatch individual items
"""

import csv
from io import StringIO
from decimal import Decimal

from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Q
from django_tenants.middleware import TenantMiddleware

from apps.tenant_apps.dea.models import (
    BankAccount,
    BankStatementLine,
    ReconciliationMatch,
    LedgerTransaction,
    AccountingPeriod,
)
from apps.tenant_apps.dea.services.reconciliation import ReconciliationService


class BankAccountListView(LoginRequiredMixin, ListView):
    """List all bank accounts for the current tenant"""
    model = BankAccount
    template_name = "dea/reconciliation/bank_account_list.html"
    context_object_name = "bank_accounts"
    paginate_by = 20

    def get_queryset(self):
        return BankAccount.objects.select_related("ledger").all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["title"] = "Bank Accounts"
        return context


class BankReconciliationDetailView(LoginRequiredMixin, DetailView):
    """Detail view for bank reconciliation of a specific account"""
    model = BankAccount
    template_name = "dea/reconciliation/reconciliation_detail.html"
    context_object_name = "bank_account"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        bank_account = self.object
        
        # Get current open period
        period = AccountingPeriod.objects.filter(is_active=True).first()
        if not period:
            context["error"] = "No active accounting period"
            return context

        context["period"] = period
        context["title"] = f"Reconciliation - {bank_account.name}"

        # Get bank statement lines for the period
        bank_lines = BankStatementLine.objects.filter(
            bank_account=bank_account,
            statement_date__gte=period.start_date,
            statement_date__lte=period.end_date,
        ).select_related("bank_account").prefetch_related("reconciliation_matches")

        # Get GL transactions for the account's ledger
        gl_lines = LedgerTransaction.objects.filter(
            Q(ledgerno_dr=bank_account.ledger) | Q(ledgerno=bank_account.ledger),
            journal_entry__created__date__gte=period.start_date,
            journal_entry__created__date__lte=period.end_date,
        ).select_related("journal_entry", "ledgerno_dr", "ledgerno").prefetch_related("reconciliation_matches")

        # Separate matched and unmatched
        matched_bank_lines = []
        unmatched_bank_lines = []
        for line in bank_lines:
            if line.is_reconciled:
                matched_bank_lines.append(line)
            else:
                unmatched_bank_lines.append(line)

        unmatched_gl_lines = [gl for gl in gl_lines if not gl.reconciliation_matches.exists()]

        # Calculate summary statistics
        summary = ReconciliationService.get_bank_statement_summary(bank_account, period)

        context.update({
            "bank_lines": bank_lines,
            "matched_bank_lines": matched_bank_lines,
            "unmatched_bank_lines": unmatched_bank_lines,
            "gl_lines": gl_lines,
            "unmatched_gl_lines": unmatched_gl_lines,
            "summary": summary,
        })

        return context


def import_bank_statement(request):
    """Import bank statement lines from CSV"""
    if request.method == "GET":
        context = {
            "title": "Import Bank Statement",
            "bank_accounts": BankAccount.objects.all(),
        }
        return render(request, "dea/reconciliation/import_bank_statement.html", context)

    if request.method == "POST":
        bank_account_id = request.POST.get("bank_account_id")
        csv_file = request.FILES.get("csv_file")

        if not bank_account_id or not csv_file:
            return JsonResponse({"error": "Missing bank account or CSV file"}, status=400)

        try:
            bank_account = BankAccount.objects.get(pk=bank_account_id)
        except BankAccount.DoesNotExist:
            return JsonResponse({"error": "Bank account not found"}, status=404)

        # Parse CSV file
        lines_created = 0
        errors = []

        try:
            csv_reader = csv.DictReader(
                StringIO(csv_file.read().decode("utf-8")),
                fieldnames=["statement_date", "description", "amount", "running_balance"],
            )
            next(csv_reader)  # Skip header row

            for row_num, row in enumerate(csv_reader, start=2):
                try:
                    statement_date = row.get("statement_date", "").strip()
                    description = row.get("description", "").strip()
                    amount = row.get("amount", "").strip()
                    running_balance = row.get("running_balance", "").strip()

                    if not statement_date or not amount:
                        errors.append(f"Row {row_num}: Missing date or amount")
                        continue

                    # Parse amount (remove currency symbols and spaces)
                    amount = Decimal(amount.replace(",", ""))
                    if running_balance:
                        running_balance = Decimal(running_balance.replace(",", ""))
                    else:
                        running_balance = Decimal(0)

                    BankStatementLine.objects.create(
                        bank_account=bank_account,
                        statement_date=statement_date,
                        description=description,
                        amount=amount,
                        running_balance=running_balance,
                        amount_currency=bank_account.currency,
                        running_balance_currency=bank_account.currency,
                    )
                    lines_created += 1
                except (ValueError, TypeError) as e:
                    errors.append(f"Row {row_num}: {str(e)}")

        except Exception as e:
            return JsonResponse({"error": f"CSV parsing error: {str(e)}"}, status=400)

        if lines_created == 0 and errors:
            return JsonResponse({"error": "No lines imported. " + "; ".join(errors[:5])}, status=400)

        return JsonResponse({
            "success": True,
            "lines_created": lines_created,
            "warnings": errors,
            "redirect": f"/dea/reconciliation/{bank_account_id}/",
        })


@require_http_methods(["POST"])
def auto_match_statements(request, bank_account_id):
    """Auto-match bank statement lines to GL transactions"""
    try:
        bank_account = BankAccount.objects.get(pk=bank_account_id)
    except BankAccount.DoesNotExist:
        return JsonResponse({"error": "Bank account not found"}, status=404)

    period = AccountingPeriod.objects.filter(is_active=True).first()
    if not period:
        return JsonResponse({"error": "No active accounting period"}, status=400)

    # Get tolerance from request (default 0)
    tolerance = Decimal(request.POST.get("tolerance", "0"))

    try:
        matches = ReconciliationService.auto_match(
            bank_account=bank_account,
            period=period,
            tolerance=tolerance,
            matched_by=request.user,
        )
        return JsonResponse({
            "success": True,
            "matches_created": len(matches),
            "message": f"Matched {len(matches)} bank statement lines",
        })
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=400)


@require_http_methods(["POST"])
def manual_match(request):
    """Manually match a bank line to a GL transaction"""
    bank_line_id = request.POST.get("bank_line_id")
    ledger_transaction_id = request.POST.get("ledger_transaction_id")

    if not bank_line_id or not ledger_transaction_id:
        return JsonResponse({"error": "Missing bank line or GL transaction"}, status=400)

    try:
        match = ReconciliationService.manual_match(
            bank_line_id=int(bank_line_id),
            ledger_transaction_id=int(ledger_transaction_id),
            matched_by=request.user,
        )
        return JsonResponse({
            "success": True,
            "message": "Match created successfully",
            "match_id": match.id,
        })
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Error: {str(e)}"}, status=500)


@require_http_methods(["POST"])
def unmatch(request):
    """Remove match for a bank line"""
    bank_line_id = request.POST.get("bank_line_id")

    if not bank_line_id:
        return JsonResponse({"error": "Missing bank line ID"}, status=400)

    try:
        ReconciliationService.unmatch(bank_line_id=int(bank_line_id))
        return JsonResponse({
            "success": True,
            "message": "Match removed successfully",
        })
    except ValueError as e:
        return JsonResponse({"error": str(e)}, status=400)
    except Exception as e:
        return JsonResponse({"error": f"Error: {str(e)}"}, status=500)
