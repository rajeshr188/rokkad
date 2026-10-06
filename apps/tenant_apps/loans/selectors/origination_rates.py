"""Workspace quote evidence and eligibility for new lending decisions."""
from copy import deepcopy

from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.domain import ValuationMethod
from apps.tenant_apps.loans.domain.valuation_freshness import evidence_freshness
from apps.tenant_apps.rates.facade import RATE_FOUND, get_latest_commodity_valuation_rate


LEGACY_RULE = "same-day-origination-v1"
RULE = "quote-age-origination-v2"


def requires_quotes(method):
    return ValuationMethod(method) != ValuationMethod.LATEST_APPRAISAL


def quote_evidence(rate):
    evidence = {
        "rate_id": rate.pk, "workspace_id": rate.workspace_id,
        "metal": rate.metal, "currency": rate.currency, "purity": rate.purity,
        "unit": "gram", "buying_rate": str(rate.buying_rate),
        "effective_at": rate.effective_at.isoformat(),
        "recorded_at": rate.timestamp.isoformat(),
        "recorded_by_id": rate.recorded_by_id,
        "source_id": rate.rate_source_id,
        "source_snapshot": deepcopy(rate.source_snapshot),
    }
    if rate.confirmed_from_id is not None:
        evidence["confirmed_from_id"] = rate.confirmed_from_id
    return evidence


def origination_quote_cutoff(loan_date, *, at=None):
    at = at or timezone.now()
    return at if loan_date == timezone.localdate(at) else loan_date


def get_origination_quote_rows(*, workspace_id, loan_date, metals, at=None, maximum_age_days=None):
    from apps.tenant_apps.loans.services.origination_settings import maximum_quote_age_days
    if current_workspace_id() != workspace_id:
        raise ValueError("Origination quotes require the active Workspace.")
    at = at or timezone.now()
    today = timezone.localdate(at)
    limit = maximum_quote_age_days(workspace_id) if maximum_age_days is None else maximum_age_days
    # A current-day form must not suggest a quote that takes effect later today.
    cutoff = origination_quote_cutoff(loan_date, at=at)
    rows = []
    for metal in dict.fromkeys(metals):
        if metal not in {"GOLD", "SILVER"}:
            raise ValueError("Unsupported collateral metal.")
        lookup = get_latest_commodity_valuation_rate(commodity_code=metal, as_of=cutoff)
        rate = lookup.rate
        usable = lookup.status == RATE_FOUND and rate.buying_rate > 0
        status, age = evidence_freshness(value=rate.buying_rate if rate else None,
            effective_date=timezone.localdate(rate.effective_at) if rate else None,
            as_of_date=today, maximum_age_days=limit)
        fresh = bool(usable and status == "CURRENT" and rate.effective_at <= at)
        rows.append({
            "metal": metal, "label": metal.title(), "rate": rate,
            "usable": usable, "fresh": fresh,
            "age_days": age, "maximum_age_days": limit, "freshness": status,
            "evidence": quote_evidence(rate) if rate else None,
        })
    return rows


def require_fresh_quotes(rows):
    for row in rows:
        if not row["fresh"]:
            requirement = ("a positive same-day buying quote" if row["maximum_age_days"] == 0 else
                f"a positive buying quote no older than {row['maximum_age_days']} calendar days")
            raise ValueError(
                f"{row['label']} requires {requirement} before approval. "
                "Open Rates, record a current quote, then review the loan again."
            )


def require_current_origination_date(value, *, label="Loan", at=None):
    today = timezone.localdate(at or timezone.now())
    if value != today:
        raise ValueError(
            f"{label} date must be today ({today:%d/%m/%Y}) when using metal quotes; "
            f"the selected date is {value:%d/%m/%Y}. "
            "Adding today's price does not change the loan date. "
            "If the money is being handed over today, edit the draft's loan date, "
            "save it and review the recalculated terms. If the money was already "
            "handed over on the original date, keep that date and contact your "
            "administrator to use Record completed payout."
        )


def assert_approved_quotes_current(*, workspace_id, method, evidence, effective_date):
    """Validate frozen identities; never replace approved monetary values."""
    from apps.tenant_apps.loans.services.origination_settings import maximum_quote_age_days
    if not requires_quotes(method):
        return
    if (not isinstance(evidence, dict) or evidence.get("rule") not in {RULE, LEGACY_RULE}
            or evidence.get("valuation_method") != ValuationMethod(method).value
            or not isinstance(evidence.get("quotes"), dict) or not evidence["quotes"]):
        raise ValueError("Approval lacks market quote evidence. Return to draft and approve again.")
    at = timezone.now()
    require_current_origination_date(effective_date, label="Disbursal", at=at)
    limit = 0 if evidence["rule"] == LEGACY_RULE else evidence.get("maximum_quote_age_days")
    if evidence["rule"] == RULE and (type(limit) is not int or not 0 <= limit <= 32767
            or evidence.get("age_basis") != "LOCAL_CALENDAR_DAYS"):
        raise ValueError("Approval lacks quote-age evidence. Return to draft and approve again.")
    if evidence["rule"] == RULE:
        try:
            evaluated_at = parse_datetime(evidence["evaluated_at"])
            ages = evidence["quote_ages_days"]
            valid_ages = (timezone.is_aware(evaluated_at) and evaluated_at <= at
                and isinstance(ages, dict) and set(ages) == set(evidence["quotes"])
                and all(type(ages[metal]) is int and 0 <= ages[metal] <= limit
                    and ages[metal] == (timezone.localdate(evaluated_at) - timezone.localdate(
                        parse_datetime(quote["effective_at"]))).days
                    for metal, quote in evidence["quotes"].items()))
        except (KeyError, TypeError, ValueError, AttributeError):
            valid_ages = False
        if not valid_ages:
            raise ValueError("Approval lacks valid quote-age evidence. Return to draft and approve again.")
    rows = get_origination_quote_rows(workspace_id=workspace_id,
        loan_date=timezone.localdate(at), metals=tuple(evidence["quotes"]), at=at,
        maximum_age_days=limit)
    try:
        if evidence.get("loan_date") != timezone.localdate(at).isoformat():
            raise ValueError("The approved loan date is no longer today.")
        if evidence["rule"] == RULE and maximum_quote_age_days(workspace_id) != limit:
            raise ValueError("The Workspace quote-age rule changed.")
        require_fresh_quotes(rows)
        if {row["metal"]: row["evidence"] for row in rows} != evidence["quotes"]:
            raise ValueError("The selected market quote changed.")
    except ValueError as exc:
        raise ValueError("Approved quotes are outdated. Return to draft, review the current quotes and quote-age rule, and approve again.") from exc
