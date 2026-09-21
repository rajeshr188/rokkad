"""Explicit source-scoped owner attestations used only by offline preparation."""
from datetime import date
from decimal import Decimal, localcontext

from apps.tenant_apps.loans.services.legacy_interest import AGGREGATE_RULE, aggregate_collection_interest, collection_interest

from .legacy_preview import number
from .parsers import PortabilityError

PROFILE = "jcl-owner/1"
COLLECTION_PROFILE = "jcl-owner/2"
NAMESPACE = "6ca968d6-2647-4dbb-8e39-24f0c1a12ed6"
EVIDENCE = "owner-clarifications-2026-09-12:jcl-net-weight"
MATURITY_EVIDENCE = "owner-clarifications-2026-09-12:jcl-missing-maturity-three-months"
LINODE_TERMS_PROFILE = "linode-owner-terms/1"
LINODE_TERMS_EVIDENCE = "owner-clarifications-2026-09-21:jsk-lakshmi-same-interest-and-maturity-as-jcl"
LINODE_PROFILE = "linode-owner/1"
LINODE_WEIGHT_EVIDENCE = "owner-clarifications-2026-09-21:jcl-jsk-lakshmi-net-weight"


def maturity_tenure(summary, facts, *, owner_profile=COLLECTION_PROFILE):
    """Apply a scoped owner maturity decision without changing source facts."""
    if owner_profile not in {COLLECTION_PROFILE, LINODE_PROFILE}:
        raise PortabilityError("Missing maturity requires an explicitly confirmed owner profile.")
    check_profile(summary, owner_profile)
    return _maturity_tenure(facts, LINODE_TERMS_EVIDENCE if owner_profile == LINODE_PROFILE else MATURITY_EVIDENCE)


def _maturity_tenure(facts, evidence):
    raw = facts.get("tenure")
    tenure = number(raw)
    if raw in (None, "") or tenure == 0:
        return 3, evidence
    if tenure is None or tenure != tenure.to_integral_value() or not 1 <= tenure <= 1200:
        raise PortabilityError("Invalid source tenure requires review; the fallback is only for missing tenure.")
    return int(tenure), None


def linode_terms(summary, facts):
    """Owner-confirmed interest/maturity only; no balance, weight or custody claim."""
    from .legacy_profiles import get_profile

    profile = get_profile(summary.get("source_profile"))
    if summary.get("source_namespace") != NAMESPACE or summary.get("source_schema") != profile.schema:
        raise PortabilityError("Confirmed Linode terms require the reviewed installation and matching source profile.")
    tenure, fallback = _maturity_tenure(facts, LINODE_TERMS_EVIDENCE)
    return {"profile": LINODE_TERMS_PROFILE, "evidence_reference": LINODE_TERMS_EVIDENCE,
            "interest_rule": AGGREGATE_RULE, "first_month_paid_upfront": True,
            "tenure_months": tenure,
            "maturity_basis": "OWNER_MISSING_MATURITY_RULE" if fallback else "RECORDED_TENURE",
            "payment_reconciliation_required_when_present": True,
            "opening_balances_approved": False, "custody_confirmed": False}


def check_profile(summary, profile):
    if profile == LINODE_PROFILE:
        linode_terms(summary, {"tenure": "0"})  # Exact reviewed installation/schema/profile.
        return
    if profile is not None and (profile not in {PROFILE, COLLECTION_PROFILE} or summary.get("source_namespace") != NAMESPACE or
                                summary.get("source_schema") != "jcl"):
        raise PortabilityError("The supported jcl owner profiles apply only to the owner-reviewed legacy namespace and jcl tenant.")


def weight_evidence(summary, profile):
    check_profile(summary, profile)
    return LINODE_WEIGHT_EVIDENCE if profile == LINODE_PROFILE else EVIDENCE if profile else None


def interest_diagnostic(candidate, *, as_of, owner_profile=PROFILE):
    """Hypothetical collection under confirmed terms; never fills opening balances."""
    if owner_profile not in {PROFILE, COLLECTION_PROFILE, LINODE_PROFILE}:
        raise PortabilityError("Unsupported owner calculation profile.")
    aggregate = owner_profile in {COLLECTION_PROFILE, LINODE_PROFILE}
    blockers = []
    if candidate["source_state"] != "UNRELEASED":
        blockers.append("RELEASED_OUTSIDE_ACTIVE_SCOPE")
    if any(issue["severity"] == "ERROR" for issue in candidate["source_loan"]["issues"]):
        blockers.append("SOURCE_ERRORS")
    if candidate["source_payments"]:
        blockers.append("PAYMENT_TREATMENT_UNREVIEWED")
    items = candidate["source_items"]
    if not items:
        blockers.append("NO_ITEMS")
    charges = []
    with localcontext() as context:
        context.prec = 64
        for item in items:
            principal, rate, charge = [number(item["facts"][key]) for key in ("loanamount", "interestrate", "interest")]
            if (principal is None or rate is None or charge is None or principal <= 0 or rate < 0 or charge < 0 or
                    principal * rate / 100 != charge):
                blockers.append("ITEM_MONTHLY_CHARGE_UNRECONCILED")
            elif not aggregate and charge != charge.to_integral_value():
                blockers.append("FRACTIONAL_AGGREGATION_UNCONFIRMED")
            else:
                charges.append(charge)
        monthly = sum(charges, Decimal("0"))
    calculated = None
    if not blockers:
        try:
            calculator = aggregate_collection_interest if aggregate else collection_interest
            calculated = calculator(date.fromisoformat(candidate["source_original_business_date"]), as_of, monthly)
        except (TypeError, ValueError, OverflowError):
            blockers.append("UNSUPPORTED_CALCULATION_INPUT")
    return {"source_loan_id": candidate["source_loan_id"],
            "source_number": candidate["source_loan"]["facts"]["loan_id"],
            "source_sha256": candidate["source_loan"]["source_sha256"],
            "profile": owner_profile, "import_ready": False, "calculation": calculated,
            "collection_evidence": {"actual_interest_collected": None, "interest_lost": None},
            "blockers": sorted(set(blockers)),
            "assumptions": ["Original principal unchanged; first month paid upfront; no subsequent collections.",
                            ("Item monthly charges agree with stored principal and rate; round the total once for rehearsal."
                             if aggregate else "Whole-rupee item monthly charges agree with stored principal and rate.")],
            "limitations": ["Collection illustration only; not certified cutover balances or accounting accrual.",
                            "Actual collections can differ; accepted interest loss is separate, never inferred from rounding or missing receipts.",
                            "Document charges, destination setup, custody and other opening evidence remain separate."]}
