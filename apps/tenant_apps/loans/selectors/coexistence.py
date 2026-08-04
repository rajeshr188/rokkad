"""Source-labelled Girvi/Loans coexistence portfolio contracts."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse

from apps.tenant_apps.girvi import facade as girvi_facade
from apps.tenant_apps.loans.domain import (
    CollateralCustodyState,
    LoanOutboxStatus,
    PawnLoanState,
    TransactionKind,
)
from apps.tenant_apps.loans.models import PawnLoan, current_tenant_workspace_id
from apps.tenant_apps.loans.selectors.balances import (
    PawnLoanBalanceSelectorError,
    calculate_pawn_loan_balance,
)


ZERO = Decimal("0")


@dataclass(frozen=True)
class UnifiedLoanReadRow:
    source_system: str
    source_label: str
    owner_app: str
    source_id: int
    source_key: str
    loan_kind: str
    loan_number: str
    loan_date: date
    party_id: int | None
    party_name: str
    stored_status: str
    lifecycle_status: str
    lifecycle_bucket: str
    original_principal: Decimal
    principal_outstanding: Decimal
    interest_outstanding: Decimal
    total_due: Decimal
    collateral_count: int
    custody_summary: str
    owner_action_name: str
    owner_action_url: str
    financial_data_available: bool
    release_status: str = "NONE"
    dea_visibility: str = "NOT_VISIBLE"
    read_error: str = ""


@dataclass(frozen=True)
class UnifiedLoanSourceTotals:
    source_system: str
    source_label: str
    row_count: int
    active_count: int
    closed_count: int
    pending_count: int
    cancelled_count: int
    unavailable_count: int
    original_principal: Decimal
    principal_outstanding: Decimal
    interest_outstanding: Decimal
    total_due: Decimal


@dataclass(frozen=True)
class UnifiedLoanPortfolio:
    as_of_date: date
    rows: tuple[UnifiedLoanReadRow, ...]
    source_totals: tuple[UnifiedLoanSourceTotals, ...]

    @property
    def row_count(self):
        return len(self.rows)

    @property
    def total_principal_outstanding(self):
        return sum((row.principal_outstanding for row in self.rows), ZERO)

    @property
    def total_due(self):
        return sum((row.total_due for row in self.rows), ZERO)


def get_unified_loan_portfolio(*, as_of_date: date) -> UnifiedLoanPortfolio:
    """Combine legacy Girvi and new Loans rows without changing either source."""
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Unified loan reads require an active tenant schema.")

    girvi_rows = tuple(
        _adapt_girvi_row(row)
        for row in girvi_facade.get_loan_coexistence_rows(as_of_date=as_of_date)
    )
    loans_rows = get_loans_coexistence_rows(as_of_date=as_of_date)
    return build_unified_loan_portfolio(
        girvi_rows=girvi_rows,
        loans_rows=loans_rows,
        as_of_date=as_of_date,
    )


def get_loans_coexistence_rows(*, as_of_date: date) -> tuple[UnifiedLoanReadRow, ...]:
    """Return new-app source rows for comparison and unified-read consumers."""
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise ValueError("Loans coexistence reads require an active tenant schema.")
    pawn_loans = (
        PawnLoan.objects.filter(workspace_id=workspace_id)
        .select_related("borrower", "policy_snapshot")
        .prefetch_related(
            "collateral_items",
            "accounting_events__outbox",
            "releases__items",
            "releases__reversal",
        )
        .order_by("loan_date", "pk")
    )
    return tuple(
        _build_pawn_row(loan, as_of_date=as_of_date) for loan in pawn_loans
    )


def build_unified_loan_portfolio(
    *, girvi_rows, loans_rows, as_of_date: date
) -> UnifiedLoanPortfolio:
    girvi_rows = tuple(girvi_rows)
    loans_rows = tuple(loans_rows)
    _validate_source_rows(girvi_rows, source_system="GIRVI", owner_app="girvi")
    _validate_source_rows(loans_rows, source_system="LOANS", owner_app="loans")
    rows = tuple(
        sorted(
            girvi_rows + loans_rows,
            key=lambda row: (row.loan_date, row.source_system, row.source_id),
            reverse=True,
        )
    )
    return UnifiedLoanPortfolio(
        as_of_date=as_of_date,
        rows=rows,
        source_totals=(
            _source_totals("GIRVI", "Girvi", girvi_rows),
            _source_totals("LOANS", "Loans", loans_rows),
        ),
    )


def _adapt_girvi_row(row):
    return UnifiedLoanReadRow(
        source_system="GIRVI",
        source_label="Girvi",
        owner_app="girvi",
        source_id=row.source_id,
        source_key=row.source_key,
        loan_kind=row.loan_kind,
        loan_number=row.loan_number,
        loan_date=row.loan_date,
        party_id=row.party_id,
        party_name=row.party_name,
        stored_status=row.stored_status,
        lifecycle_status=row.lifecycle_status,
        lifecycle_bucket=row.lifecycle_bucket,
        original_principal=row.original_principal,
        principal_outstanding=row.principal_outstanding,
        interest_outstanding=row.interest_outstanding,
        total_due=row.total_due,
        collateral_count=row.collateral_count,
        custody_summary=row.custody_summary,
        owner_action_name=row.owner_action_name,
        owner_action_url=row.owner_action_url,
        financial_data_available=row.financial_data_available,
        release_status=row.release_status,
        dea_visibility=row.dea_visibility,
        read_error=row.read_error,
    )


def _build_pawn_row(loan, *, as_of_date):
    read_error = ""
    financial_data_available = True
    try:
        balance = calculate_pawn_loan_balance(
            loan,
            events=tuple(loan.accounting_events.all()),
            collateral_items=tuple(loan.collateral_items.all()),
            policy_snapshot=_optional_policy(loan),
            as_of_date=as_of_date,
        )
        principal_outstanding = balance.principal_outstanding
        interest_outstanding = balance.interest_outstanding
        total_due = balance.total_due
        lifecycle_status = _pawn_operational_status(loan, balance)
    except (PawnLoanBalanceSelectorError, ValueError) as exc:
        principal_outstanding = ZERO
        interest_outstanding = ZERO
        total_due = ZERO
        lifecycle_status = loan.state
        financial_data_available = False
        read_error = str(exc)

    collateral = tuple(loan.collateral_items.all())
    return UnifiedLoanReadRow(
        source_system="LOANS",
        source_label="Loans",
        owner_app="loans",
        source_id=loan.pk,
        source_key=f"LOANS:PAWN:{loan.pk}",
        loan_kind="PAWN",
        loan_number=loan.loan_number,
        loan_date=loan.loan_date,
        party_id=loan.borrower_id,
        party_name=loan.borrower.display_name,
        stored_status=loan.state,
        lifecycle_status=lifecycle_status,
        lifecycle_bucket=_pawn_lifecycle_bucket(loan.state),
        original_principal=loan.principal_amount,
        principal_outstanding=principal_outstanding,
        interest_outstanding=interest_outstanding,
        total_due=total_due,
        collateral_count=len(collateral),
        custody_summary=_pawn_custody_summary(collateral),
        owner_action_name="loans:pawn_loan_detail",
        owner_action_url=reverse("loans:pawn_loan_detail", args=[loan.pk]),
        financial_data_available=financial_data_available,
        release_status=_pawn_release_status(loan),
        dea_visibility=_pawn_dea_visibility(tuple(loan.accounting_events.all())),
        read_error=read_error,
    )


def _optional_policy(loan):
    try:
        return loan.policy_snapshot
    except (AttributeError, ObjectDoesNotExist):
        return None


def _pawn_operational_status(loan, balance):
    if loan.state != PawnLoanState.ACTIVE.value:
        return loan.state
    if not balance.posting_ready:
        return "ACCOUNTING_BLOCKED"
    if balance.is_overdue:
        return "OVERDUE"
    if balance.closure_ready:
        return "CLOSURE_READY"
    return "ACTIVE"


def _pawn_lifecycle_bucket(state):
    if state == PawnLoanState.ACTIVE.value:
        return "ACTIVE"
    if state == PawnLoanState.CLOSED.value:
        return "CLOSED"
    if state == PawnLoanState.CANCELLED.value:
        return "CANCELLED"
    return "PENDING"


def _pawn_custody_summary(collateral):
    counts = {state.value: 0 for state in CollateralCustodyState}
    for item in collateral:
        if item.custody_state in counts:
            counts[item.custody_state] += 1
    return (
        f"{counts[CollateralCustodyState.IN_VAULT.value]} vault / "
        f"{counts[CollateralCustodyState.WITH_FUNDING_LENDER.value]} lender / "
        f"{counts[CollateralCustodyState.WITH_CUSTOMER.value]} customer"
    )


def _pawn_release_status(loan):
    releases = tuple(
        release
        for release in loan.releases.all()
        if not hasattr(release, "reversal")
    )
    if not releases:
        return "NONE"
    return "FULL" if any(release.is_full_release for release in releases) else "PARTIAL"


def _pawn_dea_visibility(events):
    if not events:
        return "NOT_REQUIRED"
    outboxes = []
    for event in events:
        try:
            outboxes.append(event.outbox)
        except (AttributeError, ObjectDoesNotExist):
            return "MISSING"
    statuses = {outbox.status for outbox in outboxes}
    if LoanOutboxStatus.FAILED.value in statuses:
        return "FAILED"
    if statuses & {
        LoanOutboxStatus.PENDING.value,
        LoanOutboxStatus.PROCESSING.value,
    }:
        return "PENDING"
    required = tuple(
        outbox
        for event, outbox in zip(events, outboxes, strict=True)
        if _event_requires_dea_reference(event)
    )
    if any(
        outbox.dea_voucher_id is None or outbox.dea_journal_entry_id is None
        for outbox in required
    ):
        return "MISSING"
    if required:
        return "VISIBLE"
    return "NOT_REQUIRED"


def _event_requires_dea_reference(event):
    if event.event_kind in {
        TransactionKind.INTEREST_ACCRUAL.value,
        TransactionKind.INTEREST_CAPITALIZATION.value,
    }:
        detail_key = (
            "accrual"
            if event.event_kind == TransactionKind.INTEREST_ACCRUAL.value
            else "capitalization"
        )
        return (event.payload.get(detail_key) or {}).get(
            "accounting_recognition"
        ) != "CASH"
    if event.event_kind == TransactionKind.RELEASE_RECEIPT.value:
        values = event.payload.get("values") or {}
        return sum(
            (Decimal(str(values.get(key, "0"))) for key in ("principal", "interest", "fees")),
            ZERO,
        ) != ZERO
    if event.event_kind == TransactionKind.REVERSAL.value:
        try:
            return event.reversal_of.outbox.dea_voucher_id is not None
        except ObjectDoesNotExist:
            return True
    return True


def _validate_source_rows(rows, *, source_system, owner_app):
    for row in rows:
        if row.source_system != source_system or row.owner_app != owner_app:
            raise ValueError("Unified loan row source ownership is inconsistent.")
        if not row.owner_action_name.startswith(f"{owner_app}:"):
            raise ValueError("Unified loan action must use the owning app namespace.")
        if not row.owner_action_url:
            raise ValueError("Unified loan row requires an owner action URL.")


def _source_totals(source_system, source_label, rows):
    return UnifiedLoanSourceTotals(
        source_system=source_system,
        source_label=source_label,
        row_count=len(rows),
        active_count=sum(row.lifecycle_bucket == "ACTIVE" for row in rows),
        closed_count=sum(row.lifecycle_bucket == "CLOSED" for row in rows),
        pending_count=sum(row.lifecycle_bucket == "PENDING" for row in rows),
        cancelled_count=sum(row.lifecycle_bucket == "CANCELLED" for row in rows),
        unavailable_count=sum(not row.financial_data_available for row in rows),
        original_principal=sum((row.original_principal for row in rows), ZERO),
        principal_outstanding=sum((row.principal_outstanding for row in rows), ZERO),
        interest_outstanding=sum((row.interest_outstanding for row in rows), ZERO),
        total_due=sum((row.total_due for row in rows), ZERO),
    )


__all__ = [
    "UnifiedLoanPortfolio",
    "UnifiedLoanReadRow",
    "UnifiedLoanSourceTotals",
    "build_unified_loan_portfolio",
    "get_loans_coexistence_rows",
    "get_unified_loan_portfolio",
]
