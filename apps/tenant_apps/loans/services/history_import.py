"""Authorized atomic restoration of the bounded complete-history contract."""
from datetime import date, datetime
from decimal import Decimal

from django.db import transaction, connection
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.orgs.audit import AuditLog
from apps.orgs.models import Company
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.domain import DisbursalPolicySnapshot, CollateralMetal, TransactionKind
from apps.tenant_apps.loans.domain.collateral_economics import (
    CollateralTrancheInput, DisbursalFeeInput, calculate_pawn_disbursal_economics,
)
from apps.tenant_apps.loans.integrations.event_payloads import LoanEventPayload
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.obligation_state import calculate_obligation_state_as_of, get_active_repayment_schedule_as_of
from .history_setup import require_history_setup_access, preview_history_setup
from .portability_validation import HISTORICAL_INCONSISTENCY, MISSING_EVIDENCE, OPERATIONAL_READINESS
from .history_contract import HistoryError, validate, digest, money, decimal, canonical_document
from .import_identity import find_source_origin, source_binding_id
from .event_recording import record_loan_event
from .obligations import persist_disbursal_repayment_schedule, allocate_event_to_obligations, terminate_active_repayment_schedule
from .pawn_repayment import allocate_repayment, allocate_repayment_principal_to_tranches
from .pawn_tranches import get_pawn_principal_tranche_balances
from .pawn_interest import preview_pawn_loan_accruals, build_pawn_accrual_detail, persist_pawn_accrual_lines


def require_history_access(workspace_id, actor, document):
    workspace = require_history_setup_access(workspace_id, actor)
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    for action in ("loan.approve", "loan.disburse"):
        access.require(action)
    for event in document["loan"]["events"]:
        action = {"REPAYMENT": "loan.repay", "INTEREST_ACCRUAL": "loan.accrue", "RELEASE_RECEIPT": "loan.release"}.get(event["kind"])
        if action: access.require(action)
    return workspace


def _check(expected, actual, label):
    if set(expected) != set(actual) or any(money(expected[k]) != money(actual[k]) for k in expected):
        raise HistoryError(
            f"{label} does not reconcile with canonical Loans calculations.",
            category=HISTORICAL_INCONSISTENCY,
            code="CALCULATION_MISMATCH",
        )


def balance_values(loan, day):
    value = get_pawn_loan_balance(loan.pk, as_of_date=day)
    return {"principal": decimal(value.principal_outstanding), "interest": decimal(value.interest_outstanding), "fees": decimal(value.fees_outstanding)}


def _create(model, **values):
    obj = model(**values)
    obj.full_clean()
    obj.save()
    return obj


def _stamp(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result > timezone.now():
        raise HistoryError(
            "Historical timestamps cannot be in the future.",
            category=HISTORICAL_INCONSISTENCY,
            code="FUTURE_TIMESTAMP",
        )
    return result


def _chronology(document):
    loan, manifest = document["loan"], document["manifest"]
    cutoff = date.fromisoformat(manifest["as_of"])
    start = date.fromisoformat(loan["disbursed_on"])
    if cutoff > timezone.localdate() or cutoff < start or (cutoff - start).days > 3660:
        raise HistoryError(
            "Cutover must follow disbursal, be no later than today and cover at most ten years.",
            category=OPERATIONAL_READINESS if cutoff >= start and (cutoff - start).days > 3660 else HISTORICAL_INCONSISTENCY,
            code="CUTOVER_BOUND",
        )
    if _stamp(loan["approval"]["at"]).date() > start:
        raise HistoryError(
            "Original approval must precede disbursal.",
            category=HISTORICAL_INCONSISTENCY,
            code="APPROVAL_ORDER",
        )
    ids = [row["id"] for row in loan["collateral"]]
    if len(set(ids)) != len(ids):
        raise HistoryError(
            "Duplicate collateral source identity.",
            category=HISTORICAL_INCONSISTENCY,
            code="DUPLICATE_COLLATERAL_ID",
        )
    events = loan["events"]
    if len({e["id"] for e in events}) != len(events):
        raise HistoryError(
            "Duplicate event source identity.",
            category=HISTORICAL_INCONSISTENCY,
            code="DUPLICATE_EVENT_ID",
        )
    if events[0]["kind"] != "DISBURSAL" or events[0]["date"] != loan["disbursed_on"]:
        raise HistoryError(
            "History must start with its original disbursal.",
            category=HISTORICAL_INCONSISTENCY,
            code="ORIGINAL_DISBURSAL",
        )
    previous = start
    for index, event in enumerate(events):
        day = date.fromisoformat(event["date"])
        if not previous <= day <= cutoff:
            raise HistoryError(
                "Event order or cutover date is inconsistent.",
                category=HISTORICAL_INCONSISTENCY,
                code="EVENT_ORDER",
            )
        previous = day
        if index and event["kind"] == "DISBURSAL":
            raise HistoryError(
                "Only one disbursal is supported.",
                category=OPERATIONAL_READINESS,
                code="MULTIPLE_DISBURSALS",
            )
        if (event["accrual"] is not None) != (event["kind"] == "INTEREST_ACCRUAL"):
            raise HistoryError(
                "Accrual evidence must match its event kind.",
                category=MISSING_EVIDENCE if event["accrual"] is None else HISTORICAL_INCONSISTENCY,
                code="ACCRUAL_EVIDENCE",
            )
        if (event["release"] is not None) != (event["kind"] == "RELEASE_RECEIPT"):
            raise HistoryError(
                "Release evidence must match its event kind.",
                category=MISSING_EVIDENCE if event["release"] is None else HISTORICAL_INCONSISTENCY,
                code="RELEASE_EVIDENCE",
            )
        if event["release"]:
            if index != len(events)-1 or loan["state"] != "CLOSED":
                raise HistoryError(
                    "Full release must be the last event of a closed loan.",
                    category=HISTORICAL_INCONSISTENCY,
                    code="RELEASE_ORDER",
                )
            if _stamp(event["release"]["returned_at"]).date() != day:
                raise HistoryError(
                    "Custody return date must match release.",
                    category=HISTORICAL_INCONSISTENCY,
                    code="CUSTODY_DATE",
                )
    if (loan["state"] == "CLOSED") != (events[-1]["kind"] == "RELEASE_RECEIPT"):
        raise HistoryError(
            "Closed loans require evidenced full release.",
            category=MISSING_EVIDENCE if loan["state"] == "CLOSED" else HISTORICAL_INCONSISTENCY,
            code="CLOSED_RELEASE_EVIDENCE",
        )
    return cutoff


@transaction.atomic
def import_complete_history(*, workspace_id, actor, document, mapping):
    # Context/owner checks precede data lookup and any idempotent return.
    require_history_setup_access(workspace_id, actor)
    validate(document)
    document = canonical_document(document)
    require_history_access(workspace_id, actor, document)
    if type(mapping) is not dict or set(mapping) != {"revision_id", "series_id", "product_version_id", "borrower_id"}:
        raise HistoryError(
            "Select explicit destination setup and borrower mappings.",
            category=OPERATIONAL_READINESS,
            code="DESTINATION_MAPPING",
        )
    workspace = Company.all_objects.select_for_update().get(pk=workspace_id)
    require_history_access(workspace_id, actor, document)
    source, manifest = document["loan"], document["manifest"]
    binding_id = source_binding_id(manifest["namespace"], source["id"], source["borrower"]["source_system"])
    cutoff = _chronology(document)
    checksum = digest(document)
    existing = find_source_origin(workspace_id=workspace_id, namespace=manifest["namespace"],
        source_id=source["id"], borrower_source_system=source["borrower"]["source_system"])
    if existing:
        if existing.source_sha256 != checksum or existing.references["mapping"] != mapping:
            raise HistoryError(
                "This source loan already has different accepted history or mappings.",
                category=OPERATIONAL_READINESS,
                code="SOURCE_ALREADY_ACCEPTED",
            )
        return existing, existing.references["summary"]
    release_event = source["events"][-1] if source["state"] == "CLOSED" else None
    setup = preview_history_setup(workspace_id=workspace_id, actor=actor,
        revision_id=mapping["revision_id"], series_id=mapping["series_id"], product_version_id=mapping["product_version_id"],
        source_namespace=manifest["namespace"], source_loan_id=binding_id, source_loan_number=source["number"],
        source_license_number=source["licence_number"], disbursed_on=date.fromisoformat(source["disbursed_on"]),
        tenure_months=source["tenure_months"], calculation_contract_version=source["calculation_contract"],
        operational_grace_days=source["grace_days"], source_release_id=release_event["id"] if release_event else "",
        source_release_number=release_event["release"]["number"] if release_event else "")
    # The borrower is resolved by the portability boundary using exact Party source identity.
    from apps.tenant_apps.party.models import Party
    borrower = Party.objects.select_for_update().get(workspace_id=workspace_id, pk=mapping["borrower_id"])
    from apps.tenant_apps.data_portability.children import parent_for
    parent = parent_for({"party_source_system": source["borrower"]["source_system"], "party_external_id": source["borrower"]["id"]}, workspace_id)
    if parent is None or parent.party_id != borrower.pk:
        raise HistoryError(
            "Borrower mapping must resolve the exact source Party identity.",
            category=OPERATIONAL_READINESS,
            code="BORROWER_MAPPING",
        )
    policy = DisbursalPolicySnapshot.from_dict(source["policy"])
    economics = calculate_pawn_disbursal_economics([
        CollateralTrancheInput(reference=row["id"], metal=CollateralMetal(row["metal"]), net_weight=money(row["net_weight"]),
            purity_percentage=money(row["purity"]), allocated_principal=money(row["principal"]), monthly_interest_rate=money(row["monthly_rate"]),
            metal_rate_per_unit=money(row["metal_rate"]) if row["metal_rate"] is not None else None,
            latest_appraised_value=money(row["appraised_value"]) if row["appraised_value"] is not None else None)
        for row in source["collateral"]], valuation_method=policy.valuation_method, maximum_ltv_ratio=policy.maximum_ltv_ratio,
        advance_interest_periods=source["disbursal"]["advance_periods"], currency_quantum=policy.currency_quantum,
        fees=[DisbursalFeeInput(code=f["code"], name=f["name"], calculation_type=f["kind"], value=money(f["value"]), deducted_at_disbursal=f["deducted"]) for f in source["disbursal"]["fees"]])
    _check({k: source["disbursal"][k] for k in ("principal", "monthly_interest", "advance_interest", "deducted_fees", "net_cash")},
        {"principal": economics.gross_principal, "monthly_interest": economics.monthly_interest, "advance_interest": economics.advance_interest,
         "deducted_fees": economics.deducted_fees, "net_cash": economics.net_disbursed}, "Disbursal economics")
    loan = _create(m.PawnLoan, workspace=workspace, license=setup["revision"].license, license_revision=setup["revision"],
        series=setup["series"], product_version=setup["product"], borrower=borrower, loan_number=setup["numbers"][0]["local_number"],
        state="ACTIVE", loan_date=date.fromisoformat(source["disbursed_on"]), principal_amount=economics.gross_principal,
        monthly_interest_rate=economics.effective_monthly_rate, tenure_months=source["tenure_months"], created_by=actor, updated_by=actor)
    items = {}
    for row in source["collateral"]:
        items[row["id"]] = _create(m.PawnCollateralItem, workspace=workspace, loan=loan, description=row["description"], metal=row["metal"],
            gross_weight=money(row["gross_weight"]), net_weight=money(row["net_weight"]), purity_percentage=money(row["purity"]),
            allocated_principal=money(row["principal"]), monthly_interest_rate=money(row["monthly_rate"]),
            latest_appraised_value=money(row["appraised_value"]) if row["appraised_value"] is not None else None)
    reverse_items = {obj.pk: key for key, obj in items.items()}
    tranches = [{"collateral_item_id": items[t.reference].pk, "allocated_principal": decimal(t.allocated_principal),
        "monthly_interest_rate": decimal(t.monthly_interest_rate), "advance_interest": decimal(t.advance_interest),
        "monthly_interest": decimal(t.monthly_interest), "selected_value": decimal(t.selected_value)} for t in economics.tranches]
    evidence = {**source["policy"], "tranches": tranches, "fees": source["disbursal"]["fees"],
        "monthly_interest": decimal(economics.monthly_interest), "advance_interest_periods": economics.advance_interest_periods,
        "advance_interest": decimal(economics.advance_interest), "deducted_fees": decimal(economics.deducted_fees), "net_disbursed": decimal(economics.net_disbursed)}
    approval_payload = {"principal_amount": decimal(economics.gross_principal), "collateral_economics": evidence,
        "historical_approval": source["approval"]}
    approval = _create(m.PawnLoanApprovalSnapshot, workspace=workspace, loan=loan, version=1,
        payload=approval_payload, fingerprint=digest(approval_payload))
    snapshot = _create(m.LoanPolicySnapshot, workspace=workspace, loan=loan, **source["policy"])
    events, schedule, latest_accrual = {}, None, None
    for entry in source["events"]:
        day, kind = date.fromisoformat(entry["date"]), entry["kind"]
        values = {k: money(entry[k]) for k in ("principal", "interest", "fees")}
        allocations, period = (), None
        if kind == "DISBURSAL":
            _check(values, {"principal": economics.gross_principal, "interest": 0, "fees": economics.deducted_fees}, "Disbursal event")
        elif kind == "INTEREST_ACCRUAL":
            previews = preview_pawn_loan_accruals(loan.pk, as_of_date=day)
            if not previews:
                raise HistoryError(
                    "Unexpected accrual event.",
                    category=HISTORICAL_INCONSISTENCY,
                    code="UNEXPECTED_ACCRUAL",
                )
            period = previews[0]
            supplied = entry["accrual"]
            if supplied["start"] != period.period_start.isoformat() or supplied["end"] != period.period_end.isoformat() or day != period.period_end or supplied["period"] != period.period_number:
                raise HistoryError(
                    "Missing or misordered accrual periods.",
                    category=HISTORICAL_INCONSISTENCY,
                    code="ACCRUAL_PERIOD_ORDER",
                )
            _check({k: supplied[k] for k in ("fraction", "base", "unrounded", "recognized")},
                {"fraction": period.period_fraction, "base": period.calculation_base, "unrounded": period.unrounded_interest, "recognized": period.recognized_interest}, "Accrual period")
            _check(values, {"principal": 0, "interest": period.recognized_interest, "fees": 0}, "Accrual event")
        else:
            balance = get_pawn_loan_balance(loan.pk, as_of_date=day)
            if kind == "REPAYMENT":
                allocated = allocate_repayment(balance, sum(values.values()))
                _check(values, {"principal": allocated.principal, "interest": allocated.interest, "fees": allocated.fees}, "Repayment allocation")
                allocations = allocate_repayment_principal_to_tranches(loan, allocated.principal, expected_outstanding=balance.original_principal_outstanding)
            else:
                _check(values, {"principal": balance.principal_outstanding, "interest": balance.interest_outstanding, "fees": balance.fees_outstanding}, "Full settlement")
                pending = preview_pawn_loan_accruals(loan.pk, as_of_date=day)
                if pending:
                    raise HistoryError(
                        "Full release requires all accrual evidence through its date, including zero-interest periods.",
                        category=MISSING_EVIDENCE,
                        code="MISSING_ACCRUAL_EVIDENCE",
                    )
                allocations = get_pawn_principal_tranche_balances(loan)
        expected_lines = []
        if kind in {"REPAYMENT", "RELEASE_RECEIPT"}:
            ordered = allocations if kind == "REPAYMENT" else sorted(allocations, key=lambda a: (-a.monthly_interest_rate, a.collateral_item_id))
            for item in ordered:
                before = item.balance_before if kind == "REPAYMENT" else item.principal_outstanding
                principal = item.principal_applied if kind == "REPAYMENT" else item.principal_outstanding
                after = item.balance_after if kind == "REPAYMENT" else Decimal(0)
                expected_lines.append({"item": reverse_items[item.collateral_item_id], "before": decimal(before), "principal": decimal(principal), "after": decimal(after)})
        if len(entry["allocations"]) != len(expected_lines):
            raise HistoryError(
                "Missing item principal allocation evidence.",
                category=MISSING_EVIDENCE if len(entry["allocations"]) < len(expected_lines) else HISTORICAL_INCONSISTENCY,
                code="ALLOCATION_EVIDENCE",
            )
        for supplied, expected in zip(entry["allocations"], expected_lines):
            if supplied["item"] != expected["item"]:
                raise HistoryError(
                    "Item allocation order does not match the native rule.",
                    category=HISTORICAL_INCONSISTENCY,
                    code="ALLOCATION_ORDER",
                )
            _check({k:supplied[k] for k in ("before","principal","after")}, {k:expected[k] for k in ("before","principal","after")}, "Item principal allocation")
        payload = LoanEventPayload(loan_id=loan.pk, loan_number=loan.loan_number, borrower_id=borrower.pk,
            event_kind=TransactionKind(kind), effective_date=day, values=values).to_dict()
        payload["historical_source"] = {"namespace": manifest["namespace"], "id": entry["id"], "actor": entry["actor"]}
        if kind == "DISBURSAL":
            payload["values"].update(net_cash=decimal(economics.net_disbursed), advance_interest=decimal(economics.advance_interest))
            payload["disbursal"] = {"approval_snapshot_id": approval.pk, "policy_snapshot_id": snapshot.pk,
                "advance_interest_periods": economics.advance_interest_periods, "monthly_interest": decimal(economics.monthly_interest), "tranches": tranches, "fees": source["disbursal"]["fees"]}
        if period:
            payload["accrual"] = build_pawn_accrual_detail(period, snapshot)
            payload["values"]["advance_interest_applied"] = decimal(period.advance_interest_applied)
        event, _ = record_loan_event(loan.pk, event_kind=kind, effective_date=day, payload=payload, actor=actor)
        events[entry["id"]] = event.pk
        if kind == "DISBURSAL":
            _create(m.PawnLoanDisbursalSnapshot, workspace=workspace, loan=loan, approval_snapshot=approval,
                policy_snapshot=snapshot, loan_event=event, gross_principal=economics.gross_principal,
                monthly_interest=economics.monthly_interest, advance_interest_periods=economics.advance_interest_periods,
                advance_interest=economics.advance_interest, deducted_fees=economics.deducted_fees,
                net_disbursed=economics.net_disbursed, evidence=evidence, created_by=actor)
            schedule = persist_disbursal_repayment_schedule(loan, source_event=event, disbursed_on=day, currency_quantum=snapshot.currency_quantum, actor=actor)
            source_schedule = source["schedule"]
            if source_schedule["maturity"] != schedule.maturity_date.isoformat():
                raise HistoryError(
                    "Original maturity differs from the frozen contract.",
                    category=HISTORICAL_INCONSISTENCY,
                    code="MATURITY_CONTRACT",
                )
            _check({k:source_schedule[k] for k in ("principal","interest")}, {"principal":schedule.principal,"interest":schedule.contractual_interest}, "Schedule")
            actual_rows = list(schedule.obligations.order_by("sequence"))
            if len(actual_rows) != len(source_schedule["obligations"]):
                raise HistoryError(
                    "Missing source obligations.",
                    category=MISSING_EVIDENCE if len(source_schedule["obligations"]) < len(actual_rows) else HISTORICAL_INCONSISTENCY,
                    code="OBLIGATION_EVIDENCE",
                )
            for supplied, actual in zip(source_schedule["obligations"], actual_rows):
                if supplied["sequence"] != actual.sequence or supplied["due"] != actual.due_date.isoformat():
                    raise HistoryError(
                        "Source due dates differ from the contract.",
                        category=HISTORICAL_INCONSISTENCY,
                        code="OBLIGATION_DATES",
                    )
                _check({k:supplied[k] for k in ("principal","interest")}, {"principal":actual.principal_due,"interest":actual.interest_due}, "Obligation")
        if period:
            latest_accrual = _create(m.PawnLoanInterestAccrual, workspace=workspace, loan=loan,
                period_number=period.period_number, period_start=period.period_start, period_end=period.period_end,
                period_fraction=period.period_fraction, calculation_base=period.calculation_base,
                unrounded_interest=period.unrounded_interest, recognized_interest=period.recognized_interest,
                loan_event=event, finalized_by=actor)
            persist_pawn_accrual_lines(latest_accrual, period)
        if kind in {"REPAYMENT", "RELEASE_RECEIPT"}:
            allocate_event_to_obligations(source_event=event, principal_amount=values["principal"], interest_amount=values["interest"], actor=actor)
            for order, row in enumerate(expected_lines, 1):
                item = items[row["item"]]
                model = m.PawnLoanRepaymentAllocationLine if kind == "REPAYMENT" else m.PawnLoanPrincipalClosingLine
                _create(model, workspace=workspace, loan_event=event, collateral_item=item, allocation_order=order,
                    monthly_interest_rate=item.monthly_interest_rate, balance_before=money(row["before"]), balance_after=money(row["after"]),
                    **{"principal_applied" if kind == "REPAYMENT" else "principal_settled": money(row["principal"])})
        if kind == "RELEASE_RECEIPT":
            release_data = entry["release"]
            valuations = {v["item"]: v["value"] for v in release_data["valuation"]}
            if len(valuations) != len(release_data["valuation"]) or set(valuations) != set(items):
                raise HistoryError(
                    "Full release must account for every collateral item.",
                    category=HISTORICAL_INCONSISTENCY,
                    code="RELEASE_COLLATERAL_SET",
                )
            release = _create(m.PawnLoanRelease, workspace=workspace, loan=loan, release_number=setup["numbers"][1]["local_number"],
                request_key="history:"+digest(entry)[0:64], effective_date=day, settlement_amount=sum(values.values()),
                principal_amount=values["principal"], interest_amount=values["interest"], fee_amount=values["fees"],
                valuation_snapshot={"historical_source":release_data}, loan_event=event, created_by=actor,
                catch_up_accrual=latest_accrual if latest_accrual and latest_accrual.period_end == day else None)
            for key, item in items.items():
                _create(m.PawnLoanReleaseItem, workspace=workspace, release=release, collateral_item=item,
                    returned_at=_stamp(release_data["returned_at"]), valuation_snapshot={"value":valuations[key], "source_collector":release_data["collector"]})
                _create(m.PawnCollateralCustodyEvent, workspace=workspace, collateral_item=item, release=release,
                    from_state="IN_VAULT", to_state="WITH_CUSTOMER", effective_date=day, actor=actor)
                item.custody_state="WITH_CUSTOMER"; item.save(update_fields=["custody_state"])
            terminate_active_repayment_schedule(loan=loan, source_event=event, reason="FULL_RELEASE", actor=actor)
            loan.state="CLOSED"; loan.save(update_fields=["state"])
        _check(entry["balance"], balance_values(loan, day), "Event checkpoint")
    _check(source["cutover"], balance_values(loan, cutoff), "Cutover balance")
    obligations = calculate_obligation_state_as_of(get_active_repayment_schedule_as_of(loan, cutoff), cutoff)
    if obligations.integrity_findings:
        raise HistoryError(
            "Contractual obligations have integrity findings.",
            category=HISTORICAL_INCONSISTENCY,
            code="OBLIGATION_INTEGRITY",
        )
    if source["state"] == "ACTIVE" and obligations.schedule_id is None:
        raise HistoryError(
            "Active history needs a remaining contractual schedule.",
            category=OPERATIONAL_READINESS,
            code="ACTIVE_SCHEDULE",
        )
    if source["state"] == "CLOSED" and (any(money(v) for v in source["cutover"].values()) or obligations.schedule_id is not None):
        raise HistoryError(
            "Closed history has unsettled balances or an active schedule.",
            category=HISTORICAL_INCONSISTENCY,
            code="CLOSED_UNSETTLED",
        )
    connection.check_constraints()
    summary = {"state":loan.state, "loan_number":loan.loan_number, "events":len(events), "collateral":len(items),
        "as_of":manifest["as_of"], "balance":balance_values(loan, cutoff),
        "contractual_remaining":{"principal":decimal(obligations.remaining.principal),"interest":decimal(obligations.remaining.interest)},
        "borrower_name":borrower.display_name}
    origin = m.HistoricalLoanImport.objects.create(workspace=workspace, loan=loan, source_namespace=manifest["namespace"], source_id=binding_id,
        source_sha256=checksum, document=document, references={"mapping":mapping,"items":{k:v.pk for k,v in items.items()},"events":events,"summary":summary}, imported_by=actor)
    AuditLog.log("DATA_IMPORT", company=workspace, user=actor, description="Imported reconciled complete loan history without replaying live workflows.",
        data={"history":str(origin.public_id),"loan":loan.pk,"sha256":checksum,"events":len(events)})
    return origin, summary
