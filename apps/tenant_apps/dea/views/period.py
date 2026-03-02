"""
Views for AccountingPeriod management

Provides comprehensive period management including:
- List all periods with status filters
- Create new periods  
- Close periods with validation
- Lock/unlock periods
- View period details and transactions
- Period-based reports
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils import timezone
from django_tables2 import RequestConfig
from moneyed import Money

from apps.tenant_apps.utils.htmx_utils import for_htmx

from ..filters import PeriodFilter
from ..forms import AccountingPeriodForm, PeriodCloseForm
from ..models import (
    Account,
    AccountingPeriod,
    AccountStatement,
    JournalEntry,
    Ledger,
    LedgerStatement,
)
from ..tables import PeriodTable
from ..utils.currency import Balance

logger = logging.getLogger(__name__)


@login_required
@for_htmx(use_block="content")
def period_list(request):
    """
    List all accounting periods with filtering by status
    """
    queryset = AccountingPeriod.objects.all()

    # Apply filters
    f = PeriodFilter(request.GET, queryset=queryset)

    # Annotate with counts
    periods = f.qs.annotate(
        journal_count=Count("journal_entries"),
        ledger_stmt_count=Count("ledger_statements"),
        account_stmt_count=Count("account_statements"),
    ).order_by("-start_date")

    context = {
        "periods": periods,
        "filter": f,
    }

    return TemplateResponse(request, "dea/period_list.html", context)


@login_required
@for_htmx(use_block="content")
def period_detail(request, pk):
    """
    Display accounting period details including:
    - Period information
    - Transaction summary
    - Statements count
    - Actions available
    """
    period = get_object_or_404(
        AccountingPeriod.objects.annotate(
            journal_count=Count("journal_entries"),
            ledger_stmt_count=Count("ledger_statements"),
            account_stmt_count=Count("account_statements"),
        ),
        pk=pk,
    )

    # Get transaction summary for this period
    journal_entries = period.journal_entries.select_related(
        "voucher", "posted_by"
    ).order_by("-posted_at")[:20]

    # Calculate period statistics
    stats = {
        "total_entries": period.journal_count,
        "ledger_statements": period.ledger_stmt_count,
        "account_statements": period.account_stmt_count,
    }

    # Get period balances (if closed)
    if period.status in [
        AccountingPeriod.PeriodStatus.CLOSED,
        AccountingPeriod.PeriodStatus.LOCKED,
    ]:
        ledger_balances = LedgerStatement.objects.filter(
            period=period, is_opening_statement=False
        ).select_related("ledgerno")[:10]

        account_balances = AccountStatement.objects.filter(
            period=period, is_opening_statement=False
        ).select_related("AccountNo", "AccountNo__contact")[:10]
    else:
        ledger_balances = None
        account_balances = None

    context = {
        "period": period,
        "journal_entries": journal_entries,
        "stats": stats,
        "ledger_balances": ledger_balances,
        "account_balances": account_balances,
        "can_close": period.status == AccountingPeriod.PeriodStatus.OPEN,
        "can_lock": period.status == AccountingPeriod.PeriodStatus.CLOSED,
        "can_unlock": period.status == AccountingPeriod.PeriodStatus.LOCKED,
    }

    return TemplateResponse(request, "dea/period_detail.html", context)


@login_required
@transaction.atomic
def period_create(request):
    """
    Create a new accounting period
    """
    if request.method == "POST":
        form = AccountingPeriodForm(request.POST)
        if form.is_valid():
            try:
                period = form.save(commit=False)
                # Set workspace if multi-tenant
                if hasattr(request.user, "workspace"):
                    period.workspace = request.user.workspace
                period.save()

                messages.success(
                    request, f"Period '{period.name}' created successfully."
                )

                if request.htmx:
                    return HttpResponse(
                        status=204,
                        headers={
                            "HX-Redirect": reverse(
                                "dea_period_detail", args=[period.pk]
                            )
                        },
                    )
                return redirect("dea_period_detail", pk=period.pk)

            except ValidationError as e:
                messages.error(request, f"Validation error: {e}")
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field}: {error}")
    else:
        # Pre-fill form with suggested dates
        last_period = AccountingPeriod.objects.order_by("-end_date").first()
        if last_period:
            initial = {
                "start_date": last_period.end_date + timedelta(days=1),
                "end_date": last_period.end_date + timedelta(days=30),
            }
        else:
            initial = {
                "start_date": date.today().replace(day=1),
                "end_date": (date.today().replace(day=1) + timedelta(days=32)).replace(
                    day=1
                )
                - timedelta(days=1),
            }
        form = AccountingPeriodForm(initial=initial)

    context = {
        "form": form,
        "title": "Create Accounting Period",
    }

    return TemplateResponse(request, "dea/period_form.html", context)


@login_required
@transaction.atomic
def period_update(request, pk):
    """
    Update an accounting period (only OPEN periods can be updated)
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    # Only allow updating OPEN periods
    if period.status != AccountingPeriod.PeriodStatus.OPEN:
        messages.error(
            request,
            f"Cannot update {period.status} period. Only OPEN periods can be modified.",
        )
        return redirect("dea_period_detail", pk=pk)

    if request.method == "POST":
        form = AccountingPeriodForm(request.POST, instance=period)
        if form.is_valid():
            try:
                period = form.save()
                messages.success(
                    request, f"Period '{period.name}' updated successfully."
                )

                if request.htmx:
                    return HttpResponse(
                        status=204,
                        headers={
                            "HX-Redirect": reverse(
                                "dea_period_detail", args=[period.pk]
                            )
                        },
                    )
                return redirect("dea_period_detail", pk=period.pk)

            except ValidationError as e:
                messages.error(request, f"Validation error: {e}")
    else:
        form = AccountingPeriodForm(instance=period)

    context = {
        "form": form,
        "period": period,
        "title": f"Update Period: {period.name}",
    }

    return TemplateResponse(request, "dea/period_form.html", context)


@login_required
@transaction.atomic
def period_close(request, pk):
    """
    Close an accounting period with validation and confirmation
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    # Check if period can be closed
    if period.status != AccountingPeriod.PeriodStatus.OPEN:
        messages.error(request, f"Cannot close {period.status} period.")
        return redirect("dea_period_detail", pk=pk)

    if request.method == "POST":
        form = PeriodCloseForm(request.POST)
        if form.is_valid():
            try:
                notes = form.cleaned_data.get("notes", "")

                # Close the period
                period.close_period(user=request.user, notes=notes)

                messages.success(
                    request,
                    f"Period '{period.name}' closed successfully. "
                    f"{period.journal_count} entries processed.",
                )

                logger.info(
                    f"Period {period.name} (ID: {period.pk}) closed by {request.user}"
                )

                if request.htmx:
                    return HttpResponse(
                        status=204,
                        headers={
                            "HX-Redirect": reverse(
                                "dea_period_detail", args=[period.pk]
                            )
                        },
                    )
                return redirect("dea_period_detail", pk=period.pk)

            except ValidationError as e:
                messages.error(request, f"Failed to close period: {e}")
                logger.error(f"Period close failed: {e}")
            except Exception as e:
                messages.error(request, f"Unexpected error: {e}")
                logger.exception(f"Period close exception: {e}")
    else:
        form = PeriodCloseForm()

    # Get summary for confirmation
    context = {
        "form": form,
        "period": period,
        "entries_count": period.journal_entries.count(),
        "ledgers_count": Ledger.objects.count(),
        "accounts_count": Account.objects.count(),
        "title": f"Close Period: {period.name}",
    }

    return TemplateResponse(request, "dea/period_close_confirm.html", context)


@login_required
@permission_required("dea.can_lock_period", raise_exception=True)
@transaction.atomic
def period_lock(request, pk):
    """
    Lock a closed period to prevent any modifications
    Requires special permission
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    try:
        period.lock_period(user=request.user)
        messages.success(request, f"Period '{period.name}' locked successfully.")
        logger.info(f"Period {period.pk} locked by {request.user}")

    except ValidationError as e:
        messages.error(request, str(e))

    return redirect("dea_period_detail", pk=pk)


@login_required
@permission_required("dea.can_unlock_period", raise_exception=True)
@transaction.atomic
def period_unlock(request, pk):
    """
    Unlock a locked period for corrections
    Requires special permission and logs audit trail
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    if request.method == "POST":
        reason = request.POST.get("reason", "")

        if not reason:
            messages.error(request, "Reason for unlocking is required.")
            return redirect("dea_period_detail", pk=pk)

        try:
            period.unlock_period(user=request.user)

            # Log unlock with reason
            logger.warning(
                f"Period {period.pk} unlocked by {request.user}. " f"Reason: {reason}"
            )

            messages.warning(
                request,
                f"Period '{period.name}' unlocked. This action has been logged.",
            )

        except ValidationError as e:
            messages.error(request, str(e))

    return redirect("dea_period_detail", pk=pk)


@login_required
@for_htmx(use_block="content")
def period_transactions(request, pk):
    """
    List all transactions for a specific period
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    # Get all journal entries for this period
    entries = (
        period.journal_entries.select_related("voucher", "posted_by")
        .prefetch_related("ltxns", "atxns")
        .order_by("-posted_at")
    )

    # Pagination
    from django.core.paginator import Paginator

    paginator = Paginator(entries, 25)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "period": period,
        "page_obj": page_obj,
        "entries": page_obj,
    }

    return TemplateResponse(request, "dea/period_transactions.html", context)


@login_required
@for_htmx(use_block="content")
def period_balances(request, pk):
    """
    Display period closing balances for all ledgers and accounts
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    if period.status == AccountingPeriod.PeriodStatus.OPEN:
        messages.info(
            request, "This period is still OPEN. Balances shown are current, not final."
        )

    # Get closing statements for ledgers
    ledger_statements = (
        LedgerStatement.objects.filter(period=period, is_opening_statement=False)
        .select_related("ledgerno", "ledgerno__AccountType")
        .order_by("ledgerno__AccountType__AccountType", "ledgerno__name")
    )

    # Get closing statements for accounts
    account_statements = (
        AccountStatement.objects.filter(period=period, is_opening_statement=False)
        .select_related("AccountNo", "AccountNo__contact", "AccountNo__AccountType_Ext")
        .order_by("AccountNo__contact__name")
    )

    # Group by account type
    ledgers_by_type = {}
    for stmt in ledger_statements:
        acc_type = stmt.ledgerno.AccountType.AccountType
        if acc_type not in ledgers_by_type:
            ledgers_by_type[acc_type] = []
        ledgers_by_type[acc_type].append(stmt)

    context = {
        "period": period,
        "ledgers_by_type": ledgers_by_type,
        "account_statements": account_statements,
    }

    return TemplateResponse(request, "dea/period_balances.html", context)


@login_required
def period_report(request, pk):
    """
    Generate comprehensive period report (PDF/Excel export)
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    # Get report format
    format_type = request.GET.get("format", "html")

    # Gather report data
    report_data = {
        "period": period,
        "generated_at": timezone.now(),
        "generated_by": request.user,
    }

    # Get all balances
    ledger_statements = LedgerStatement.objects.filter(
        period=period, is_opening_statement=False
    ).select_related("ledgerno", "ledgerno__AccountType")

    account_statements = AccountStatement.objects.filter(
        period=period, is_opening_statement=False
    ).select_related("AccountNo", "AccountNo__contact")

    report_data["ledger_statements"] = ledger_statements
    report_data["account_statements"] = account_statements

    if format_type == "pdf":
        # Generate PDF
        from django.template.loader import render_to_string
        from weasyprint import HTML

        html_string = render_to_string("dea/period_report_pdf.html", report_data)
        html = HTML(string=html_string)
        pdf = html.write_pdf()

        response = HttpResponse(pdf, content_type="application/pdf")
        response[
            "Content-Disposition"
        ] = f'attachment; filename="period_{period.name}_report.pdf"'
        return response

    elif format_type == "excel":
        # Generate Excel
        import xlsxwriter
        from io import BytesIO

        output = BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet(f"Period {period.name}")

        # Write headers and data
        row = 0
        worksheet.write(row, 0, f"Period Report: {period.name}")
        row += 2

        worksheet.write(row, 0, "Ledger")
        worksheet.write(row, 1, "Balance")
        row += 1

        for stmt in ledger_statements:
            worksheet.write(row, 0, stmt.ledgerno.name)
            worksheet.write(row, 1, float(stmt.ClosingBalance.amount))
            row += 1

        workbook.close()
        output.seek(0)

        response = HttpResponse(
            output.read(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response[
            "Content-Disposition"
        ] = f'attachment; filename="period_{period.name}_report.xlsx"'
        return response

    # Default HTML view
    return TemplateResponse(request, "dea/period_report.html", report_data)


@login_required
def period_status_ajax(request):
    """
    AJAX endpoint to get current period status
    Returns JSON with current open period info
    """
    current_period = AccountingPeriod.objects.get_current_period()

    if current_period:
        data = {
            "has_period": True,
            "period_id": current_period.pk,
            "period_name": current_period.name,
            "status": current_period.status,
            "start_date": current_period.start_date.isoformat(),
            "end_date": current_period.end_date.isoformat(),
        }
    else:
        data = {
            "has_period": False,
            "message": "No open accounting period found",
        }

    return JsonResponse(data)


@login_required
def period_delete(request, pk):
    """
    Delete a period (only if OPEN and no transactions)
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    # Check if period can be deleted
    if period.status != AccountingPeriod.PeriodStatus.OPEN:
        messages.error(
            request,
            f"Cannot delete {period.status} period. Only OPEN periods can be deleted.",
        )
        return redirect("dea_period_detail", pk=pk)

    if period.journal_entries.exists():
        messages.error(
            request,
            "Cannot delete period with transactions. "
            f"This period has {period.journal_entries.count()} journal entries.",
        )
        return redirect("dea_period_detail", pk=pk)

    if request.method == "POST":
        period_name = period.name
        period.delete()
        messages.success(request, f"Period '{period_name}' deleted successfully.")
        return redirect("dea_period_list")

    context = {
        "period": period,
    }

    return TemplateResponse(request, "dea/period_confirm_delete.html", context)
