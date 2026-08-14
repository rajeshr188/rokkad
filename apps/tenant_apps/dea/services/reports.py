"""
Financial Reports Service

Generates 6 standard financial reports:
- Trial Balance
- Profit & Loss (Income Statement)
- Balance Sheet
- Cash Flow Statement (indirect method)
- AR Aging
- AP Aging
"""
from datetime import date
from decimal import Decimal
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field

from django.db.models import Sum
from moneyed import Money

from django.db import models
from ..models import (
    Ledger, LedgerTransaction, AccountType, AccountingPeriod,
    SalesInvoiceVoucher, PurchaseInvoiceVoucher
)


@dataclass
class ReportLine:
    """Represents a single line in a financial report."""
    account_name: str
    ledger_code: str = ""
    balance: Money = field(default_factory=lambda: Money(0, 'INR'))
    prior_balance: Money = field(default_factory=lambda: Money(0, 'INR'))
    level: int = 0  # For hierarchical reports
    is_subtotal: bool = False
    account_id: Optional[int] = None


@dataclass
class ReportData:
    """Container for report data and metadata."""
    title: str
    period: Optional['AccountingPeriod'] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    lines: List[ReportLine] = field(default_factory=list)
    totals: Dict[str, Money] = field(default_factory=dict)


class ReportsService:
    """Service for generating financial reports."""

    def __init__(self, tenant_schema: Optional[str] = None):
        self.tenant_schema = tenant_schema

    def trial_balance(
        self,
        period: AccountingPeriod,
        include_prior: bool = False
    ) -> ReportData:
        """
        Generate trial balance report.
        Shows debit and credit balances by account for the period.
        """
        report = ReportData(
            title="Trial Balance",
            period=period,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        grand_debit = Money(0, 'INR')
        grand_credit = Money(0, 'INR')

        # Group ledgers by AccountType hierarchy
        for account_type in AccountType.objects.all():
            type_lines = []
            total_debit = Money(0, 'INR')
            total_credit = Money(0, 'INR')

            ledgers = Ledger.objects.filter(
                AccountType=account_type,
                parent__isnull=True  # Root level only for grouping
            ).select_related('AccountType')

            for ledger in ledgers:
                debit_total, credit_total = self._get_ledger_debit_credit_for_period(
                    ledger,
                    period,
                )
                net_debit = debit_total - credit_total
                balance = net_debit
                prior_balance = Money(0, 'INR')
                if include_prior:
                    prior_period = self._get_prior_period(period)
                    if prior_period:
                        prior_balance = self._get_ledger_balance_for_period(ledger, prior_period)

                if debit_total.amount or credit_total.amount:
                    # Determine debit/credit side based on account type
                    if account_type.AccountType in ['Asset', 'Expense', 'Gain']:
                        debit_side = net_debit if net_debit.amount >= 0 else Money(0, 'INR')
                        credit_side = -net_debit if net_debit.amount < 0 else Money(0, 'INR')
                    else:
                        net_credit = credit_total - debit_total
                        credit_side = net_credit if net_credit.amount >= 0 else Money(0, 'INR')
                        debit_side = -net_credit if net_credit.amount < 0 else Money(0, 'INR')

                    total_debit += debit_side
                    total_credit += credit_side
                    grand_debit += debit_side
                    grand_credit += credit_side

                    type_lines.append(ReportLine(
                        account_name=ledger.name or ledger.code,
                        ledger_code=ledger.code,
                        balance=balance,
                        prior_balance=prior_balance,
                        level=1,
                        account_id=ledger.id,
                    ))

            # Add account type subtotal if there are lines
            if type_lines:
                report.lines.append(ReportLine(
                    account_name=f"{account_type.AccountType} (Subtotal)",
                    balance=total_debit if total_debit.amount > 0 else total_credit,
                    level=0,
                    is_subtotal=True,
                ))
                report.lines.extend(type_lines)

        report.totals = {
            'debit': grand_debit,
            'credit': grand_credit,
            'in_balance': grand_debit == grand_credit,
        }

        return report

    def income_statement(self, period: AccountingPeriod) -> ReportData:
        """
        Generate Profit & Loss (Income Statement) report.
        Structure: Revenue - COGS - OpEx - Finance = Net Profit
        """
        report = ReportData(
            title="Profit & Loss Statement",
            period=period,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        # Revenue
        revenue_lines, revenue_total = self._get_ledger_lines_by_flag(
            'is_operating_revenue', period
        )
        report.lines.append(ReportLine(
            account_name="Revenue",
            is_subtotal=True,
            level=0,
            balance=revenue_total,
        ))
        report.lines.extend(revenue_lines)

        # Other Income
        other_income_lines, other_income_total = self._get_ledger_lines_by_account_type(
            'Income', period, exclude_flags=['is_operating_revenue']
        )
        report.lines.append(ReportLine(
            account_name="Other Income",
            is_subtotal=True,
            level=0,
            balance=other_income_total,
        ))
        report.lines.extend(other_income_lines)

        gross_revenue = revenue_total + other_income_total
        report.lines.append(ReportLine(
            account_name="Gross Revenue",
            is_subtotal=True,
            level=0,
            balance=gross_revenue,
        ))

        # COGS
        cogs_lines, cogs_total = self._get_ledger_lines_by_flag(
            'is_direct_expense', period
        )
        report.lines.append(ReportLine(
            account_name="Cost of Goods Sold",
            is_subtotal=True,
            level=0,
            balance=cogs_total,
        ))
        report.lines.extend(cogs_lines)

        gross_profit = gross_revenue - cogs_total
        report.lines.append(ReportLine(
            account_name="Gross Profit",
            is_subtotal=True,
            level=0,
            balance=gross_profit,
        ))

        # Operating Expenses
        opex_lines, opex_total = self._get_ledger_lines_by_flag(
            'is_operating_expense', period
        )
        report.lines.append(ReportLine(
            account_name="Operating Expenses",
            is_subtotal=True,
            level=0,
            balance=opex_total,
        ))
        report.lines.extend(opex_lines)

        operating_profit = gross_profit - opex_total
        report.lines.append(ReportLine(
            account_name="Operating Profit",
            is_subtotal=True,
            level=0,
            balance=operating_profit,
        ))

        # Finance Costs (interest expense)
        finance_lines, finance_total = self._get_ledger_lines_by_name_pattern(
            'interest', period, expense_side=True
        )
        report.lines.append(ReportLine(
            account_name="Finance Costs",
            is_subtotal=True,
            level=0,
            balance=finance_total,
        ))
        report.lines.extend(finance_lines)

        net_profit_before_tax = operating_profit - finance_total
        report.lines.append(ReportLine(
            account_name="Net Profit Before Tax",
            is_subtotal=True,
            level=0,
            balance=net_profit_before_tax,
        ))

        # Tax Provision
        tax_lines, tax_total = self._get_ledger_lines_by_name_pattern(
            'tax', period, expense_side=True
        )
        report.lines.append(ReportLine(
            account_name="Tax Provision",
            is_subtotal=True,
            level=0,
            balance=tax_total,
        ))
        report.lines.extend(tax_lines)

        net_profit = net_profit_before_tax - tax_total
        report.lines.append(ReportLine(
            account_name="Net Profit After Tax",
            is_subtotal=True,
            level=0,
            balance=net_profit,
        ))

        report.totals = {
            'revenue': gross_revenue,
            'cogs': cogs_total,
            'gross_profit': gross_profit,
            'opex': opex_total,
            'operating_profit': operating_profit,
            'finance_costs': finance_total,
            'tax': tax_total,
            'net_profit': net_profit,
        }

        return report

    def balance_sheet(self, period: AccountingPeriod) -> ReportData:
        """
        Generate Balance Sheet report.
        Structure: Assets = Liabilities + Equity
        """
        report = ReportData(
            title="Balance Sheet",
            period=period,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        # Assets
        current_assets_lines, current_assets = self._get_asset_lines(period, current_only=True)
        report.lines.append(ReportLine(
            account_name="Current Assets",
            is_subtotal=True,
            level=0,
            balance=current_assets,
        ))
        report.lines.extend(current_assets_lines)

        fixed_assets_lines, fixed_assets = self._get_asset_lines(period, current_only=False)
        report.lines.append(ReportLine(
            account_name="Fixed Assets",
            is_subtotal=True,
            level=0,
            balance=fixed_assets,
        ))
        report.lines.extend(fixed_assets_lines)

        total_assets = current_assets + fixed_assets
        report.lines.append(ReportLine(
            account_name="Total Assets",
            is_subtotal=True,
            level=0,
            balance=total_assets,
        ))

        # Liabilities
        current_liab_lines, current_liab = self._get_liability_lines(period, current_only=True)
        report.lines.append(ReportLine(
            account_name="Current Liabilities",
            is_subtotal=True,
            level=0,
            balance=current_liab,
        ))
        report.lines.extend(current_liab_lines)

        long_term_liab_lines, long_term_liab = self._get_liability_lines(period, current_only=False)
        report.lines.append(ReportLine(
            account_name="Long-term Liabilities",
            is_subtotal=True,
            level=0,
            balance=long_term_liab,
        ))
        report.lines.extend(long_term_liab_lines)

        total_liab = current_liab + long_term_liab
        report.lines.append(ReportLine(
            account_name="Total Liabilities",
            is_subtotal=True,
            level=0,
            balance=total_liab,
        ))

        # Equity
        equity_lines, equity_total = self._get_equity_lines(period)
        report.lines.append(ReportLine(
            account_name="Equity",
            is_subtotal=True,
            level=0,
            balance=equity_total,
        ))
        report.lines.extend(equity_lines)

        total_equity = equity_total
        report.lines.append(ReportLine(
            account_name="Total Equity",
            is_subtotal=True,
            level=0,
            balance=total_equity,
        ))

        total_liab_equity = total_liab + total_equity
        report.lines.append(ReportLine(
            account_name="Total Liabilities + Equity",
            is_subtotal=True,
            level=0,
            balance=total_liab_equity,
        ))

        report.totals = {
            'assets': total_assets,
            'liabilities': total_liab,
            'equity': total_equity,
            'liab_equity': total_liab_equity,
            'in_balance': total_assets == total_liab_equity,
        }

        return report

    def cash_flow_statement(self, period: AccountingPeriod) -> ReportData:
        """
        Generate Cash Flow Statement using indirect method.
        Start with Net Profit, adjust for non-cash items.
        """
        report = ReportData(
            title="Cash Flow Statement",
            period=period,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        # Start with Net Profit from P&L
        pl_report = self.income_statement(period)
        net_profit = pl_report.totals.get('net_profit', Money(0, 'INR'))
        report.lines.append(ReportLine(
            account_name="Net Profit",
            is_subtotal=True,
            level=0,
            balance=net_profit,
        ))

        # Adjustments: Depreciation (add back non-cash expense)
        depr_lines, depr_total = self._get_ledger_lines_by_name_pattern(
            'depreciation', period, expense_side=True
        )
        report.lines.append(ReportLine(
            account_name="Add: Depreciation",
            is_subtotal=True,
            level=0,
            balance=depr_total,
        ))
        report.lines.extend(depr_lines)

        # Adjustments: Interest accrual (if any)
        int_lines, int_total = self._get_ledger_lines_by_name_pattern(
            'accrual', period, expense_side=True
        )
        report.lines.append(ReportLine(
            account_name="Add: Accruals",
            is_subtotal=True,
            level=0,
            balance=int_total,
        ))
        report.lines.extend(int_lines)

        cash_from_ops = net_profit + depr_total + int_total
        report.lines.append(ReportLine(
            account_name="Cash from Operations",
            is_subtotal=True,
            level=0,
            balance=cash_from_ops,
        ))

        # Investing: Fixed asset purchases (simplified)
        fixed_asset_lines, fixed_asset_total = self._get_ledger_lines_by_name_pattern(
            'fixed asset', period, expense_side=False
        )
        report.lines.append(ReportLine(
            account_name="Cash used in Investing",
            is_subtotal=True,
            level=0,
            balance=-fixed_asset_total,
        ))
        report.lines.extend(fixed_asset_lines)

        # Financing: Simplified (loan proceeds/repayments)
        financing_lines, financing_total = self._get_ledger_lines_by_name_pattern(
            'loan', period, expense_side=False
        )
        report.lines.append(ReportLine(
            account_name="Cash from Financing",
            is_subtotal=True,
            level=0,
            balance=financing_total,
        ))
        report.lines.extend(financing_lines)

        net_cash_flow = cash_from_ops - fixed_asset_total + financing_total
        report.lines.append(ReportLine(
            account_name="Net Cash Flow",
            is_subtotal=True,
            level=0,
            balance=net_cash_flow,
        ))

        report.totals = {
            'net_profit': net_profit,
            'depreciation': depr_total,
            'cash_from_ops': cash_from_ops,
            'cash_used_investing': fixed_asset_total,
            'cash_from_financing': financing_total,
            'net_cash_flow': net_cash_flow,
        }

        return report

    def ar_aging(self, period: AccountingPeriod) -> ReportData:
        """
        Generate AR Aging report showing outstanding invoices by age bucket.
        Buckets: 0-30, 31-60, 61-90, 90+
        """
        report = ReportData(
            title="Accounts Receivable Aging",
            period=period,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        today = date.today()
        invoices = SalesInvoiceVoucher.objects.filter(
            invoice_date__lte=period.end_date,
            received_amount__lt=models.F('total_amount')
        )

        buckets = {
            '0-30': Money(0, 'INR'),
            '31-60': Money(0, 'INR'),
            '61-90': Money(0, 'INR'),
            '90+': Money(0, 'INR'),
        }

        for invoice in invoices:
            days_old = (today - invoice.invoice_date).days
            amount = invoice.total_amount - invoice.received_amount

            report.lines.append(ReportLine(
                account_name=f"Invoice {invoice.invoice_number} - {invoice.customer}",
                balance=amount,
                level=1,
                account_id=invoice.id,
            ))

            if days_old <= 30:
                buckets['0-30'] += amount
            elif days_old <= 60:
                buckets['31-60'] += amount
            elif days_old <= 90:
                buckets['61-90'] += amount
            else:
                buckets['90+'] += amount

        report.lines.insert(0, ReportLine(
            account_name="0-30 Days",
            is_subtotal=True,
            level=0,
            balance=buckets['0-30'],
        ))
        report.lines.insert(1, ReportLine(
            account_name="31-60 Days",
            is_subtotal=True,
            level=0,
            balance=buckets['31-60'],
        ))
        report.lines.insert(2, ReportLine(
            account_name="61-90 Days",
            is_subtotal=True,
            level=0,
            balance=buckets['61-90'],
        ))
        report.lines.insert(3, ReportLine(
            account_name="90+ Days",
            is_subtotal=True,
            level=0,
            balance=buckets['90+'],
        ))

        total_ar = Money(0, 'INR')
        for bucket_amount in buckets.values():
            total_ar += bucket_amount
        report.totals = buckets
        report.totals['total'] = total_ar

        return report

    def ap_aging(self, period: AccountingPeriod) -> ReportData:
        """
        Generate AP Aging report showing outstanding bills by age bucket.
        Mirror of AR Aging.
        """
        report = ReportData(
            title="Accounts Payable Aging",
            period=period,
            start_date=period.start_date,
            end_date=period.end_date,
        )

        today = date.today()
        bills = PurchaseInvoiceVoucher.objects.filter(
            invoice_date__lte=period.end_date,
            paid_amount__lt=models.F('total_amount')
        )

        buckets = {
            '0-30': Money(0, 'INR'),
            '31-60': Money(0, 'INR'),
            '61-90': Money(0, 'INR'),
            '90+': Money(0, 'INR'),
        }

        for bill in bills:
            days_old = (today - bill.invoice_date).days
            amount = bill.total_amount - bill.paid_amount

            report.lines.append(ReportLine(
                account_name=f"Bill {bill.internal_number or bill.invoice_number} - {bill.vendor}",
                balance=amount,
                level=1,
                account_id=bill.id,
            ))

            if days_old <= 30:
                buckets['0-30'] += amount
            elif days_old <= 60:
                buckets['31-60'] += amount
            elif days_old <= 90:
                buckets['61-90'] += amount
            else:
                buckets['90+'] += amount

        report.lines.insert(0, ReportLine(
            account_name="0-30 Days",
            is_subtotal=True,
            level=0,
            balance=buckets['0-30'],
        ))
        report.lines.insert(1, ReportLine(
            account_name="31-60 Days",
            is_subtotal=True,
            level=0,
            balance=buckets['31-60'],
        ))
        report.lines.insert(2, ReportLine(
            account_name="61-90 Days",
            is_subtotal=True,
            level=0,
            balance=buckets['61-90'],
        ))
        report.lines.insert(3, ReportLine(
            account_name="90+ Days",
            is_subtotal=True,
            level=0,
            balance=buckets['90+'],
        ))

        total_ap = Money(0, 'INR')
        for bucket_amount in buckets.values():
            total_ap += bucket_amount
        report.totals = buckets
        report.totals['total'] = total_ap

        return report

    # -------- Helper Methods --------

    def _get_ledger_balance_for_period(
        self, ledger: Ledger, period: AccountingPeriod
    ) -> Money:
        """Get the balance of a ledger for a specific period."""
        credit_total = LedgerTransaction.objects.filter(
            ledgerno=ledger,
            journal_entry__period=period,
        ).aggregate(total=Sum('amount_base'))['total'] or Decimal('0.00')
        debit_total = LedgerTransaction.objects.filter(
            ledgerno_dr=ledger,
            journal_entry__period=period,
        ).aggregate(total=Sum('amount_base'))['total'] or Decimal('0.00')

        amount = credit_total - debit_total
        return Money(amount, 'INR')

    def _get_ledger_debit_credit_for_period(
        self, ledger: Ledger, period: AccountingPeriod
    ) -> Tuple[Money, Money]:
        """Get base-currency debit and credit totals for a ledger in a period."""
        credit_total = LedgerTransaction.objects.filter(
            ledgerno=ledger,
            journal_entry__period=period,
        ).aggregate(total=Sum('amount_base'))['total'] or Decimal('0.00')
        debit_total = LedgerTransaction.objects.filter(
            ledgerno_dr=ledger,
            journal_entry__period=period,
        ).aggregate(total=Sum('amount_base'))['total'] or Decimal('0.00')
        return Money(debit_total, 'INR'), Money(credit_total, 'INR')

    def _get_prior_period(self, period: AccountingPeriod) -> Optional[AccountingPeriod]:
        """Get the prior accounting period."""
        try:
            return period.get_previous_period()
        except Exception:
            return None

    def _get_ledger_lines_by_flag(
        self, flag_name: str, period: AccountingPeriod
    ) -> Tuple[List[ReportLine], Money]:
        """Get ledger lines filtered by a boolean flag."""
        lines = []
        total = Money(0, 'INR')

        filter_kwargs = {flag_name: True}
        ledgers = Ledger.objects.filter(**filter_kwargs)

        for ledger in ledgers:
            balance = self._get_ledger_balance_for_period(ledger, period)
            if balance != 0:
                lines.append(ReportLine(
                    account_name=ledger.name or ledger.code,
                    ledger_code=ledger.code,
                    balance=balance,
                    level=1,
                    account_id=ledger.id,
                ))
                total += balance

        return lines, total

    def _get_ledger_lines_by_account_type(
        self, account_type_name: str, period: AccountingPeriod, exclude_flags=None
    ) -> Tuple[List[ReportLine], Money]:
        """Get ledger lines filtered by account type."""
        lines = []
        total = Money(0, 'INR')

        if exclude_flags is None:
            exclude_flags = []

        query = Ledger.objects.filter(AccountType__AccountType=account_type_name)
        for flag in exclude_flags:
            query = query.filter(**{flag: False})

        for ledger in query:
            balance = self._get_ledger_balance_for_period(ledger, period)
            if balance != 0:
                lines.append(ReportLine(
                    account_name=ledger.name or ledger.code,
                    ledger_code=ledger.code,
                    balance=balance,
                    level=1,
                    account_id=ledger.id,
                ))
                total += balance

        return lines, total

    def _get_ledger_lines_by_name_pattern(
        self, pattern: str, period: AccountingPeriod, expense_side: bool = False
    ) -> Tuple[List[ReportLine], Money]:
        """Get ledger lines matching a name pattern."""
        lines = []
        total = Money(0, 'INR')

        ledgers = Ledger.objects.filter(name__icontains=pattern)

        for ledger in ledgers:
            balance = self._get_ledger_balance_for_period(ledger, period)
            if balance != 0:
                lines.append(ReportLine(
                    account_name=ledger.name or ledger.code,
                    ledger_code=ledger.code,
                    balance=balance,
                    level=1,
                    account_id=ledger.id,
                ))
                total += balance if not expense_side else -balance

        return lines, total

    def _get_asset_lines(
        self, period: AccountingPeriod, current_only: bool = True
    ) -> Tuple[List[ReportLine], Money]:
        """Get asset ledger lines."""
        lines = []
        total = Money(0, 'INR')

        filter_kwargs = {'is_current_asset': current_only} if current_only else {'is_current_asset': False}
        ledgers = Ledger.objects.filter(
            AccountType__AccountType='Asset',
            **filter_kwargs
        )

        for ledger in ledgers:
            balance = self._get_ledger_balance_for_period(ledger, period)
            if balance != 0:
                lines.append(ReportLine(
                    account_name=ledger.name or ledger.code,
                    ledger_code=ledger.code,
                    balance=balance,
                    level=1,
                    account_id=ledger.id,
                ))
                total += balance

        return lines, total

    def _get_liability_lines(
        self, period: AccountingPeriod, current_only: bool = True
    ) -> Tuple[List[ReportLine], Money]:
        """Get liability ledger lines."""
        lines = []
        total = Money(0, 'INR')

        filter_kwargs = {'is_current_liability': current_only} if current_only else {'is_current_liability': False}
        ledgers = Ledger.objects.filter(
            AccountType__AccountType='Liability',
            **filter_kwargs
        )

        for ledger in ledgers:
            balance = self._get_ledger_balance_for_period(ledger, period)
            if balance != 0:
                lines.append(ReportLine(
                    account_name=ledger.name or ledger.code,
                    ledger_code=ledger.code,
                    balance=balance,
                    level=1,
                    account_id=ledger.id,
                ))
                total += balance

        return lines, total

    def _get_equity_lines(self, period: AccountingPeriod) -> Tuple[List[ReportLine], Money]:
        """Get equity ledger lines."""
        lines = []
        total = Money(0, 'INR')

        ledgers = Ledger.objects.filter(AccountType__AccountType='Equity')

        for ledger in ledgers:
            balance = self._get_ledger_balance_for_period(ledger, period)
            if balance != 0:
                lines.append(ReportLine(
                    account_name=ledger.name or ledger.code,
                    ledger_code=ledger.code,
                    balance=balance,
                    level=1,
                    account_id=ledger.id,
                ))
                total += balance

        return lines, total
