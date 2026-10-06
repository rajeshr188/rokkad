"""Explicit admission of a native payout already made on an earlier date.

This is not legacy-data import and never changes the loan date or pays cash.
"""
from copy import deepcopy
from datetime import datetime, time, timedelta

from django.utils import timezone
from django.core.exceptions import PermissionDenied
from apps.tenancy.context import current_workspace_id

from apps.tenant_apps.loans.models import (
    PawnLoanEconomicPolicy, PawnMetalInterestRatePolicy, PawnLoanFeePolicy,
)
from apps.tenant_apps.loans.selectors.origination_rates import quote_evidence, requires_quotes
from apps.tenant_apps.rates.models import Rate
from .action_access import require_loan_action


RULE = "earlier-payout-v1"
ACTIONS = ("workspace.settings.manage", "data.edit", "loan.approve", "loan.disburse")


def authorize(loan, actor):
    if current_workspace_id() != loan.workspace_id:
        raise PermissionDenied("Earlier payout recording requires the active Workspace.")
    require_loan_action(loan, actor, *ACTIONS)


def day_end(day):
    return timezone.make_aware(datetime.combine(day + timedelta(days=1), time.min))


def require_earlier_native_draft(loan):
    if loan.state != "DRAFT" or loan.loan_date >= timezone.localdate():
        raise ValueError("Record an earlier payout requires a draft with its actual payout date before today.")
    if loan.loan_events.exclude(event_kind__in=("DISBURSAL", "REVERSAL")).exists():
        raise ValueError("Use this action only for native origination or a fully reversed native disbursal.")
    if loan.disbursal_snapshots.exclude(basis="APPROVED").exists():
        raise ValueError("Recorded or opening origins require their supported history correction workflow.")
    if loan.loan_events.filter(event_kind="DISBURSAL", reversed_by_event__isnull=True).exists():
        raise ValueError("An unreversed payout is already recorded for this loan.")


def historical_basis(loan):
    """Use an earlier approval where available; otherwise dated, existing evidence.

No client-supplied policy or quote IDs are accepted. A backdated quote recorded
after the actual day is not contemporaneous evidence.
"""
    require_earlier_native_draft(loan)
    cutoff = day_end(loan.loan_date)
    basis = None
    for approval in loan.approval_snapshots.order_by("-version"):
        payload = approval.payload
        if (payload.get("loan_date") == loan.loan_date.isoformat()
                and (approval.approved_at < cutoff or payload.get("earlier_payout", {}).get("rule") == RULE)
                and payload.get("license_id") == loan.license_id
                and payload.get("series_id") == loan.series_id
                and payload.get("collateral_economics")):
            basis = approval
            break
    return {"approval": basis, "cutoff": cutoff, "loan_date": loan.loan_date,
            "workspace_id": loan.workspace_id}


def historical_policies(context, collateral, *, license_id, series_id):
    """Re-use frozen policy identities; fallback resolution is cutoff-bounded."""
    from .economic_policies import (
        resolve_pawn_loan_economic_policy, resolve_pawn_metal_interest_rate_policy,
        resolve_pawn_loan_fee_policies,
    )
    kwargs = dict(workspace_id=context["workspace_id"], license_id=license_id,
                  as_of_date=context["loan_date"], recorded_before=context["cutoff"])
    basis = context["approval"]
    if basis is None:
        return (resolve_pawn_loan_economic_policy(**kwargs, series_id=series_id),
                tuple(resolve_pawn_metal_interest_rate_policy(**kwargs, series_id=series_id,
                    metal=item.metal) for item in collateral),
                resolve_pawn_loan_fee_policies(**kwargs))
    frozen = basis.payload["collateral_economics"]
    try:
        policy = PawnLoanEconomicPolicy.objects.get(pk=frozen["economic_policy_id"],
            workspace_id=context["workspace_id"])
        ids = {row["metal"]: row["interest_rate_policy_id"] for row in frozen["tranches"]}
        rates = tuple(PawnMetalInterestRatePolicy.objects.get(pk=ids[item.metal],
            workspace_id=context["workspace_id"], metal=item.metal) for item in collateral)
        fees = tuple(PawnLoanFeePolicy.objects.get(pk=row["fee_policy_id"],
            workspace_id=context["workspace_id"]) for row in frozen["fees"])
    except (KeyError, PawnLoanEconomicPolicy.DoesNotExist, PawnMetalInterestRatePolicy.DoesNotExist,
            PawnLoanFeePolicy.DoesNotExist) as exc:
        raise ValueError("Earlier approval lacks the policies for these collateral items. Administrator review is required.") from exc
    for row in (policy, *rates, *fees):
        if (row.license_id not in (None, license_id)
                or getattr(row, "series_id", None) not in (None, series_id)
                or row.effective_from > context["loan_date"]
                or (row.effective_until and row.effective_until < context["loan_date"])):
            raise ValueError("Earlier approval's policy does not cover the actual payout date and series.")
    def unchanged(row, values, fields):
        for field, key in fields:
            if key not in values or getattr(row, field) != row._meta.get_field(field).to_python(values[key]):
                raise ValueError("An earlier approved policy was modified. Administrator evidence review is required.")
    unchanged(policy, frozen, [(name, name) for name in (
        "valuation_method", "maximum_ltv_ratio", "advance_interest_periods", "interest_method",
        "partial_month_method", "partial_month_cutoff_days", "partial_month_lower_fraction",
        "capitalization_interval_periods", "rounding_method", "currency_quantum")])
    if policy.minimum_first_month != frozen.get("minimum_first_month", False):
        raise ValueError("The earlier approved minimum first-month rule was modified.")
    tranches = {row["metal"]: row for row in frozen["tranches"]}
    for item, rate in zip(collateral, rates, strict=True):
        values = tranches[item.metal]
        baseline = "policy_monthly_interest_rate"
        # Pre-override approvals froze the policy-selected rate directly.
        if baseline not in values and values.get("interest_rate_override") is None:
            baseline = "monthly_interest_rate"
        unchanged(rate, values, [("monthly_interest_rate", baseline)])
    for fee, values in zip(fees, frozen["fees"], strict=True):
        unchanged(fee, values, [("code", "code"), ("name", "name"),
            ("calculation_type", "calculation_type"), ("value", "policy_value"),
            ("deducted_at_disbursal", "deducted_at_disbursal")])
    return policy, rates, fees


def historical_quotes(context, *, method, metals):
    if not requires_quotes(method):
        return {}
    basis = context["approval"]
    frozen = basis.payload.get("origination_rates", {}).get("quotes", {}) if basis else {}
    result = {}
    for metal in dict.fromkeys(metals):
        rows = Rate.objects.filter(workspace_id=context["workspace_id"], metal=metal.title(),
            currency="INR", purity="24k", is_withdrawal=False, successor__isnull=True,
            effective_at__date=context["loan_date"], timestamp__lt=context["cutoff"])
        if basis:
            expected = frozen.get(metal)
            rate = rows.filter(pk=(expected or {}).get("rate_id")).first()
            if rate is None or quote_evidence(rate) != expected:
                raise ValueError(f"{metal.title()}'s earlier approved quote is missing, corrected or withdrawn. Administrator evidence review is required.")
        else:
            rate = rows.order_by("-effective_at", "-timestamp", "-pk").first()
        if rate is None or rate.buying_rate <= 0:
            raise ValueError(f"{metal.title()} needs an existing positive quote recorded on the actual payout date. Today's price cannot be used for this earlier payout.")
        result[metal] = quote_evidence(rate)
    return result


def recording_evidence(loan, context, *, actor, reason, review_digest):
    authorize(loan, actor)
    reason = (reason or "").strip()
    if not reason or len(reason) > 500:
        raise ValueError("Explain the earlier payout or correction in 1–500 characters.")
    return {"rule": RULE, "actual_payout_date": loan.loan_date.isoformat(),
            "recorded_by_id": actor.pk, "recorded_at": timezone.now().isoformat(),
            "reason": reason, "review_digest": review_digest,
            "basis_approval_id": context["approval"].pk if context["approval"] else None}


def assert_historical_approval(loan, *, actor, evidence, recording, effective_date):
    authorize(loan, actor)
    if (not isinstance(recording, dict) or recording.get("rule") != RULE
            or recording.get("recorded_by_id") != actor.pk or not recording.get("reason")
            or recording.get("actual_payout_date") != effective_date.isoformat()
            or effective_date != loan.loan_date or effective_date >= timezone.localdate()
            or not isinstance(evidence, dict) or evidence.get("rule") != RULE
            or evidence.get("loan_date") != effective_date.isoformat()):
        raise ValueError("Use the authorized earlier-payout review to record this historical approval.")
    # Revalidate original identities without ever substituting today's quote.
    quotes = deepcopy(evidence.get("quotes", {}))
    if requires_quotes(evidence["valuation_method"]) and not quotes:
        raise ValueError("Historical approval is missing its quote evidence.")
    for metal, expected in quotes.items():
        rate = Rate.objects.filter(workspace_id=loan.workspace_id, pk=expected.get("rate_id"),
            metal=metal.title(), currency="INR", purity="24k", is_withdrawal=False,
            successor__isnull=True, effective_at__date=effective_date,
            timestamp__lt=day_end(effective_date)).first()
        if rate is None or rate.buying_rate <= 0 or quote_evidence(rate) != expected:
            raise ValueError("Historical quote evidence changed. Review the earlier payout again.")
