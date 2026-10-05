"""Read-only dated dependencies shared by servicing and correction reviews."""
from dataclasses import dataclass


@dataclass(frozen=True)
class ServicingDependencies:
    events: tuple
    accruals: tuple
    custody: tuple

    def evidence(self):
        return dict(events=list(self.events), accruals=list(self.accruals), custody=list(self.custody))


def servicing_dependencies(loan, *, effective_date):
    """An inventory, never permission to insert before or replay these records.

    Existing lifecycle correction commands decide which dependency graphs they can
    compensate. Include payload hashes and custody facts in the signed review so
    a movement after preview requires another review even without a money event.
    """
    events = tuple(dict(id=e.pk, kind=e.event_kind, date=e.effective_date.isoformat(),
        fingerprint=e.payload_fingerprint) for e in loan.loan_events.filter(
            effective_date__gte=effective_date).order_by("effective_date", "pk"))
    accruals = tuple(dict(id=a.pk, event=a.loan_event_id, through=a.period_end.isoformat())
        for a in loan.interest_accruals.filter(period_end__gt=effective_date).order_by("pk"))
    from apps.tenant_apps.loans.models import PawnCollateralCustodyEvent
    custody = tuple(dict(id=c.pk, item=c.collateral_item_id, date=c.effective_date.isoformat(),
        from_state=c.from_state, to_state=c.to_state) for c in PawnCollateralCustodyEvent.objects.filter(
            collateral_item__loan=loan, effective_date__gte=effective_date).order_by("pk"))
    return ServicingDependencies(events, accruals, custody)
