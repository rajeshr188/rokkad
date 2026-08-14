"""Read-only FundingLoan operator projections and integrity findings."""

from dataclasses import dataclass
from decimal import Decimal

from apps.tenant_apps.loans.domain import CollateralCustodyState, PawnLoanState
from apps.tenant_apps.loans.domain.future_funding import (
    FundingCollateralCandidate,
    FundingLoanEvent as DomainFundingLoanEvent,
    FundingLoanBalance,
    FundingLoanEventKind,
    FundingLoanState,
    assess_funding_closure,
    calculate_funding_loan_balance,
)
from apps.tenant_apps.loans.models import (
    FundingLoan,
    FundingLoanDraftCollateral,
    FundingLoanEvent,
    FundingPledgeItem,
    current_tenant_workspace_id,
)


class FundingLoanSelectorError(ValueError):
    pass


@dataclass(frozen=True)
class FundingLoanSummary:
    funding_loan_id: int
    funding_number: str
    lender_id: int
    lender_name: str
    state: str
    principal_outstanding: Decimal
    interest_outstanding: Decimal
    fees_outstanding: Decimal
    total_due: Decimal
    active_collateral_count: int
    created_at: object


@dataclass(frozen=True)
class FundingCollateralRow:
    pledge_item_id: int
    collateral_item_id: int
    source_pawn_loan_id: int
    source_loan_number: str
    description: str
    selected_collateral_value: Decimal
    custody_state: str
    active: bool


@dataclass(frozen=True)
class FundingTimelineRow:
    occurred_at: object
    entry_type: str
    operation: str
    effective_date: object
    summary: str
    source_id: int
    reversal: bool = False


@dataclass(frozen=True)
class FundingStatementRow:
    source_id: int
    sequence: int
    effective_date: object
    operation: str
    principal_effect: Decimal
    interest_effect: Decimal
    fee_effect: Decimal
    principal_balance: Decimal
    interest_balance: Decimal
    fee_balance: Decimal
    total_balance: Decimal
    actor_name: str


@dataclass(frozen=True)
class FundingLoanDetail:
    summary: FundingLoanSummary
    activated_on: object | None
    maturity_on: object | None
    monthly_interest_rate: Decimal | None
    maximum_funding_ltv_ratio: Decimal | None
    collateral: tuple[FundingCollateralRow, ...]
    statement: tuple[FundingStatementRow, ...]
    timeline: tuple[FundingTimelineRow, ...]
    financial_correction: object | None
    return_corrections: tuple
    pledge_correction_available: bool


@dataclass(frozen=True)
class FundingCorrectionTarget:
    source_id: int
    operation: str
    effective_date: object
    summary: str


@dataclass(frozen=True)
class FundingSettlementReadiness:
    financially_settled: bool
    collateral_returned: bool
    closure_ready: bool
    blockers: tuple[str, ...]
    active_collateral_ids: tuple[int, ...]


@dataclass(frozen=True)
class FundingLoanIntegrityFinding:
    code: str
    funding_loan_id: int
    object_type: str
    object_id: int
    message: str


@dataclass(frozen=True)
class FundingLoanDraftInputDetail:
    principal_amount: Decimal | None
    monthly_interest_rate: Decimal | None
    activated_on: object | None
    maturity_on: object | None
    maximum_funding_ltv_ratio: Decimal
    currency_quantum: Decimal
    collateral_item_ids: tuple[int, ...]
    total_collateral_value: Decimal
    maximum_funded_amount: Decimal
    ready: bool
    blockers: tuple[str, ...]


def get_funding_loan_summaries(*, states=None):
    workspace_id = _workspace_id()
    loans = FundingLoan.objects.filter(workspace_id=workspace_id).select_related(
        "lender", "terms_snapshot"
    )
    if states is not None:
        loans = loans.filter(state__in=tuple(str(state) for state in states))
    loans = loans.prefetch_related("events", "pledge__items").order_by(
        "-created_at", "funding_number"
    )
    return tuple(_summary(loan) for loan in loans)


def get_funding_loan_detail(funding_loan_id: int):
    workspace_id = _workspace_id()
    try:
        loan = (
            FundingLoan.objects.filter(workspace_id=workspace_id)
            .select_related("lender", "terms_snapshot", "pledge")
            .prefetch_related(
                "events__actor",
                "events__reversal_of",
                "pledge__items__collateral_item__loan",
                "pledge__custody_events",
                "returns__items__pledge_item",
                "returns__custody_events",
                "returns__reversal",
                "pledge__reversal__custody_events",
                "returns__reversal__custody_events",
            )
            .get(pk=funding_loan_id)
        )
    except FundingLoan.DoesNotExist as exc:
        raise FundingLoanSelectorError(
            "FundingLoan was not found in the active workspace."
        ) from exc
    terms = getattr(loan, "terms_snapshot", None)
    collateral = tuple(
        FundingCollateralRow(
            pledge_item_id=item.pk,
            collateral_item_id=item.collateral_item_id,
            source_pawn_loan_id=item.source_pawn_loan_id,
            source_loan_number=item.collateral_item.loan.loan_number,
            description=item.collateral_item.description,
            selected_collateral_value=item.selected_collateral_value,
            custody_state=item.collateral_item.custody_state,
            active=item.released_at is None,
        )
        for item in sorted(loan.pledge.items.all(), key=lambda row: row.collateral_item_id)
    ) if hasattr(loan, "pledge") else ()
    timeline = _timeline(loan)
    financial_correction = _financial_correction(loan)
    return_corrections = _return_corrections(loan)
    balance = _balance(loan)
    return FundingLoanDetail(
        summary=_summary(loan),
        activated_on=terms.activated_on if terms else None,
        maturity_on=terms.maturity_on if terms else None,
        monthly_interest_rate=terms.monthly_interest_rate if terms else None,
        maximum_funding_ltv_ratio=(
            terms.maximum_funding_ltv_ratio if terms else None
        ),
        collateral=collateral,
        statement=_statement(loan),
        timeline=timeline,
        financial_correction=financial_correction,
        return_corrections=return_corrections,
        pledge_correction_available=(
            loan.state == FundingLoanState.SETTLEMENT_PENDING.value
            and balance.financially_settled
            and hasattr(loan, "pledge")
            and not hasattr(loan.pledge, "reversal")
            and bool(collateral)
            and all(row.active for row in collateral)
        ),
    )


def get_funding_loan_draft_inputs(funding_loan_id: int):
    workspace_id = _workspace_id()
    try:
        loan = FundingLoan.objects.select_related("draft_terms").get(
            pk=funding_loan_id,
            workspace_id=workspace_id,
            state=FundingLoanState.DRAFT.value,
        )
    except FundingLoan.DoesNotExist as exc:
        raise FundingLoanSelectorError(
            "Draft FundingLoan was not found in the active workspace."
        ) from exc
    terms = getattr(loan, "draft_terms", None)
    selections = tuple(
        FundingLoanDraftCollateral.objects.filter(funding_loan=loan)
        .select_related("collateral_item")
        .order_by("collateral_item__loan_id", "collateral_item_id")
    )
    total_value = sum(
        (row.selected_collateral_value for row in selections),
        Decimal("0"),
    )
    maximum_ltv = (
        terms.maximum_funding_ltv_ratio if terms else Decimal("0.800000")
    )
    maximum_funded = total_value * maximum_ltv
    blockers = []
    if terms is None:
        blockers.append("Enter valid funding terms.")
    if not selections:
        blockers.append("Select at least one eligible collateral item.")
    if terms is not None and terms.principal_amount > maximum_funded:
        blockers.append("Funding principal exceeds the selected collateral LTV limit.")
    return FundingLoanDraftInputDetail(
        principal_amount=terms.principal_amount if terms else None,
        monthly_interest_rate=terms.monthly_interest_rate if terms else None,
        activated_on=terms.activated_on if terms else None,
        maturity_on=terms.maturity_on if terms else None,
        maximum_funding_ltv_ratio=maximum_ltv,
        currency_quantum=terms.currency_quantum if terms else Decimal("0.0100"),
        collateral_item_ids=tuple(row.collateral_item_id for row in selections),
        total_collateral_value=total_value,
        maximum_funded_amount=maximum_funded,
        ready=not blockers,
        blockers=tuple(blockers),
    )


def get_funding_settlement_readiness(funding_loan_id: int, *, detail=None):
    detail = detail or get_funding_loan_detail(funding_loan_id)
    candidates = tuple(
        FundingCollateralCandidate(
            collateral_item_id=row.collateral_item_id,
            pawn_loan_id=row.source_pawn_loan_id,
            pawn_loan_state=PawnLoanState.ACTIVE,
            custody_state=CollateralCustodyState(row.custody_state),
            active_funding_pledge_id=(row.pledge_item_id if row.active else None),
            collateral_value=row.selected_collateral_value,
        )
        for row in detail.collateral
    )
    closure = assess_funding_closure(
        FundingLoanBalance(
            principal_outstanding=detail.summary.principal_outstanding,
            interest_outstanding=detail.summary.interest_outstanding,
            fees_outstanding=detail.summary.fees_outstanding,
            total_due=detail.summary.total_due,
        ),
        candidates,
    )
    return FundingSettlementReadiness(
        financially_settled=closure.financially_settled,
        collateral_returned=closure.collateral_returned,
        closure_ready=closure.ready,
        blockers=closure.blockers,
        active_collateral_ids=tuple(
            row.collateral_item_id for row in detail.collateral if row.active
        ),
    )


def get_funding_loan_integrity_findings():
    workspace_id = _workspace_id()
    loans = tuple(
        FundingLoan.objects.filter(workspace_id=workspace_id)
        .select_related("terms_snapshot", "pledge")
        .prefetch_related(
            "events__reversal_of",
            "pledge__items__collateral_item",
            "pledge__custody_events",
            "returns__items__pledge_item",
            "returns__custody_events",
            "pledge__reversal__custody_events",
            "returns__reversal__custody_events",
        )
        .order_by("pk")
    )
    findings = []
    for loan in loans:
        events = tuple(sorted(loan.events.all(), key=lambda event: event.sequence))
        expected_sequences = tuple(range(1, len(events) + 1))
        actual_sequences = tuple(event.sequence for event in events)
        if actual_sequences != expected_sequences:
            findings.append(
                _finding(
                    "EVENT_SEQUENCE",
                    loan,
                    "funding_loan",
                    loan.pk,
                    "FundingLoan event sequence is not contiguous from one.",
                )
            )
        if loan.state not in {FundingLoanState.DRAFT.value, FundingLoanState.CANCELLED.value}:
            if not events or not hasattr(loan, "terms_snapshot") or not hasattr(loan, "pledge"):
                findings.append(
                    _finding(
                        "ACTIVATION_EVIDENCE",
                        loan,
                        "funding_loan",
                        loan.pk,
                        "Open or closed FundingLoan is missing activation evidence.",
                    )
                )
                continue
        try:
            balance = _balance(loan)
        except ValueError as exc:
            findings.append(
                _finding("EVENT_FOLD", loan, "funding_loan", loan.pk, str(exc))
            )
            balance = None
        pledge_items = tuple(loan.pledge.items.all()) if hasattr(loan, "pledge") else ()
        for item in pledge_items:
            expected_custody = (
                CollateralCustodyState.WITH_FUNDING_LENDER.value
                if item.released_at is None
                else CollateralCustodyState.IN_VAULT.value
            )
            if item.collateral_item.custody_state != expected_custody:
                findings.append(
                    _finding(
                        "COLLATERAL_PROJECTION",
                        loan,
                        "pledge_item",
                        item.pk,
                        "Pledge membership and collateral custody projection disagree.",
                    )
                )
            latest = item.collateral_item.custody_history.order_by("-id").first()
            if latest is None or latest.to_state != item.collateral_item.custody_state:
                findings.append(
                    _finding(
                        "CUSTODY_TIMELINE",
                        loan,
                        "collateral_item",
                        item.collateral_item_id,
                        "Latest custody evidence does not match the collateral projection.",
                    )
                )
        if loan.state == FundingLoanState.CLOSED.value:
            if balance is not None and not balance.financially_settled:
                findings.append(
                    _finding(
                        "CLOSED_BALANCE",
                        loan,
                        "funding_loan",
                        loan.pk,
                        "Closed FundingLoan has a non-zero operational balance.",
                    )
                )
            if any(item.released_at is None for item in pledge_items):
                findings.append(
                    _finding(
                        "CLOSED_COLLATERAL",
                        loan,
                        "funding_loan",
                        loan.pk,
                        "Closed FundingLoan retains active pledged collateral.",
                    )
                )
    return tuple(findings)


def _summary(loan):
    balance = _balance(loan)
    pledge = getattr(loan, "pledge", None)
    active_count = (
        sum(item.released_at is None for item in pledge.items.all()) if pledge else 0
    )
    return FundingLoanSummary(
        funding_loan_id=loan.pk,
        funding_number=loan.funding_number,
        lender_id=loan.lender_id,
        lender_name=loan.lender.display_name,
        state=loan.state,
        principal_outstanding=balance.principal_outstanding,
        interest_outstanding=balance.interest_outstanding,
        fees_outstanding=balance.fees_outstanding,
        total_due=balance.total_due,
        active_collateral_count=active_count,
        created_at=loan.created_at,
    )


def _balance(loan):
    terms = getattr(loan, "terms_snapshot", None)
    quantum = terms.currency_quantum if terms else Decimal("0.01")
    events = tuple(
        DomainFundingLoanEvent(
            sequence=event.sequence,
            kind=FundingLoanEventKind(event.event_kind),
            principal_amount=event.principal_amount,
            interest_amount=event.interest_amount,
            fee_amount=event.fee_amount,
            reversal_of_sequence=(
                event.reversal_of.sequence if event.reversal_of_id else None
            ),
        )
        for event in sorted(loan.events.all(), key=lambda row: row.sequence)
    )
    if not events and loan.state in {
        FundingLoanState.DRAFT.value,
        FundingLoanState.CANCELLED.value,
    }:
        zero = Decimal("0").quantize(quantum)
        return FundingLoanBalance(zero, zero, zero, zero)
    return calculate_funding_loan_balance(events, currency_quantum=quantum)


def _timeline(loan):
    rows = [
        FundingTimelineRow(
            occurred_at=event.created_at,
            entry_type="FINANCIAL",
            operation=event.operation,
            effective_date=event.effective_date,
            summary=(
                f"Principal {event.principal_amount}; interest {event.interest_amount}; "
                f"fees {event.fee_amount}"
            ),
            source_id=event.pk,
            reversal=event.event_kind == FundingLoanEventKind.REVERSAL.value,
        )
        for event in loan.events.all()
    ]
    custody_events = []
    if hasattr(loan, "pledge"):
        custody_events.extend(loan.pledge.custody_events.all())
        if hasattr(loan.pledge, "reversal"):
            custody_events.extend(loan.pledge.reversal.custody_events.all())
    for funding_return in loan.returns.all():
        custody_events.extend(funding_return.custody_events.all())
        if hasattr(funding_return, "reversal"):
            custody_events.extend(funding_return.reversal.custody_events.all())
    rows.extend(
        FundingTimelineRow(
            occurred_at=event.created_at,
            entry_type="CUSTODY",
            operation=_custody_operation(event),
            effective_date=event.effective_date,
            summary=f"Collateral {event.collateral_item_id}: {event.from_state} to {event.to_state}",
            source_id=event.pk,
            reversal=bool(
                event.funding_pledge_reversal_id or event.funding_return_reversal_id
            ),
        )
        for event in custody_events
    )
    return tuple(sorted(rows, key=lambda row: (row.occurred_at, row.source_id)))


def _statement(loan):
    events = tuple(sorted(loan.events.all(), key=lambda row: row.sequence))
    if not events:
        return ()
    terms = getattr(loan, "terms_snapshot", None)
    quantum = terms.currency_quantum if terms else Decimal("0.01")
    rows = []
    domain_events = []
    for event in events:
        domain_events.append(
            DomainFundingLoanEvent(
                sequence=event.sequence,
                kind=FundingLoanEventKind(event.event_kind),
                principal_amount=event.principal_amount,
                interest_amount=event.interest_amount,
                fee_amount=event.fee_amount,
                reversal_of_sequence=(
                    event.reversal_of.sequence if event.reversal_of_id else None
                ),
            )
        )
        balance = calculate_funding_loan_balance(
            tuple(domain_events),
            currency_quantum=quantum,
        )
        if event.event_kind == FundingLoanEventKind.REPAYMENT.value:
            direction = Decimal("-1")
        elif event.event_kind == FundingLoanEventKind.REVERSAL.value:
            direction = (
                Decimal("1")
                if event.reversal_of.event_kind == FundingLoanEventKind.REPAYMENT.value
                else Decimal("-1")
            )
        else:
            direction = Decimal("1")
        actor = event.actor
        actor_name = "System"
        if actor is not None:
            actor_name = actor.get_full_name() or actor.get_username()
        rows.append(
            FundingStatementRow(
                source_id=event.pk,
                sequence=event.sequence,
                effective_date=event.effective_date,
                operation=event.operation,
                principal_effect=event.principal_amount * direction,
                interest_effect=event.interest_amount * direction,
                fee_effect=event.fee_amount * direction,
                principal_balance=balance.principal_outstanding,
                interest_balance=balance.interest_outstanding,
                fee_balance=balance.fees_outstanding,
                total_balance=balance.total_due,
                actor_name=actor_name,
            )
        )
    return tuple(rows)


def _financial_correction(loan):
    reversed_ids = {
        event.reversal_of_id
        for event in loan.events.all()
        if event.event_kind == FundingLoanEventKind.REVERSAL.value
    }
    active = [
        event
        for event in loan.events.all()
        if event.event_kind != FundingLoanEventKind.REVERSAL.value
        and event.pk not in reversed_ids
    ]
    if not active or active[-1].event_kind == FundingLoanEventKind.ACTIVATION.value:
        return None
    event = active[-1]
    return FundingCorrectionTarget(
        source_id=event.pk,
        operation=event.operation,
        effective_date=event.effective_date,
        summary=(
            f"Principal {event.principal_amount}; interest {event.interest_amount}; "
            f"fees {event.fee_amount}"
        ),
    )


def _return_corrections(loan):
    rows = []
    for funding_return in loan.returns.all():
        if hasattr(funding_return, "reversal"):
            continue
        items = tuple(funding_return.items.all())
        if items and all(item.pledge_item.released_at is not None for item in items):
            rows.append(
                FundingCorrectionTarget(
                    source_id=funding_return.pk,
                    operation="RETURN_COLLATERAL",
                    effective_date=funding_return.effective_date,
                    summary=f"{len(items)} collateral item(s) returned",
                )
            )
    return tuple(rows)


def _custody_operation(event):
    if event.funding_pledge_reversal_id:
        return "REVERSE_PLEDGE"
    if event.funding_return_reversal_id:
        return "REVERSE_RETURN"
    if event.funding_pledge_id:
        return "PLEDGE"
    return "RETURN_COLLATERAL"


def _finding(code, loan, object_type, object_id, message):
    return FundingLoanIntegrityFinding(code, loan.pk, object_type, object_id, message)


def _workspace_id():
    workspace_id = current_tenant_workspace_id()
    if workspace_id is None:
        raise FundingLoanSelectorError(
            "FundingLoan selectors require an active tenant schema."
        )
    return workspace_id


__all__ = [
    "FundingCollateralRow",
    "FundingCorrectionTarget",
    "FundingLoanDetail",
    "FundingLoanIntegrityFinding",
    "FundingLoanSelectorError",
    "FundingLoanSummary",
    "FundingStatementRow",
    "FundingSettlementReadiness",
    "FundingTimelineRow",
    "get_funding_loan_detail",
    "get_funding_loan_integrity_findings",
    "get_funding_loan_summaries",
    "get_funding_settlement_readiness",
]
