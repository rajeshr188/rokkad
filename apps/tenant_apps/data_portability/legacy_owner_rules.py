"""Explicit source-scoped owner attestations used only by offline preparation."""
from datetime import date
from decimal import Decimal, localcontext

from apps.tenant_apps.loans.services.legacy_interest import aggregate_collection_interest, collection_interest

from .legacy_preview import number
from .parsers import PortabilityError

PROFILE = "jcl-owner/1"
COLLECTION_PROFILE = "jcl-owner/2"
NAMESPACE = "6ca968d6-2647-4dbb-8e39-24f0c1a12ed6"
EVIDENCE = "owner-clarifications-2026-09-12:jcl-net-weight"
MATURITY_EVIDENCE = "owner-clarifications-2026-09-12:jcl-missing-maturity-three-months"


def maturity_tenure(summary, facts):
    """Apply the owner's jcl migration fallback without changing source facts."""
    check_profile(summary, COLLECTION_PROFILE)
    raw = facts.get("tenure")
    tenure = number(raw)
    if raw in (None, "") or tenure == 0:
        return 3, MATURITY_EVIDENCE
    if tenure is None or tenure != tenure.to_integral_value() or not 1 <= tenure <= 1200:
        raise PortabilityError("Invalid source tenure requires review; the fallback is only for missing tenure.")
    return int(tenure), None


def check_profile(summary, profile):
    if profile is not None and (profile not in {PROFILE, COLLECTION_PROFILE} or summary.get("source_namespace") != NAMESPACE or
                                summary.get("source_schema") != "jcl"):
        raise PortabilityError("The supported jcl owner profiles apply only to the owner-reviewed legacy namespace and jcl tenant.")


def interest_diagnostic(candidate, *, as_of, owner_profile=PROFILE):
    """Hypothetical collection under confirmed terms; never fills opening balances."""
    if owner_profile not in {PROFILE, COLLECTION_PROFILE}:
        raise PortabilityError("Unsupported owner calculation profile.")
    aggregate = owner_profile == COLLECTION_PROFILE
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
