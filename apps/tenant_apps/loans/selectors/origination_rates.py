"""Workspace quote evidence and eligibility for new lending decisions."""
from copy import deepcopy

from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.domain import ValuationMethod
from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate


RULE = "same-day-origination-v1"


def requires_quotes(method):
    return ValuationMethod(method) != ValuationMethod.LATEST_APPRAISAL


def quote_evidence(rate):
    return {
        "rate_id": rate.pk, "workspace_id": rate.workspace_id,
        "metal": rate.metal, "currency": rate.currency, "purity": rate.purity,
        "unit": "gram", "buying_rate": str(rate.buying_rate),
        "effective_at": rate.effective_at.isoformat(),
        "recorded_at": rate.timestamp.isoformat(),
        "recorded_by_id": rate.recorded_by_id,
        "source_id": rate.rate_source_id,
        "source_snapshot": deepcopy(rate.source_snapshot),
    }


def origination_quote_cutoff(loan_date, *, at=None):
    at = at or timezone.now()
    return at if loan_date == timezone.localdate(at) else loan_date


def get_origination_quote_rows(*, workspace_id, loan_date, metals, at=None):
    if current_workspace_id() != workspace_id:
        raise ValueError("Origination quotes require the active Workspace.")
    at = at or timezone.now()
    today = timezone.localdate(at)
    # A current-day form must not suggest a quote that takes effect later today.
    cutoff = origination_quote_cutoff(loan_date, at=at)
    rows = []
    for metal in dict.fromkeys(metals):
        if metal not in {"GOLD", "SILVER"}:
            raise ValueError("Unsupported collateral metal.")
        lookup = get_latest_commodity_valuation_rate(commodity_code=metal, as_of=cutoff)
        rate = lookup.rate
        usable = lookup.status == RATE_FOUND and rate.buying_rate > 0
        fresh = bool(usable and timezone.localdate(rate.effective_at) == today
                     and rate.effective_at <= at)
        rows.append({
            "metal": metal, "label": metal.title(), "rate": rate,
            "usable": usable, "fresh": fresh,
            "age_days": (loan_date - timezone.localdate(rate.effective_at)).days if rate else None,
            "evidence": quote_evidence(rate) if rate else None,
        })
    return rows


def require_fresh_quotes(rows):
    for row in rows:
        if not row["fresh"]:
            raise ValueError(
                f"{row['label']} requires a positive same-day buying quote before approval. "
                "Open Rates, add today's quote, then review the loan again."
            )


def require_current_origination_date(value, *, label="Loan", at=None):
    if value != timezone.localdate(at or timezone.now()):
        raise ValueError(
            f"{label} date must be today when using metal quotes. "
            "Return to the draft and review today's terms; historical entry needs a separate workflow."
        )


def assert_approved_quotes_current(*, workspace_id, method, evidence, effective_date):
    """Validate frozen identities; never replace approved monetary values."""
    if not requires_quotes(method):
        return
    if (not isinstance(evidence, dict) or evidence.get("rule") != RULE
            or evidence.get("valuation_method") != ValuationMethod(method).value
            or not isinstance(evidence.get("quotes"), dict) or not evidence["quotes"]):
        raise ValueError("Approval lacks market quote evidence. Return to draft and approve again.")
    at = timezone.now()
    require_current_origination_date(effective_date, label="Disbursal", at=at)
    rows = get_origination_quote_rows(workspace_id=workspace_id,
        loan_date=timezone.localdate(at), metals=tuple(evidence["quotes"]), at=at)
    try:
        require_fresh_quotes(rows)
        if {row["metal"]: row["evidence"] for row in rows} != evidence["quotes"]:
            raise ValueError("The selected market quote changed.")
    except ValueError as exc:
        raise ValueError("Approved quotes are outdated. Return to draft, review today's quotes and approve again.") from exc
