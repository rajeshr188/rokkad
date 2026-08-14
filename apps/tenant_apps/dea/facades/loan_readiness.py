"""Read-only prerequisites for operational loan posting callers."""

from dataclasses import dataclass
from datetime import date

from django.core.exceptions import ValidationError

from apps.tenant_apps.dea.models import AccountingPeriod, Ledger
from apps.tenant_apps.dea.posting.resolver import get_ledger_id_by_key
from apps.tenant_apps.dea.services.account_resolution import resolve_party_account


@dataclass(frozen=True)
class LoanPostingPrerequisites:
    """DEA-owned dependencies required before a PawnLoan can be posted.

    This is deliberately a read-only boundary.  It neither creates mappings nor
    opens periods, and it does not create a voucher or journal entry.
    """

    open_period: object | None
    funding_cash_ledger: object | None
    borrower_account: object | None
    interest_income_ledger: object | None
    fee_income_ledger: object | None
    principal_control_ledger: object | None
    borrower_control_ledger: object | None
    interest_receivable_ledger: object | None
    unearned_interest_ledger: object | None = None


def get_loan_posting_prerequisites(
    *,
    party,
    effective_date: date,
    requires_fee_income: bool = False,
) -> LoanPostingPrerequisites:
    """Return existing DEA setup only; callers decide how to present blockers."""
    return LoanPostingPrerequisites(
        open_period=(
            AccountingPeriod.objects.filter(
                status=AccountingPeriod.PeriodStatus.OPEN,
                start_date__lte=effective_date,
                end_date__gte=effective_date,
            )
            .order_by("start_date")
            .first()
        ),
        # The current loan posting rules use CASH.  A future cash/bank account
        # choice must be added to the source event and its posting rule together.
        funding_cash_ledger=Ledger.objects.filter(name="CASH").first(),
        borrower_account=resolve_party_account(
            party,
            role_key="BORROWER",
            purpose="BORROWER_LOAN_RECEIVABLE",
            create=False,
        ),
        interest_income_ledger=Ledger.objects.filter(name="INTEREST_INCOME").first(),
        fee_income_ledger=(
            _ledger_by_key("DOCUMENT_CHARGE_INCOME") if requires_fee_income else True
        ),
        principal_control_ledger=Ledger.objects.filter(
            name="LOAN_PRINCIPAL_CTRL"
        ).first(),
        borrower_control_ledger=Ledger.objects.filter(
            name="BORROWER_LOAN_CTRL"
        ).first(),
        interest_receivable_ledger=Ledger.objects.filter(
            name="INTEREST_RECEIVABLE"
        ).first(),
        unearned_interest_ledger=Ledger.objects.filter(name="Unearned Revenue").first(),
    )


def _ledger_by_key(key: str):
    """Resolve readiness through the same canonical key aliases as posting."""
    try:
        ledger_id = get_ledger_id_by_key(key)
    except ValidationError:
        return None
    return Ledger.objects.filter(pk=ledger_id).first()
