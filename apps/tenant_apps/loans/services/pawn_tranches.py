"""Reconstruct collateral principal balances from immutable source evidence."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from itertools import groupby
from django.db.models import Q
from apps.tenant_apps.loans.selectors.disbursal import effective_disbursal_snapshot

from apps.tenant_apps.loans.models import (
    PawnLoanPrincipalOpeningLine,
    PawnLoanRepaymentAllocationLine,
    PawnLoanPrincipalClosingLine,
)


class PawnTrancheBalanceError(ValueError):
    pass


@dataclass(frozen=True)
class PawnPrincipalTrancheBalance:
    collateral_item_id: int
    monthly_interest_rate: Decimal
    initial_principal: Decimal
    principal_outstanding: Decimal


def get_pawn_principal_tranche_balances(
    loan, *, as_of_date: date | None = None
) -> tuple[PawnPrincipalTrancheBalance, ...]:
    """Fold active repayment lines over the frozen disbursal allocations."""
    origins = tuple(loan.loan_events.filter(event_kind="MIGRATION_OPENING"))
    opening = None
    if origins:
        from .opening_evidence import read_opening_evidence, opening_tranches, OpeningEvidenceError
        if len(origins) != 1 or loan.loan_events.filter(event_kind__in=["DISBURSAL", "RENEWAL_OPENING"]).exists():
            raise PawnTrancheBalanceError("Migration opening requires exactly one financial origin.")
        if as_of_date is not None and as_of_date < origins[0].effective_date:
            raise PawnTrancheBalanceError("Item principal before migration cutover is unavailable.")
        try:
            opening = read_opening_evidence(loan, origins[0])
        except OpeningEvidenceError as exc:
            raise PawnTrancheBalanceError(str(exc)) from exc
    disbursal = effective_disbursal_snapshot(loan, as_of_date=as_of_date)
    if opening is not None:
        if disbursal is not None:
            raise PawnTrancheBalanceError("Migration opening cannot have fabricated disbursal evidence.")
        tranches = opening_tranches(opening)
    elif disbursal is not None:
        tranches = tuple(disbursal.evidence.get("tranches") or ())
    else:
        opening_lines = tuple(
            PawnLoanPrincipalOpeningLine.objects.filter(
                loan_event__loan=loan,
                loan_event__reversed_by_event__isnull=True,
            ).order_by("allocation_order")
        )
        if not opening_lines:
            return ()
        tranches = tuple(
            {
                "collateral_item_id": line.collateral_item_id,
                "allocated_principal": line.principal_opened,
                "monthly_interest_rate": line.monthly_interest_rate,
            }
            for line in opening_lines
        )
    if not tranches:
        raise PawnTrancheBalanceError(
            "Itemized PawnLoan disbursal is missing frozen tranche evidence."
        )
    collateral_ids = set(loan.collateral_items.values_list("pk", flat=True))
    if opening is not None and collateral_ids != set(opening["item_mapping"].values()):
        raise PawnTrancheBalanceError("Migration opening item membership differs from the loan.")
    ordered_ids = []
    rates = {}
    initial = {}
    current = {}
    for tranche in tranches:
        try:
            item_id = int(tranche["collateral_item_id"])
            principal = Decimal(str(tranche["allocated_principal"]))
            rate = Decimal(str(tranche["monthly_interest_rate"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise PawnTrancheBalanceError(
                "Frozen disbursal tranche evidence is incomplete."
            ) from exc
        if item_id not in collateral_ids or item_id in current:
            raise PawnTrancheBalanceError(
                "Frozen disbursal tranche identities do not match this PawnLoan."
            )
        if principal < 0 or rate < 0:
            raise PawnTrancheBalanceError(
                "Frozen disbursal tranche amounts cannot be negative."
            )
        ordered_ids.append(item_id)
        rates[item_id] = rate
        initial[item_id] = principal
        current[item_id] = principal

    active = Q(loan_event__reversed_by_event__isnull=True)
    if as_of_date is not None:
        active |= Q(loan_event__reversed_by_event__effective_date__gt=as_of_date)
    lines = (
        PawnLoanRepaymentAllocationLine.objects.filter(active, loan_event__loan=loan)
        .select_related("loan_event")
        .order_by(
            "loan_event__effective_date",
            "loan_event_id",
            "allocation_order",
        )
    )
    if as_of_date is not None:
        lines = lines.filter(loan_event__effective_date__lte=as_of_date)
    for _event_id, event_lines_iter in groupby(lines, key=lambda line: line.loan_event_id):
        event_lines = tuple(event_lines_iter)
        event = event_lines[0].loan_event
        if opening is not None and event.effective_date <= origins[0].effective_date:
            raise PawnTrancheBalanceError("Repayment allocation cannot overlap the migration cutover.")
        values = event.payload.get("values") or {}
        expected_principal = Decimal(
            str(values.get("original_principal", values.get("principal", "0")))
        )
        if sum(
            (line.principal_applied for line in event_lines), Decimal("0")
        ) != expected_principal:
            raise PawnTrancheBalanceError(
                "Repayment allocation lines do not reconcile to event principal."
            )
        expected_order = sorted(
            current,
            key=lambda item_id: (-rates[item_id], item_id),
        )
        if [line.allocation_order for line in event_lines] != list(
            range(1, len(event_lines) + 1)
        ) or [line.collateral_item_id for line in event_lines] != expected_order:
            raise PawnTrancheBalanceError(
                "Repayment allocation lines violate highest-rate-first ordering."
            )
        for line in event_lines:
            item_id = line.collateral_item_id
            if item_id not in current:
                raise PawnTrancheBalanceError(
                    "Repayment allocation references unknown collateral."
                )
            if line.monthly_interest_rate != rates[item_id]:
                raise PawnTrancheBalanceError(
                    "Repayment allocation rate differs from frozen disbursal evidence."
                )
            if line.balance_before != current[item_id]:
                raise PawnTrancheBalanceError(
                    "Repayment allocation history has a discontinuous item balance."
                )
            if line.balance_before - line.principal_applied != line.balance_after:
                raise PawnTrancheBalanceError(
                    "Repayment allocation history does not reconcile."
                )
            current[item_id] = line.balance_after

    if opening is not None:
        closures = PawnLoanPrincipalClosingLine.objects.filter(active, loan_event__loan=loan)
        if as_of_date is not None:
            closures = closures.filter(loan_event__effective_date__lte=as_of_date)
        closed = tuple(closures.select_related("loan_event"))
        if closed:
            if len({line.loan_event_id for line in closed}) != 1 or {line.collateral_item_id for line in closed} != set(current):
                raise PawnTrancheBalanceError("Opening full-release principal lines must cover every item exactly once.")
            for line in closed:
                if (line.loan_event.event_kind != "RELEASE_RECEIPT" or line.balance_before != current[line.collateral_item_id] or
                        line.principal_settled != line.balance_before or line.balance_after != 0 or
                        line.monthly_interest_rate != rates[line.collateral_item_id]):
                    raise PawnTrancheBalanceError("Opening full-release principal lines do not reconcile.")
                current[line.collateral_item_id] = Decimal("0")
    return tuple(
        PawnPrincipalTrancheBalance(
            collateral_item_id=item_id,
            monthly_interest_rate=rates[item_id],
            initial_principal=initial[item_id],
            principal_outstanding=current[item_id],
        )
        for item_id in ordered_ids
    )


__all__ = [
    "PawnPrincipalTrancheBalance",
    "PawnTrancheBalanceError",
    "get_pawn_principal_tranche_balances",
]
