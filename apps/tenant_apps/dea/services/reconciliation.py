from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.db.models import Q

from apps.tenant_apps.dea.models.bank import BankAccount, BankStatementLine, ReconciliationMatch
from apps.tenant_apps.dea.models.ledger import LedgerTransaction


class ReconciliationService:
    """
    Bank reconciliation service providing automatic matching, 
    manual matching, and unmatched item tracking.
    """

    @staticmethod
    def get_unmatched_bank_lines(bank_account, period):
        """Get all unmatched bank statement lines for a given period"""
        return BankStatementLine.objects.filter(
            bank_account=bank_account,
            statement_date__gte=period.start_date,
            statement_date__lte=period.end_date,
            is_reconciled=False,
        )

    @staticmethod
    def get_unmatched_gl_lines(ledger, period):
        """Get all GL transactions not matched to any bank line for a given period"""
        return LedgerTransaction.objects.filter(
            Q(ledgerno_dr=ledger) | Q(ledgerno=ledger),
            journal_entry__created__date__gte=period.start_date,
            journal_entry__created__date__lte=period.end_date,
        ).exclude(reconciliation_matches__isnull=False).distinct()

    @staticmethod
    def get_bank_statement_summary(bank_account, period):
        """Get summary statistics for bank statement"""
        lines = BankStatementLine.objects.filter(
            bank_account=bank_account,
            statement_date__gte=period.start_date,
            statement_date__lte=period.end_date,
        )
        total_lines = lines.count()
        reconciled = lines.filter(is_reconciled=True).count()
        unmatched = total_lines - reconciled
        total_amount = sum(Decimal(str(line.amount)) for line in lines)
        
        return {
            'total_lines': total_lines,
            'reconciled_lines': reconciled,
            'unmatched_lines': unmatched,
            'reconciliation_percentage': (reconciled / total_lines * 100) if total_lines > 0 else 0,
            'total_amount': total_amount,
        }

    @staticmethod
    @transaction.atomic
    def auto_match(bank_account, period, tolerance=Decimal("0.00"), matched_by=None):
        """
        Automatically match bank statement lines to GL transactions by date and amount.
        
        Returns list of created ReconciliationMatch objects.
        Matches require exact date match and amount within tolerance.
        """
        matches = []
        bank_lines = list(ReconciliationService.get_unmatched_bank_lines(bank_account, period))
        gl_lines = list(ReconciliationService.get_unmatched_gl_lines(bank_account.ledger, period))

        for bank_line in bank_lines:
            candidate = None
            for gl_line in gl_lines:
                # Match by statement date and amount (with tolerance)
                gl_date = gl_line.journal_entry.created.date() if gl_line.journal_entry else gl_line.created.date()
                if gl_date != bank_line.statement_date:
                    continue
                
                gl_amount = Decimal(str(gl_line.amount.amount))
                bank_amount = Decimal(str(bank_line.amount))
                
                if abs(gl_amount - bank_amount) <= tolerance:
                    candidate = gl_line
                    break

            if candidate is None:
                continue

            match = ReconciliationMatch.objects.create(
                bank_statement_line=bank_line,
                ledger_transaction=candidate,
                matched_by=matched_by,
                is_manual=False,
            )
            bank_line.is_reconciled = True
            bank_line.save(update_fields=["is_reconciled"])
            matches.append(match)
            # Remove matched GL line from candidates for next iteration
            gl_lines = [gl for gl in gl_lines if gl.pk != candidate.pk]

        return matches

    @staticmethod
    @transaction.atomic
    def manual_match(bank_line_id, ledger_transaction_id, matched_by=None):
        """
        Manually match a specific bank line to a GL transaction.
        
        Raises ValueError if either doesn't exist or already matched.
        """
        try:
            bank_line = BankStatementLine.objects.get(pk=bank_line_id)
            gl_transaction = LedgerTransaction.objects.get(pk=ledger_transaction_id)
        except (BankStatementLine.DoesNotExist, LedgerTransaction.DoesNotExist):
            raise ValueError("Bank line or GL transaction not found")

        if bank_line.is_reconciled:
            raise ValueError(f"Bank line {bank_line_id} is already reconciled")

        if gl_transaction.reconciliation_matches.exists():
            raise ValueError(f"GL transaction {ledger_transaction_id} is already matched")

        match = ReconciliationMatch.objects.create(
            bank_statement_line=bank_line,
            ledger_transaction=gl_transaction,
            matched_by=matched_by,
            is_manual=True,
        )
        bank_line.is_reconciled = True
        bank_line.save(update_fields=["is_reconciled"])
        return match

    @staticmethod
    @transaction.atomic
    def unmatch(bank_line_id):
        """
        Remove reconciliation match for a bank statement line.
        
        Marks bank line as unreconciled.
        """
        try:
            bank_line = BankStatementLine.objects.get(pk=bank_line_id)
        except BankStatementLine.DoesNotExist:
            raise ValueError("Bank line not found")

        # Delete all matches for this bank line
        ReconciliationMatch.objects.filter(bank_statement_line=bank_line).delete()
        
        bank_line.is_reconciled = False
        bank_line.save(update_fields=["is_reconciled"])
        return True
