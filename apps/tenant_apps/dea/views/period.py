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
from django.contrib.contenttypes.models import ContentType
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
from ..forms import AccountingPeriodForm, PeriodAdjustmentForm, PeriodCloseForm
from ..models import (
    Account,
    AccountingPeriod,
    AccountStatement,
    JournalEntry,
    JournalEntryLineItem,
    JournalEntryVoucher,
    Ledger,
    LedgerStatement,
    Voucher,
    VoucherStatus,
    VoucherType,
)
from ..tables import PeriodTable
from ..utils.currency import Balance

logger = logging.getLogger(__name__)

PRE_CLOSE_ADJUSTMENT_TYPES = [
    ("ACCRUAL", "Accruals"),
    ("PREPAID_EXPENSE", "Prepaid expenses"),
    ("DEPRECIATION", "Depreciation"),
    ("INTEREST_ACCRUAL", "Interest accrual"),
    ("CUSTOM", "Custom adjustments"),
]


def _map_adjustment_entry_type(adjustment_type):
    if adjustment_type in {"ACCRUAL", "INTEREST_ACCRUAL"}:
        return "ACCRUAL"
    if adjustment_type in {"PREPAID_EXPENSE", "DEPRECIATION"}:
        return "ADJUSTMENT"
    return "OTHER"


def _build_pre_close_summary(period):
    reference = f"PERIOD:{period.pk}"
    adjustment_docs = JournalEntryVoucher.objects.filter(reference=reference).order_by(
        "-je_date", "-created_at"
    )
    adjustment_counts = {}
    checklist = []

    for key, label in PRE_CLOSE_ADJUSTMENT_TYPES:
        count = adjustment_docs.filter(memo=f"PRE_CLOSE:{key}").count()
        adjustment_counts[key] = count
        checklist.append(
            {
                "label": label,
                "count": count,
                "ready": count > 0,
                "status_text": "Recorded" if count else "Review needed",
            }
        )

    draft_vouchers = (
        Voucher.objects.filter(
            journal_entries__period=period,
            status=VoucherStatus.DRAFT,
        )
        .select_related("voucher_type")
        .distinct()
    )
    draft_vouchers_count = draft_vouchers.count()
    checklist.append(
        {
            "label": "Draft vouchers resolved",
            "count": draft_vouchers_count,
            "ready": draft_vouchers_count == 0,
            "status_text": (
                "Ready"
                if draft_vouchers_count == 0
                else f"{draft_vouchers_count} draft voucher(s) remain"
            ),
        }
    )

    return {
        "adjustments": adjustment_docs[:20],
        "adjustment_counts": adjustment_counts,
        "total_adjustments": adjustment_docs.count(),
        "draft_vouchers": draft_vouchers[:10],
        "draft_vouchers_count": draft_vouchers_count,
        "checklist": checklist,
    }


def _create_period_adjustment(period, user, cleaned_data):
    adjustment_type = cleaned_data["adjustment_type"]
    adjustment_label = dict(PRE_CLOSE_ADJUSTMENT_TYPES).get(
        adjustment_type, adjustment_type.replace("_", " ").title()
    )
    debit_ledger = cleaned_data["debit_ledger"]
    credit_ledger = cleaned_data["credit_ledger"]
    amount = cleaned_data["amount"]
    effective_date = cleaned_data["effective_date"]
    description = cleaned_data["description"].strip()
    if cleaned_data.get("auto_reverse_next_period"):
        description = f"{description} [Flagged for next-period reversal review]"

    adjustment_doc = JournalEntryVoucher.objects.create(
        je_date=effective_date,
        entry_type=_map_adjustment_entry_type(adjustment_type),
        description=f"[{adjustment_label}] {description}",
        memo=f"PRE_CLOSE:{adjustment_type}",
        reference=f"PERIOD:{period.pk}",
        total_debit=amount,
        total_credit=amount,
        reviewed_by=user,
        reviewed_at=timezone.now(),
        created_by=user,
        updated_by=user,
        auto_post_to_accounting=False,
    )
    JournalEntryLineItem.objects.bulk_create(
        [
            JournalEntryLineItem(
                journal_entry=adjustment_doc,
                line_number=1,
                ledger_id=debit_ledger.pk,
                ledger_name=debit_ledger.name or f"Ledger {debit_ledger.pk}",
                side="DR",
                amount=amount,
                description=description,
            ),
            JournalEntryLineItem(
                journal_entry=adjustment_doc,
                line_number=2,
                ledger_id=credit_ledger.pk,
                ledger_name=credit_ledger.name or f"Ledger {credit_ledger.pk}",
                side="CR",
                amount=amount,
                description=description,
            ),
        ]
    )

    voucher_type, _ = VoucherType.objects.get_or_create(
        name="PERIOD_ADJUSTMENT",
        defaults={"description": "System-posted pre-close adjustment entry"},
    )
    voucher = Voucher.objects.create(
        voucher_no=f"PERIOD-ADJ-{period.pk}-{adjustment_doc.pk}",
        voucher_type=voucher_type,
        voucher_date=effective_date,
        status=VoucherStatus.POSTED,
        created_by=user,
        updated_by=user,
        doc_content_type=ContentType.objects.get_for_model(adjustment_doc),
        doc_object_id=adjustment_doc.pk,
        fingerprint=f"period-adjustment:{period.pk}:{adjustment_doc.pk}:{adjustment_type}",
        last_posted_at=timezone.now(),
        narration=adjustment_doc.description,
    )
    journal_entry = JournalEntry.objects.create(
        voucher=voucher,
        period=period,
        posted_by=user,
        desc=adjustment_doc.description,
    )
    journal_entry.transact(
        [
            {
                "ledgerno": credit_ledger.name,
                "ledgerno_dr": debit_ledger.name,
                "amount": amount,
            }
        ],
        [],
    )
    return adjustment_doc, journal_entry


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
def period_adjustments(request, pk):
    """Review and post pre-close adjustment entries for a period."""
    period = get_object_or_404(AccountingPeriod, pk=pk)
    pre_close_summary = _build_pre_close_summary(period)

    if request.method == "POST":
        if period.status != AccountingPeriod.PeriodStatus.OPEN:
            messages.error(
                request,
                f"Adjustments can only be posted while period '{period.name}' is OPEN.",
            )
            return redirect("dea_period_adjustments", pk=pk)

        form = PeriodAdjustmentForm(request.POST, period=period)
        if form.is_valid():
            try:
                adjustment_doc, journal_entry = _create_period_adjustment(
                    period=period,
                    user=request.user,
                    cleaned_data=form.cleaned_data,
                )
                messages.success(
                    request,
                    f"Posted {adjustment_doc.get_entry_type_display().lower()} entry "
                    f"{adjustment_doc.je_number} for period '{period.name}'.",
                )
                logger.info(
                    "Period adjustment %s posted for period %s by %s",
                    adjustment_doc.je_number,
                    period.pk,
                    request.user,
                )
                return redirect("dea_period_adjustments", pk=pk)
            except ValidationError as e:
                messages.error(request, f"Failed to post adjustment: {e}")
            except Exception as e:
                messages.error(request, f"Unexpected adjustment error: {e}")
                logger.exception("Period adjustment exception: %s", e)
    else:
        form = PeriodAdjustmentForm(period=period)

    context = {
        "period": period,
        "form": form,
        "pre_close_summary": pre_close_summary,
        "can_post_adjustments": period.status == AccountingPeriod.PeriodStatus.OPEN,
        "title": f"Period Adjustments: {period.name}",
    }
    return TemplateResponse(request, "dea/period_adjustments.html", context)


@login_required
@transaction.atomic
def period_close(request, pk):
    """
    Close an accounting period with validation and confirmation
    """
    period = get_object_or_404(AccountingPeriod, pk=pk)

    # Check if period can be closed
    if period.status != AccountingPeriod.PeriodStatus.OPEN:
        if period.status == AccountingPeriod.PeriodStatus.CLOSED:
            messages.info(
                request,
                f"Period '{period.name}' is already closed. Closing can only be done once.",
            )
        elif period.status == AccountingPeriod.PeriodStatus.LOCKED:
            messages.warning(
                request,
                f"Period '{period.name}' is locked and cannot be closed again.",
            )
        else:
            messages.error(request, f"Cannot close {period.status} period.")
        return redirect("dea_period_detail", pk=pk)

    pre_close_summary = _build_pre_close_summary(period)

    if request.method == "POST":
        form = PeriodCloseForm(
            request.POST,
            draft_vouchers_count=pre_close_summary["draft_vouchers_count"],
        )
        if form.is_valid():
            try:
                notes = form.cleaned_data.get("notes", "")

                # 1.8 — Interest accrual catch-up before close.
                # Run accrual for all unreleased loans up to period.end_date so
                # that P&L is complete before the closing entries are generated.
                # Failures are surfaced as warnings and do NOT block the close.
                try:
                    from apps.tenant_apps.girvi.models.loan_refactored import GivenLoan
                    from apps.tenant_apps.girvi.service_modules.accrual import (
                        InterestAccrualCommand,
                        InterestAccrualService,
                    )

                    active_loans = GivenLoan.objects.filter(release__isnull=True)
                    accrual_failures = []
                    for loan in active_loans:
                        try:
                            result = InterestAccrualService.execute(
                                InterestAccrualCommand(
                                    loan=loan,
                                    as_of_date=period.end_date,
                                    trigger_source="PERIOD_CLOSE",
                                    created_by=request.user,
                                    notes=f"Period close catch-up for {period.name}",
                                    post_to_accounting=True,
                                )
                            )
                            if not result.success:
                                accrual_failures.append(
                                    f"Loan {loan.loan_id}: {result.message}"
                                )
                        except Exception:
                            logger.exception(
                                "Accrual catch-up failed for loan %s during period close %s",
                                loan.pk,
                                period.pk,
                            )
                            accrual_failures.append(
                                f"Loan {getattr(loan, 'loan_id', loan.pk)}: accrual catch-up error"
                            )
                    for warning_msg in accrual_failures:
                        messages.warning(request, f"Accrual catch-up: {warning_msg}")
                except ImportError:
                    logger.debug("Girvi app not installed; skipping accrual catch-up on period close.")

                # Close the period
                period.close_period(user=request.user, notes=notes)
                entries_processed = period.journal_entries.count()

                messages.success(
                    request,
                    f"Period '{period.name}' closed successfully. "
                    f"{entries_processed} entries processed.",
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
        form = PeriodCloseForm(
            draft_vouchers_count=pre_close_summary["draft_vouchers_count"]
        )

    # Get summary for confirmation
    context = {
        "form": form,
        "period": period,
        "entries_count": period.journal_entries.count(),
        "ledgers_count": Ledger.objects.count(),
        "accounts_count": Account.objects.count(),
        "pre_close_summary": pre_close_summary,
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
        .order_by("AccountNo__contact__firstname", "AccountNo__contact__lastname")
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
