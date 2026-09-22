"""Bounded opening and servicing evidence export; this is not a restore command."""
from dataclasses import asdict
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.selectors.balances import calculate_pawn_loan_balance
from .history_contract import HistoryError, MAX_BYTES, decimal, digest, dump
from .history_setup import require_history_setup_access
from .opening_continuation import preview_opening_collection
from .opening_evidence import read_opening_evidence
from .opening_import import PROFILE as COMMIT_PROFILE

from .opening_contract import FIELDS, FIELDS_V2, MAX_RECORDS, PROFILE, PAYMENT_PROFILE


def _json(value):
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise HistoryError("Opening export contains a non-finite amount.")
        return decimal(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, dict):
        return {key: _json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(item) for item in value]
    return value


def _row(kind, instance):
    return _json({name: getattr(instance, name) for name in FIELDS_V2[kind].split()})


def _access(workspace_id, actor):
    workspace = require_history_setup_access(workspace_id, actor)
    resolve_workspace_access(actor=actor, workspace=workspace).require("data.export")
    return workspace


@transaction.atomic
def export_loan_data(*, workspace_id, actor, loan_id):
    """Choose the truthful download profile only after checking Workspace access."""
    _access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    _access(workspace_id, actor)
    loan = m.PawnLoan.objects.select_for_update().get(workspace_id=workspace_id, pk=loan_id)
    if loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
        return export_opening(workspace_id=workspace_id, actor=actor, loan_id=loan_id), "loan-opening.jsonl"
    from .history_export import export_history
    return export_history(workspace_id=workspace_id, actor=actor, loan_id=loan_id), "loan-history.jsonl"


@transaction.atomic
def export_opening(*, workspace_id, actor, loan_id):
    try:
        return _export_opening(workspace_id=workspace_id, actor=actor, loan_id=loan_id)
    except (KeyError, TypeError, ValueError) as exc:
        raise HistoryError("Opening evidence cannot be exported: " + str(exc)) from exc


def _export_opening(*, workspace_id, actor, loan_id, as_of_date=None, audit=True):
    workspace = _access(workspace_id, actor)
    Company.all_objects.select_for_update().get(pk=workspace_id)
    workspace = _access(workspace_id, actor)
    loan = m.PawnLoan.objects.select_for_update().get(workspace_id=workspace_id, pk=loan_id)
    if loan.state not in {"ACTIVE", "CLOSED"}:
        raise HistoryError("Only active or fully released opening loans are supported.")
    items = list(loan.collateral_items.select_for_update().order_by("pk")[:21])
    events = list(loan.loan_events.select_for_update().order_by("effective_date", "pk")[:241])
    if not 1 <= len(items) <= 20 or not 1 <= len(events) <= 240:
        raise HistoryError("Opening export requires 1-20 items and 1-240 events.")
    openings = [event for event in events if event.event_kind == "MIGRATION_OPENING"]
    if len(openings) != 1:
        raise HistoryError("One reviewed migration opening is required.")
    opening = read_opening_evidence(loan, openings[0])
    origin = m.HistoricalLoanImport.objects.get(workspace_id=workspace_id, loan=loan)
    if (origin.document.get("profile") != COMMIT_PROFILE or
            origin.source_sha256 != digest(origin.document) or
            origin.document.get("review") != opening["review"] or
            origin.references.get("items") != opening["item_mapping"] or
            set(opening["item_mapping"].values()) != {item.pk for item in items}):
        raise HistoryError("Opening import provenance and collateral membership must match.")
    review = opening["review"]
    setup = origin.document["setup"]
    if loan.tenure_months != setup["tenure_months"] or loan.principal_amount != Decimal(review["balances"]["principal"]):
        raise HistoryError("Opening original terms have changed.")
    for name, value in setup["policy"].items():
        actual = getattr(loan.policy_snapshot, name)
        if actual != (Decimal(value) if isinstance(actual, Decimal) else value):
            raise HistoryError("Opening servicing policy differs from its frozen setup.")
    source_items = {opening["item_mapping"][row["id"]]: row for row in review["collateral"]}
    for item in items:
        source = source_items[item.pk]
        if item.description != source["description"] or item.metal != source["metal"]:
            raise HistoryError("Opening collateral facts have changed.")
        for name, field in (("gross_weight", "gross_weight"), ("net_weight", "net_weight"),
                ("purity", "purity_percentage"), ("remaining_principal", "allocated_principal"),
                ("monthly_rate", "monthly_interest_rate")):
            if getattr(item, field) != (None if source[name] is None else Decimal(source[name])):
                raise HistoryError("Opening collateral weights, principal or agreed rate have changed.")
    if any(item.renewed_from_id or item.current_storage_location_id or item.interest_rate_policy_id or
           item.funding_pledge_items.exists() or item.storage_movements.exists() for item in items):
        raise HistoryError("Connected renewal, funding, rate policy or storage history requires a wider profile.")

    as_of = as_of_date or max(timezone.localdate(), max(event.effective_date for event in events))
    continuation = preview_opening_collection(loan, events=events, as_of_date=as_of)
    balance = calculate_pawn_loan_balance(loan, events=events, collateral_items=items,
        policy_snapshot=loan.policy_snapshot, as_of_date=as_of, pending_delivery_blocks=False)
    settled = balance.principal_outstanding == balance.interest_outstanding == balance.fees_outstanding == 0
    closed = loan.state == "CLOSED"
    reversed_ids = {row.reversal_of_id for row in events if row.event_kind == "REVERSAL" and row.effective_date <= as_of}
    released = any(row.event_kind == "RELEASE_RECEIPT" and row.effective_date <= as_of and row.pk not in reversed_ids for row in events)
    if (closed != released or (closed and not settled) or
            any(item.custody_state != ("WITH_CUSTOMER" if closed else "IN_VAULT") for item in items)):
        raise HistoryError("Opening balance, loan state and collateral custody disagree.")

    # Every query is directly Workspace-scoped, including child evidence tables.
    def rows(kind, model, **filters):
        queryset = model.objects.filter(workspace_id=workspace_id, **filters).order_by("pk")
        result = [_row(kind, row) for row in queryset[:MAX_RECORDS + 1]]
        if len(result) > MAX_RECORDS:
            raise HistoryError("Opening supporting evidence exceeds the record limit.")
        return result

    evidence = {"loan": _row("loan", loan), "origin": _row("origin", origin),
        "policy": _row("policy", loan.policy_snapshot), "items": [_row("items", item) for item in items],
        "events": [_row("events", event) for event in events]}
    for kind, model in (("accruals", m.PawnLoanInterestAccrual), ("releases", m.PawnLoanRelease),
            ("schedules", m.RepaymentScheduleVersion), ("obligations", m.RepaymentObligation),
            ("schedule_changes", m.RepaymentScheduleChange), ("allocations", m.ObligationAllocation),
            ("change_log", m.LoanChangeLog)):
        evidence[kind] = rows(kind, model, loan_id=loan.pk)
    evidence["accrual_lines"] = rows("accrual_lines", m.PawnLoanInterestAccrualLine, accrual_id__in=[row["id"] for row in evidence["accruals"]])
    release_ids = [row["id"] for row in evidence["releases"]]
    evidence["release_items"] = rows("release_items", m.PawnLoanReleaseItem, release_id__in=release_ids)
    evidence["release_reversals"] = rows("release_reversals", m.PawnLoanReleaseReversal, release_id__in=release_ids)
    evidence["closing_lines"] = rows("closing_lines", m.PawnLoanPrincipalClosingLine, loan_event_id__in=[event.pk for event in events])
    has_payments = any(event.event_kind == "REPAYMENT" for event in events)
    if has_payments:
        evidence["repayment_lines"] = rows("repayment_lines", m.PawnLoanRepaymentAllocationLine, loan_event_id__in=[event.pk for event in events])
    if (len(evidence["schedules"]) != 1 or evidence["schedules"][0]["id"] != origin.references["schedule_id"] or
            evidence["schedules"][0]["source_event_id"] != openings[0].pk):
        raise HistoryError("The reviewed opening schedule is missing or has an unsupported replacement.")
    if ({row["loan_event_id"] for row in evidence["accruals"]} != {event.pk for event in events if event.event_kind == "INTEREST_ACCRUAL"} or
            {row["loan_event_id"] for row in evidence["releases"]} != {event.pk for event in events if event.event_kind == "RELEASE_RECEIPT"}):
        raise HistoryError("Opening servicing events and their supporting records disagree.")
    item_ids = [item.pk for item in items]
    custody = m.PawnCollateralCustodyEvent.objects.filter(workspace_id=workspace_id, collateral_item_id__in=item_ids)
    if custody.exclude(release_id__in=release_ids).exists():
        raise HistoryError("Opening custody contains actions outside supported full release/reversal.")
    evidence["custody_events"] = rows("custody_events", m.PawnCollateralCustodyEvent, collateral_item_id__in=item_ids)
    evidence["appraisals"] = rows("appraisals", m.CollateralAppraisal, collateral_item_id__in=item_ids)

    from apps.tenant_apps.data_portability.models import LoanHistoryBatch
    evidence["source_verifications"] = []
    batches = LoanHistoryBatch.objects.filter(workspace_id=workspace_id, profile="legacy-opening/1", result=origin).order_by("pk")
    for batch in batches[:21]:
        if batch.document.get("opening") != origin.document:
            raise HistoryError("Source staging evidence differs from the accepted opening.")
        evidence["source_verifications"].append(_json({"batch": batch.public_id,
            "source_evidence": batch.document["source_evidence"]}))
    if origin.references.get("restore"):
        evidence["source_verifications"].extend(origin.references["restore"]["document"]["evidence"]["source_verifications"])
    if len(evidence["source_verifications"]) > 20 or 3 + sum(len(value) for value in evidence.values() if isinstance(value, list)) > MAX_RECORDS:
        raise HistoryError("Opening supporting evidence exceeds the record limit.")
    evidence["recorded_balance"] = {name: decimal(getattr(balance, name + "_outstanding")) for name in ("principal", "interest", "fees")}
    evidence["interest_conceded"] = decimal(balance.interest_conceded)
    evidence["collection_preview"] = _json(asdict(continuation))
    profile = PAYMENT_PROFILE if has_payments else PROFILE
    manifest = {"profile": profile, "coverage": "OPENING_AND_SUPPORTED_SERVICING",
        "financial_history_from": openings[0].effective_date.isoformat(), "as_of": as_of.isoformat(),
        "history_before_cutover": "UNAVAILABLE", "restore_supported": True,
        "reference_scope": {"workspace_id": workspace_id, "ids": "SOURCE_DATABASE_LOCAL"},
        "exclusions": ["pre_cutover_transactions", "binary_files", "workspace_configuration", "party_master"],
        "sha256": digest(evidence)}
    content = (dump(manifest) + "\n" + dump(evidence) + "\n").encode("utf-8")
    if len(content) > MAX_BYTES:
        raise HistoryError("Opening export exceeds the 5 MiB limit.")
    if audit:
        AuditLog.log("DATA_EXPORT", company=workspace, user=actor,
            description="Exported opening and supported servicing evidence; earlier history unavailable.",
            data={"loan": loan.pk, "profile": profile, "sha256": manifest["sha256"]})
    return content
