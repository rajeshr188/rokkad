"""Select an effective disbursal without treating reversed attempts as live."""

from django.db.models import Q


def effective_disbursal_snapshot(loan, *, as_of_date=None):
    snapshots = loan.disbursal_snapshots.select_related("loan_event", "policy_snapshot")
    active = Q(loan_event__reversed_by_event__isnull=True)
    if as_of_date is not None:
        snapshots = snapshots.filter(loan_event__effective_date__lte=as_of_date)
        active |= Q(loan_event__reversed_by_event__effective_date__gt=as_of_date)
    return snapshots.filter(active).order_by("-loan_event__effective_date", "-loan_event_id").first()
