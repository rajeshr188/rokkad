"""
Financial Reports Views

Provides views for rendering all 6 financial reports:
- Trial Balance
- Profit & Loss
- Balance Sheet
- Cash Flow Statement
- AR Aging
- AP Aging
"""
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
import csv

from ..models import AccountingPeriod
from ..services.reports import ReportsService


class BaseReportView(LoginRequiredMixin, TemplateView):
    """Base view for financial reports."""
    report_service = None

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        period_id = self.kwargs.get('period_id')
        if period_id:
            period = get_object_or_404(AccountingPeriod, pk=period_id)
        else:
            # Default to latest closed period
            period = AccountingPeriod.objects.filter(
                status='CLOSED'
            ).order_by('-end_date').first()
        
        if not period:
            context['error'] = "No accounting period found"
            return context
        
        service = ReportsService()
        context['period'] = period
        context['report_data'] = getattr(self, 'get_report_data')(service, period)
        
        return context

    def get_report_data(self, service, period):
        """Override this method in subclasses."""
        raise NotImplementedError


class TrialBalanceView(BaseReportView):
    """Trial Balance report view."""
    template_name = 'dea/reports/trial_balance.html'
    
    def get_report_data(self, service, period):
        return service.trial_balance(period, include_prior=True)


class IncomeStatementView(BaseReportView):
    """Profit & Loss (Income Statement) report view."""
    template_name = 'dea/reports/income_statement.html'
    
    def get_report_data(self, service, period):
        return service.income_statement(period)


class BalanceSheetView(BaseReportView):
    """Balance Sheet report view."""
    template_name = 'dea/reports/balance_sheet.html'
    
    def get_report_data(self, service, period):
        return service.balance_sheet(period)


class CashFlowView(BaseReportView):
    """Cash Flow Statement report view."""
    template_name = 'dea/reports/cash_flow.html'
    
    def get_report_data(self, service, period):
        return service.cash_flow_statement(period)


class ARAgingView(BaseReportView):
    """Accounts Receivable Aging report view."""
    template_name = 'dea/reports/ar_aging_period.html'
    
    def get_report_data(self, service, period):
        return service.ar_aging(period)


class APAgingView(BaseReportView):
    """Accounts Payable Aging report view."""
    template_name = 'dea/reports/ap_aging_period.html'
    
    def get_report_data(self, service, period):
        return service.ap_aging(period)


@login_required
def trial_balance_csv(request, period_id):
    """Export Trial Balance as CSV."""
    period = get_object_or_404(AccountingPeriod, pk=period_id)
    service = ReportsService()
    report = service.trial_balance(period)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="trial_balance_{period.name}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Account', 'Code', 'Balance', 'Prior Balance'])
    
    for line in report.lines:
        if not line.is_subtotal:
            writer.writerow([
                line.account_name,
                line.ledger_code,
                line.balance.amount,
                line.prior_balance.amount,
            ])
    
    return response


@login_required
def income_statement_csv(request, period_id):
    """Export Income Statement as CSV."""
    period = get_object_or_404(AccountingPeriod, pk=period_id)
    service = ReportsService()
    report = service.income_statement(period)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="income_statement_{period.name}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Item', 'Amount'])
    
    for line in report.lines:
        writer.writerow([
            line.account_name,
            line.balance.amount,
        ])
    
    return response


@login_required
def balance_sheet_csv(request, period_id):
    """Export Balance Sheet as CSV."""
    period = get_object_or_404(AccountingPeriod, pk=period_id)
    service = ReportsService()
    report = service.balance_sheet(period)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="balance_sheet_{period.name}.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Account', 'Amount'])
    
    for line in report.lines:
        writer.writerow([
            line.account_name,
            line.balance.amount,
        ])
    
    return response
