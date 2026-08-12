from dataclasses import dataclass


@dataclass(frozen=True)
class RiskTransition:
    event_type: str
    old_value: object
    new_value: object


def detect_risk_transitions(old, new):
    if old is None:
        event_type = "ASSESSMENT_ERROR_ENTERED" if new.get("status") == "ERROR" else "ASSESSMENT_INITIALIZED"
        return (RiskTransition(event_type, None, _summary(new)),)
    transitions = []
    if old.get("status") != new.get("status"):
        if new.get("status") == "ERROR": kind = "ASSESSMENT_ERROR_ENTERED"
        elif old.get("status") == "ERROR": kind = "ASSESSMENT_ERROR_RECOVERED"
        else: kind = "STATUS_CHANGED"
        transitions.append(RiskTransition(kind, old.get("status"), new.get("status")))
    old_dpd, new_dpd = old.get("days_past_due"), new.get("days_past_due")
    old_bucket, new_bucket = _dpd_bucket(old_dpd), _dpd_bucket(new_dpd)
    if old_bucket != new_bucket:
        kind = "DELINQUENCY_CURED" if new_bucket == "CURRENT" else "DELINQUENCY_ENTERED" if old_bucket == "CURRENT" else "DPD_BUCKET_CHANGED"
        transitions.append(RiskTransition(kind, {"dpd": old_dpd, "bucket": old_bucket}, {"dpd": new_dpd, "bucket": new_bucket}))
    for flag, entered, exited in (
        ("MATURITY_APPROACHING", "MATURITY_WARNING_ENTERED", "MATURITY_WARNING_EXITED"),
        ("PAST_MATURITY", "PAST_MATURITY_ENTERED", "PAST_MATURITY_CURED"),
        ("LTV_WARNING", "LTV_WARNING_ENTERED", "LTV_WARNING_CURED"),
        ("LTV_BREACH", "LTV_BREACH_ENTERED", "LTV_BREACH_CURED"),
        ("LTV_CRITICAL", "LTV_CRITICAL_ENTERED", "LTV_CRITICAL_CURED"),
        ("VALUATION_UNKNOWN", "VALUATION_ERROR_ENTERED", "VALUATION_ERROR_CURED"),
    ):
        was, now = flag in set(old.get("flags") or ()), flag in set(new.get("flags") or ())
        if was != now: transitions.append(RiskTransition(entered if now else exited, was, now))
    _changed(transitions, "PERFORMANCE_CHANGED", old, new, "performance_class")
    _changed(transitions, "SEVERITY_CHANGED", old, new, "severity")
    _changed(transitions, "POLICY_CHANGED", old, new, "policy_identity")
    return tuple(transitions)


def _changed(target, event_type, old, new, key):
    if old.get(key) != new.get(key): target.append(RiskTransition(event_type, old.get(key), new.get(key)))


def _dpd_bucket(value):
    value = value or 0
    if value <= 0: return "CURRENT"
    if value < 30: return "DPD_1_29"
    if value < 60: return "DPD_30_59"
    if value < 90: return "DPD_60_89"
    return "DPD_90_PLUS"


def _summary(value):
    return {key: value.get(key) for key in ("status", "days_past_due", "performance_class", "severity", "policy_identity")}
