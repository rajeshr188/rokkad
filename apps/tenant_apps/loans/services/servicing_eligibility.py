"""Shared factual prerequisites; commands retain authority, locks and posting."""
from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from apps.tenant_apps.loans.selectors.servicing_contract import resolve_servicing_contract
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_completeness


def shared_monthly_bullet(loan):
    policy = loan.policy_snapshot
    return bool(policy and policy.policy_version == 2 and policy.interest_method == "SIMPLE"
        and policy.partial_month_method == "FULL_MONTH"
        and loan.product_version.repayment_structure in ("SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT"))


@dataclass(frozen=True)
class ServicingBlocker:
    code: str
    message: str


@dataclass(frozen=True)
class ServicingEligibility:
    operation: str
    purpose: str
    effective_date: date
    contract: object | None
    transaction_coverage: object | None
    blockers: tuple[ServicingBlocker, ...]

    @property
    def ready(self):
        return not self.blockers

    def require(self):
        if self.blockers:
            raise ValueError("; ".join(row.message for row in self.blockers))
        return self


def servicing_eligibility(loan, *, operation, purpose, effective_date):
    """Read only: supported debt is distinct from a complete-book attestation.

    Current wrappers supply today's date. Reviewed completed-action adapters supply
    the actual date. Internal restoration/correction writers retain their separate
    validation. No result authorizes a caller or permits generic opening posting.
    """
    if operation not in {"REPAYMENT", "FULL_RELEASE", "RENEWAL", "AUCTION"} or purpose not in {"CURRENT", "PAPER"}:
        raise ValueError("Unsupported servicing operation or purpose.")
    blockers = []
    def block(code, message):
        blockers.append(ServicingBlocker(code, message))
    contract = coverage = None
    if type(effective_date) is not date or effective_date > timezone.localdate():
        block("INVALID_DATE", "Enter the actual transaction date, no later than today.")
    else:
        try:
            contract = resolve_servicing_contract(loan, as_of_date=effective_date)
        except ValueError as exc:
            block("UNSUPPORTED_CONTRACT", str(exc))
    if contract is None:
        return ServicingEligibility(operation, purpose, effective_date, None, None, tuple(blockers))
    if loan.state != "ACTIVE":
        block("LOAN_NOT_ACTIVE", "Only an active loan can receive this servicing action.")
    from apps.tenant_apps.loans.selectors.servicing_dependencies import servicing_dependencies
    dependencies = servicing_dependencies(loan, effective_date=effective_date)
    if any(row["date"] > effective_date.isoformat() for row in dependencies.events):
        block("LATER_ACTIVITY", "Later activity is already recorded. Reconcile that activity before entering this earlier transaction.")
    if dependencies.accruals:
        block("LATER_ACCRUAL", "Interest has been finalized beyond this transaction date. Review the later periods first.")
    if any(row["date"] > effective_date.isoformat() for row in dependencies.custody):
        block("LATER_CUSTODY", "Later collateral movements exist. Review them before recording this earlier transaction.")
    if contract.origin_kind == "MIGRATION_OPENING" and effective_date <= contract.financial_history_from:
        block("CUTOVER_DATE", "Opening servicing must be strictly after cutover.")
    if purpose == "PAPER" and contract.origin_kind != "MIGRATION_OPENING" and not contract.profile.startswith("recorded-anniversary/"):
        shared_monthly = contract.profile == "native-monthly-policy/2" and shared_monthly_bullet(loan) and loan.disbursal_snapshot_id
        legacy_release = operation == "FULL_RELEASE" and contract.profile == "native-event-fold/1" and contract.policy_snapshot_id
        if not (shared_monthly or legacy_release):
            block("PAPER_CONTRACT", "Completed paper entry needs a supported saved monthly contract. Review the frozen contract before recording this transaction.")
    if operation == "FULL_RELEASE":
        items = tuple(loan.collateral_items.all())
        if not items:
            block("NO_COLLATERAL", "A loan without collateral cannot be released.")
        elif not any(item.custody_state != "WITH_CUSTOMER" for item in items):
            block("ALREADY_RETURNED", "Every collateral item has already been returned.")
    coverage = transaction_completeness(loan, effective_date)
    if operation == "AUCTION" and not coverage.complete:
        block("TRANSACTION_COVERAGE", "Confirm complete paper transactions through today before auction recovery. " + coverage.message)
    return ServicingEligibility(operation, purpose, effective_date, contract, coverage, tuple(blockers))


def paper_repayment_allocation_allowed(loan, balance, allocation):
    """Retain the opening reader's bounded profile rather than post unreadable facts."""
    if balance.fees_outstanding:
        raise ValueError("Paper receipt allocation with outstanding fees needs an agreed fee rule.")
    if allocation.principal and loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
        from .pawn_tranches import get_pawn_principal_tranche_balances
        if sum(row.principal_outstanding > 0 for row in get_pawn_principal_tranche_balances(loan)) > 1:
            raise ValueError("This reviewed opening allocation profile supports paper principal payments on one outstanding item only. Multiple-item paper allocations need a supported reviewed profile; no split will be inferred.")
