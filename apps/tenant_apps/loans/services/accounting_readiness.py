"""Read-only accounting setup checks for future PawnLoan financial actions."""

from dataclasses import dataclass
from datetime import date

from django.urls import NoReverseMatch, reverse

from apps.tenant_apps.dea import facade as dea_facade


@dataclass(frozen=True)
class AccountingReadinessBlocker:
    code: str
    message: str
    action_label: str
    action_url: str | None


@dataclass(frozen=True)
class PawnLoanAccountingReadiness:
    effective_date: date
    blockers: tuple[AccountingReadinessBlocker, ...]

    @property
    def ready(self):
        return not self.blockers


class PawnLoanAccountingNotReadyError(ValueError):
    def __init__(self, readiness: PawnLoanAccountingReadiness):
        self.readiness = readiness
        super().__init__(
            "PawnLoan accounting is not ready: "
            + "; ".join(blocker.message for blocker in readiness.blockers)
        )


def assess_pawn_loan_accounting_readiness(
    loan,
    *,
    effective_date: date,
    requires_fee_income: bool = False,
    requires_interest_receivable: bool = False,
) -> PawnLoanAccountingReadiness:
    """Return precise, actionable disbursal blockers without mutating setup."""
    prerequisites = dea_facade.get_loan_posting_prerequisites(
        party=loan.borrower,
        effective_date=effective_date,
        requires_fee_income=requires_fee_income,
    )
    blockers = []
    if not prerequisites.open_period:
        blockers.append(
            _blocker(
                "OPEN_ACCOUNTING_PERIOD_REQUIRED",
                f"No open accounting period contains {effective_date.isoformat()}.",
                "Manage accounting periods",
                "dea_period_list",
            )
        )
    if not prerequisites.funding_cash_ledger:
        blockers.append(
            _blocker(
                "FUNDING_CASH_ACCOUNT_REQUIRED",
                "A funding cash account (CASH) is required before disbursal.",
                "Manage cash and bank ledgers",
                "dea_ledger_list",
            )
        )
    if not prerequisites.principal_control_ledger:
        blockers.append(
            _blocker(
                "LOAN_PRINCIPAL_CONTROL_REQUIRED",
                "A LOAN_PRINCIPAL_CTRL ledger is required before disbursal.",
                "Manage loan ledgers",
                "dea_ledger_list",
            )
        )
    if not prerequisites.borrower_control_ledger:
        blockers.append(
            _blocker(
                "BORROWER_LOAN_CONTROL_REQUIRED",
                "A BORROWER_LOAN_CTRL ledger is required before disbursal.",
                "Manage loan ledgers",
                "dea_ledger_list",
            )
        )
    if not prerequisites.borrower_account:
        blockers.append(
            _blocker(
                "BORROWER_RECEIVABLE_REQUIRED",
                "The borrower needs an active loan-receivable account mapping.",
                "Set up borrower accounting",
                "loans:pawn_borrower_account_setup",
                route_args=(loan.pk,) if getattr(loan, "pk", None) else (),
            )
        )
    if not prerequisites.interest_income_ledger:
        blockers.append(
            _blocker(
                "INTEREST_INCOME_ACCOUNT_REQUIRED",
                "An INTEREST_INCOME ledger is required before disbursal.",
                "Manage income ledgers",
                "dea_ledger_list",
            )
        )
    if requires_interest_receivable and not prerequisites.interest_receivable_ledger:
        blockers.append(
            _blocker(
                "INTEREST_RECEIVABLE_ACCOUNT_REQUIRED",
                "An INTEREST_RECEIVABLE ledger is required for accrual accounting.",
                "Manage receivable ledgers",
                "dea_ledger_list",
            )
        )
    if requires_fee_income and not prerequisites.fee_income_ledger:
        blockers.append(
            _blocker(
                "FEE_INCOME_ACCOUNT_REQUIRED",
                "A DOCUMENT_CHARGE_INCOME ledger is required for this loan's fees.",
                "Manage income ledgers",
                "dea_ledger_list",
            )
        )
    return PawnLoanAccountingReadiness(effective_date=effective_date, blockers=tuple(blockers))


def require_pawn_loan_accounting_readiness(
    loan,
    *,
    effective_date: date,
    requires_fee_income: bool = False,
    requires_interest_receivable: bool = False,
) -> PawnLoanAccountingReadiness:
    """Fail closed for the E3.4 disbursal command and later financial actions."""
    readiness = assess_pawn_loan_accounting_readiness(
        loan,
        effective_date=effective_date,
        requires_fee_income=requires_fee_income,
        requires_interest_receivable=requires_interest_receivable,
    )
    if not readiness.ready:
        raise PawnLoanAccountingNotReadyError(readiness)
    return readiness


def _blocker(code, message, action_label, route_name, *, route_args=()):
    try:
        action_url = reverse(route_name, args=route_args)
    except NoReverseMatch:
        action_url = None
    return AccountingReadinessBlocker(
        code=code,
        message=message,
        action_label=action_label,
        action_url=action_url,
    )
