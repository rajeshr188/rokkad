from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import hashlib
import json


@dataclass(frozen=True)
class RiskPolicy:
    identity: str
    maturity_warning_days: int
    dpd_watch_threshold: int
    dpd_substandard_threshold: int
    ltv_warning_ratio: Decimal
    ltv_breach_ratio: Decimal
    ltv_critical_ratio: Decimal


@dataclass(frozen=True)
class PawnLoanRiskAssessment:
    as_of_date: date
    days_to_maturity: int
    performance_class: str
    flags: tuple[str, ...]
    severity: str
    action_hint: str
    explanations: tuple[str, ...]
    policy_identity: str
    fingerprint: str


def assess_pawn_loan_risk(*, as_of_date, maturity_date, days_past_due, ltv_ratio, valuation_blockers=(), accounting_variance=False, policy):
    flags, explanations = [], []
    days_to_maturity = (maturity_date - as_of_date).days
    if days_to_maturity < 0:
        flags.append("PAST_MATURITY"); explanations.append(f"Contract maturity passed {-days_to_maturity} day(s) ago.")
    elif days_to_maturity <= policy.maturity_warning_days:
        flags.append("MATURITY_APPROACHING"); explanations.append(f"Contract matures in {days_to_maturity} day(s).")
    if days_past_due >= policy.dpd_substandard_threshold:
        performance = "SUBSTANDARD"; flags.append("DPD_SUBSTANDARD"); explanations.append(f"DPD {days_past_due} reached the substandard threshold.")
    elif days_past_due >= policy.dpd_watch_threshold:
        performance = "WATCH"; flags.append("PAYMENT_OVERDUE"); explanations.append(f"Oldest unpaid obligation is {days_past_due} day(s) past due.")
    else:
        performance = "STANDARD"
    if valuation_blockers:
        flags.append("VALUATION_UNKNOWN"); explanations.append("Collateral valuation is unavailable: " + ", ".join(valuation_blockers) + ".")
    elif ltv_ratio is not None:
        if ltv_ratio >= policy.ltv_critical_ratio: code = "LTV_CRITICAL"
        elif ltv_ratio > policy.ltv_breach_ratio: code = "LTV_BREACH"
        elif ltv_ratio >= policy.ltv_warning_ratio: code = "LTV_WARNING"
        else: code = None
        if code:
            flags.append(code); explanations.append(f"Monitoring LTV {ltv_ratio} triggered {code.lower().replace('_', ' ')}.")
    if accounting_variance:
        flags.append("ACCOUNTING_VARIANCE"); explanations.append("Contractual and legacy/accounting overdue interpretations differ.")
    severity = _severity(flags)
    action = {"CRITICAL": "IMMEDIATE_REVIEW", "HIGH": "PRIORITY_REVIEW", "MEDIUM": "MONITOR", "LOW": "NONE"}[severity]
    payload = {"as_of": as_of_date.isoformat(), "maturity": maturity_date.isoformat(), "dpd": days_past_due, "ltv": str(ltv_ratio) if ltv_ratio is not None else None, "blockers": list(valuation_blockers), "variance": accounting_variance, "policy": policy.identity, "flags": flags}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return PawnLoanRiskAssessment(as_of_date, days_to_maturity, performance, tuple(flags), severity, action, tuple(explanations), policy.identity, fingerprint)


def _severity(flags):
    values = set(flags)
    if values & {"LTV_CRITICAL", "DPD_SUBSTANDARD"}: return "CRITICAL"
    if values & {"LTV_BREACH", "VALUATION_UNKNOWN", "ACCOUNTING_VARIANCE", "PAST_MATURITY"}: return "HIGH"
    if values & {"LTV_WARNING", "PAYMENT_OVERDUE", "MATURITY_APPROACHING"}: return "MEDIUM"
    return "LOW"
