from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.tenant_apps.dea.models.bank import BankAccount, BankStatementLine, ReconciliationMatch
from apps.tenant_apps.dea.models.ledger import LedgerTransaction


class ReconciliationService:
    @staticmethod
    def get_unmatched_bank_lines(bank_account, period):
        return BankStatementLine.objects.filter(
            bank_account=bank_account,
            statement_date__gte=period.start_date,
            statement_date__lte=period.end_date,
            is_reconciled=False,
        )

    @staticmethod
    def get_unmatched_gl_lines(ledger, period):
        return LedgerTransaction.objects.filter(
            ledgerno=ledger,
            created__date__gte=period.start_date,
            created__date__lte=period.end_date,
        ).exclude(reconciliation_matches__isnull=False).distinct()

    @staticmethod
    @transaction.atomic
    def auto_match(bank_account, period, tolerance=Decimal("0.000"), matched_by=None):
        matches = []
        bank_lines = ReconciliationService.get_unmatched_bank_lines(bank_account, period)
        gl_lines = ReconciliationService.get_unmatched_gl_lines(bank_account.ledger, period)

        for bank_line in bank_lines:
            candidate = None
            for gl_line in gl_lines:
                if gl_line.created.date() != bank_line.statement_date:
                    continue
                if abs(Decimal(str(gl_line.amount.amount)) - Decimal(str(bank_line.amount))) <= tolerance:
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
            gl_lines = gl_lines.exclude(pk=candidate.pk)

        return matches
