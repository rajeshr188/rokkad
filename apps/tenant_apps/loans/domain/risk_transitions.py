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
        elif old.get("status") == "ERROR" and new.get("status") == "CURRENT": kind = "ASSESSMENT_ERROR_RECOVERED"
        else: kind = "STATUS_CHANGED"
        transitions.append(RiskTransition(kind, old.get("status"), new.get("status")))
    if new.get("status") != "CURRENT":
        return tuple(transitions)  # Failed/outdated evidence cannot demonstrate a cure.
    old_dpd, new_dpd = old.get("days_past_due"), new.get("days_past_due")
    old_bucket, new_bucket = _dpd_bucket(old_dpd), _dpd_bucket(new_dpd)
    if new_bucket is not None and old_bucket != new_bucket and not (old_bucket is None and new_bucket == "CURRENT"):
        kind = "DELINQUENCY_CURED" if new_bucket == "CURRENT" else "DELINQUENCY_ENTERED" if old_bucket in (None, "CURRENT") else "DPD_BUCKET_CHANGED"
        transitions.append(RiskTransition(kind, {"dpd": old_dpd, "bucket": old_bucket}, {"dpd": new_dpd, "bucket": new_bucket}))
    for flag, entered, exited in (
        ("MATURITY_APPROACHING", "MATURITY_WARNING_ENTERED", "MATURITY_WARNING_EXITED"),
        ("PAST_MATURITY", "PAST_MATURITY_ENTERED", "PAST_MATURITY_CURED"),
        ("VALUATION_UNKNOWN", "VALUATION_ERROR_ENTERED", "VALUATION_ERROR_CURED"),
    ):
        was, now = flag in set(old.get("flags") or ()), flag in set(new.get("flags") or ())
        if was != now: transitions.append(RiskTransition(entered if now else exited, was, now))
    old_ltv, new_ltv = _ltv_rank(old), _ltv_rank(new)
    if new_ltv is not None:
        for rank, flag in ((1, "LTV_WARNING"), (2, "LTV_BREACH"), (3, "LTV_CRITICAL")):
            if new_ltv == rank and old_ltv != rank:
                transitions.append(RiskTransition(flag + "_ENTERED", False, True))
            if old_ltv == rank and new_ltv < rank:
                transitions.append(RiskTransition(flag + "_CURED", True, False))
    _changed(transitions, "PERFORMANCE_CHANGED", old, new, "performance_class")
    _changed(transitions, "SEVERITY_CHANGED", old, new, "severity")
    _changed(transitions, "POLICY_CHANGED", old, new, "policy_identity")
    return tuple(transitions)


def _changed(target, event_type, old, new, key):
    if old.get(key) != new.get(key): target.append(RiskTransition(event_type, old.get(key), new.get(key)))


def _dpd_bucket(value):
    if value is None: return None
    if value <= 0: return "CURRENT"
    if value < 30: return "DPD_1_29"
    if value < 60: return "DPD_30_59"
    if value < 90: return "DPD_60_89"
    return "DPD_90_PLUS"


def _ltv_rank(value):
    flags = set(value.get("flags") or ())
    if value.get("status") == "ERROR" or "VALUATION_UNKNOWN" in flags:
        return None
    if "ltv_ratio" in value and value["ltv_ratio"] is None:
        return None
    if "LTV_CRITICAL" in flags: return 3
    if "LTV_BREACH" in flags: return 2
    if "LTV_WARNING" in flags: return 1
    return 0


def _summary(value):
    return {key: value.get(key) for key in ("status", "days_past_due", "performance_class", "severity", "policy_identity")}
