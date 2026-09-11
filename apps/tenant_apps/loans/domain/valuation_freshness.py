"""Age limits are inclusive local-calendar-day limits, not elapsed hours."""
from decimal import Decimal

def evidence_freshness(*, value, effective_date, as_of_date, maximum_age_days):
    if value is None or effective_date is None:
        return "MISSING", None
    age = (as_of_date - effective_date).days
    if not Decimal(value).is_finite() or value <= 0:
        return "INVALID", age
    if age < 0:
        return "FUTURE", age
    if maximum_age_days is None:
        return "UNCONFIGURED", age
    return ("CURRENT" if age <= maximum_age_days else "STALE"), age
