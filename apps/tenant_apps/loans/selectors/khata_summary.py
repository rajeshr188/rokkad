"""Today-only khata portfolio reads. Limits are never borrower debt."""
from decimal import Decimal, ROUND_DOWN

from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import (
    KhataAccount, KhataOperation, KhataAgreementRevision, KhataInterestAllocation,
    KhataCollateralSelection, KhataCollateralItem, KhataPolicyRevision,
)
from .khata import account_position, effective_agreement, interest_schedule, eligible_items
from apps.tenant_apps.loans.domain.khata import DrawPosition, available_draw
from .origination_rates import get_origination_quote_rows, require_fresh_quotes

ZERO = Decimal(0)
LIVE_STATES = ("DRAFT", "APPROVED", "ACTIVE", "SETTLED_RETURN_PENDING")
MONEY_FIELDS = ("principal", "interest", "due_interest", "overdue_interest", "limit", "unused")


def summary_accounts(*, workspace, borrower=None, balances_only=False, filters=None):
    if current_workspace_id() != workspace.pk:
        raise ValueError("Khata summaries require the matching Workspace context.")
    qs = KhataAccount.objects.filter(workspace=workspace)
    if borrower is not None:
        qs = qs.filter(borrower_id=borrower.pk)
    data = filters or {}
    if data.get("q"):
        qs = qs.filter(Q(account_number__icontains=data["q"]) | Q(borrower__display_name__icontains=data["q"])
            | Q(borrower__party_code__icontains=data["q"]))
    for name in ("state", "borrower", "series"):
        if data.get(name):
            qs = qs.filter(**{name: data[name]})
    if data.get("association"):
        qs = qs.filter(series__license__isnull=data["association"] == "independent")
    qs = qs.select_related("workspace", "borrower", "series__license")
    if balances_only:
        # Fold every financial source with the existing calculator. Receipt allocations
        # retain the existing corrected-source exclusion; custody counts are live reads.
        items = KhataCollateralItem.objects.filter(workspace=workspace, account_id=OuterRef("pk")).annotate(
            returned=Exists(KhataOperation.objects.filter(workspace=workspace, item_id=OuterRef("pk"),
                kind__in=("RETURN", "HANDOVER"))),
            reserved=Exists(KhataCollateralSelection.objects.filter(workspace=workspace, item_id=OuterRef("pk"),
                role="OUT", operation__corrected_by__isnull=True)),
        ).filter(returned=False)
        def count(rows):
            counts = rows.order_by().values("account_id").annotate(n=Count("pk")).values("n")
            return Coalesce(Subquery(counts), Value(0))
        return qs.annotate(summary_held_count=count(items), summary_pending_count=count(items.filter(reserved=True))).prefetch_related(
            Prefetch("operations", queryset=KhataOperation.objects.filter(kind__in=("WITHDRAW", "REVISE", "SETTLE"))
                .select_related("agreement").order_by("sequence"), to_attr="summary_operations"),
            Prefetch("agreement_revisions", queryset=KhataAgreementRevision.objects.order_by("-number"), to_attr="summary_agreements"),
            "interest_periods", Prefetch("interest_periods__allocations", queryset=KhataInterestAllocation.objects.filter(operation__corrected_by__isnull=True)),
        ).order_by("pk")
    return qs.prefetch_related(
        Prefetch("operations", queryset=KhataOperation.objects.select_related("agreement", "corrected_by", "created_by").order_by("sequence").prefetch_related(
            Prefetch("collateral_selections", queryset=KhataCollateralSelection.objects.filter(role="OUT"), to_attr="summary_selections")
        ), to_attr="summary_operations"),
        Prefetch("agreement_revisions", queryset=KhataAgreementRevision.objects.order_by("-number"), to_attr="summary_agreements"),
        "interest_periods", Prefetch("collateral", queryset=KhataCollateralItem.objects.select_related("received_operation")),
        Prefetch("interest_periods__allocations", queryset=KhataInterestAllocation.objects.filter(operation__corrected_by__isnull=True)),
    ).order_by("pk")


def account_summary(account):
    """Uses the canonical replay/calculator, including receipt compensation."""
    today = timezone.localdate()
    if hasattr(account, "summary_operations"):
        account.summary_allocations = [a for p in account.interest_periods.all() for a in p.allocations.all()]
    position = account_position(account)
    agreement = effective_agreement(account)
    if agreement is None or (account.state == "ACTIVE" and position is None):
        raise ValueError("Khata source evidence is incomplete.")
    schedule = interest_schedule(account, today) if position else []
    summary = dict(account=account, as_of=today, agreement=agreement, schedule=schedule,
        principal=position.principal if position else ZERO,
        interest=sum((r["outstanding"] for r in schedule), ZERO),
        due_interest=sum((r["outstanding"] for r in schedule if r["due_on"] <= today), ZERO),
        overdue_interest=sum((r["outstanding"] for r in schedule if r["due_on"] < today), ZERO),
        limit=position.limit if position else agreement.agreed_limit,
        unused=position.unused if position else ZERO,
        opened=position is not None,
    )
    if not all(summary[key].is_finite() and summary[key] >= 0 for key in MONEY_FIELDS):
        raise ValueError("Khata money evidence needs review.")
    summary["outstanding"] = summary["principal"] + summary["interest"]
    if hasattr(account, "summary_held_count"):
        summary.update(held_count=account.summary_held_count, pending_returns=account.summary_pending_count)
        return summary
    operations = account.summary_operations if hasattr(account, "summary_operations") else list(account.operations.all())
    returned = {op.item_id for op in operations if op.kind in ("HANDOVER", "RETURN")}
    if hasattr(account, "summary_operations"):
        corrected = {op.correction_of_id for op in operations if op.kind == "CORRECT"}
        reserved = {s.item_id for op in operations if op.pk not in corrected for s in op.summary_selections}
    else:
        reserved = set(KhataCollateralSelection.objects.filter(operation__account=account, role="OUT",
            operation__corrected_by__isnull=True).values_list("item_id", flat=True))
    summary["held_count"] = sum(item.pk not in returned for item in account.collateral.all())
    summary["pending_returns"] = len(reserved - returned)
    return summary


def collateral_cover(account, summary):
    """Read-only capacity suggestion; commands still recheck every lending gate."""
    if current_workspace_id() != account.workspace_id:
        raise ValueError("Khata cover requires the matching Workspace context.")
    policy = KhataPolicyRevision.objects.filter(workspace_id=account.workspace_id).order_by("-number").first()
    result = dict(value=None, capacity=None, backing=None, current_ltv=None, undercovered=False,
        exchange_policy=policy.exchange if policy else "WARN", overdue_policy=policy.overdue if policy else "WARN",
        reason="", quotes=[])
    if summary.get("unavailable"):
        result["reason"] = "Balance evidence needs review."
        return result
    if hasattr(account, "summary_held_count"):
        items = list(eligible_items(account))
    else:
        returned = {op.item_id for op in account.summary_operations if op.kind in ("RETURN", "HANDOVER")}
        corrected = {op.correction_of_id for op in account.summary_operations if op.kind == "CORRECT"}
        reserved = {s.item_id for op in account.summary_operations if op.pk not in corrected for s in op.summary_selections}
        items = [item for item in account.collateral.all() if item.pk not in returned | reserved]
    try:
        rows = get_origination_quote_rows(workspace_id=account.workspace_id, loan_date=timezone.localdate(),
            metals=[item.metal for item in items])
        require_fresh_quotes(rows)
    except ValueError:
        result["reason"] = "A positive same-day approved price is required for every eligible metal."
        return result
    prices = {row["metal"]: row["rate"].buying_rate for row in rows}
    result["quotes"] = [row["evidence"] for row in rows]
    value = sum(((prices[item.metal] * item.net_weight * item.purity / 100).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
        for item in items), ZERO)
    terms = summary["agreement"]
    backing = (value * terms.ltv).quantize(Decimal("0.01"), rounding=ROUND_DOWN)
    position = account_position(account) or DrawPosition(terms.agreed_limit, ZERO, terms.agreed_limit)
    try:
        capacity = available_draw(position, collateral_value=value, ltv=terms.ltv)
    except ValueError:
        result["reason"] = "Collateral values exceed the supported calculation bounds."
        return result
    result.update(value=value, capacity=capacity, backing=backing,
        current_ltv=summary["principal"] / value * 100 if value else (ZERO if not summary["principal"] else None),
        agreed_ltv=terms.ltv * 100, undercovered=summary["principal"] > backing)
    if account.state not in ("APPROVED", "ACTIVE"):
        result["capacity"] = ZERO
        result["reason"] = "Withdrawals require opening approval or an active agreement, and all command checks."
    elif result["overdue_policy"] == "BLOCK" and summary["overdue_interest"]:
        result["capacity"] = ZERO
        result["reason"] = "Overdue interest blocks further withdrawals and exchanges."
    elif not account.series.is_active or account.borrower.status != "ACTIVE":
        result["capacity"] = ZERO
        result["reason"] = "Series or borrower is unavailable for new lending."
    elif account.series.license_id:
        license = account.series.license
        day = timezone.localdate()
        if not license.is_active or license.is_legacy_reference or license.issued_on > day or license.is_expired(day):
            result["capacity"] = ZERO
            result["reason"] = "The associated licence is unavailable for new lending."
    return result


def portfolio_summary(*, workspace, borrower=None, include_rows=True, filters=None):
    totals = {key: ZERO for key in MONEY_FIELDS}
    rows, unavailable, active_borrowers = [], 0, set()
    active_count = pending_returns = account_count = 0
    accounts = summary_accounts(workspace=workspace, borrower=borrower, balances_only=True, filters=filters)
    if not include_rows:
        accounts = accounts.filter(state__in=LIVE_STATES)
    for account in accounts.iterator(chunk_size=250):
        account_count += 1
        if account.state == "ACTIVE":
            active_count += 1
            active_borrowers.add(account.borrower_id)
        try:
            row = account_summary(account)
        except (ValueError, ArithmeticError, TypeError):
            row = dict(account=account, unavailable=True)
            if account.state in ("ACTIVE", "SETTLED_RETURN_PENDING"):
                unavailable += 1
        else:
            pending_returns += row["pending_returns"]
            # Draft limits are proposals; closed accounts have no live entitlement.
            if account.state == "ACTIVE":
                for key in MONEY_FIELDS:
                    totals[key] += row[key]
        if include_rows:
            rows.append(row)
    return dict(rows=rows, active_count=active_count, borrower_ids=active_borrowers,
        pending_returns=pending_returns, unavailable=unavailable, account_count=account_count,
        **{key: value if not unavailable else None for key, value in totals.items()})
