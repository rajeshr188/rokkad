"""Reviewed, atomic admission of a never-entered paper loan and its timeline."""
from copy import deepcopy
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
from uuid import UUID, uuid4

from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from apps.orgs.models import Company
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.integrations import disbursal_payload
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from .action_access import require_workspace_action
from .event_recording import record_loan_event
from .obligations import persist_disbursal_repayment_schedule
from apps.tenant_apps.party.models import Party
from .recorded_numbers import claim_number, identity
from .recorded_origination_evidence import CONTRACT_POLICY_FIELDS
from .recorded_collections import PROFILE, collection_balance
from apps.tenant_apps.loans.domain.monthly_contract import RECORDED_PROFILE, POLICY_VERSION

SALT = "loans.recorded-history.review.v1"
INTENT_SALT = "loans.recorded-history.intent.v1"


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _digest(value):
    return hashlib.sha256(_canonical(value).encode()).hexdigest()


def _text(value, label, limit=160):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or any(ord(c) < 32 or ord(c) == 127 for c in value):
        raise ValueError(f"Enter {label}, up to {limit} characters without control characters.")
    return value.strip()


def _amount(value, label, *, places=2, positive=False):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result >= Decimal("1e12") or (positive and result == 0):
            raise ValueError()
        if result != result.quantize(Decimal(1).scaleb(-places)):
            raise ValueError()
    except (InvalidOperation, ValueError):
        raise ValueError(f"Enter a valid {label} with at most {places} decimal places.") from None
    return str(result.quantize(Decimal(1).scaleb(-places)))


def validate_input(data, *, historical_source=False):
    """Validate again in the command; a valid browser form is not authority."""
    if not isinstance(data, dict) or len(_canonical(data)) > 40000:
        raise ValueError("Paper history is missing or exceeds the supported size.")
    value = deepcopy(data)
    quantum = Decimal(value.pop("currency_quantum", "0.01"))
    if quantum not in (Decimal("0.01"), Decimal("1")):
        raise ValueError("Select paise or whole-rupee rounding from the actual agreement.")
    from .recorded_items import validate_items, monthly_interest, effective_rate
    collateral = value.pop("collateral", None)
    if collateral is not None:
        collateral = validate_items(collateral, _amount, _text)
    entry_note = value.pop("entry_note", None)
    if entry_note is not None:
        entry_note = _text(entry_note, "entry source explanation", 255)
    extra_fields = {"document_charge", "payout_basis"}
    required = {"borrower_id", "series_id", "product_version_id", "number", "date", "principal", "rate", "tenure",
        "advance_months", "cash_paid", "source_reference", "description", "metal", "quantity", "gross_weight",
        "net_weight", "purity", "monitoring_method", "monitoring_ltv", "monitoring_reason", "complete_through",
        "final_state", "confirmed_history", "confirmed_rule", "events"}
    routine = value.pop("recording_mode", None)
    if routine not in (None, "TRANSACTION_ENTRY"):
        raise ValueError("Unsupported paper recording mode.")
    if set(value) not in (required, required | extra_fields):
        raise ValueError("The paper history fields are incomplete or unsupported.")
    if extra_fields <= set(value):
        value["document_charge"] = _amount(value["document_charge"], "document charge")
        if value["payout_basis"] not in ("CASH", "PROCEEDS"):
            raise ValueError("Select actual cash or paper proceeds after deductions.")
    for name in ("borrower_id", "series_id", "product_version_id", "tenure", "quantity"):
        if type(value[name]) is not int or value[name] <= 0:
            raise ValueError(f"Select a valid {name.replace('_', ' ')}.")
    if value["tenure"] > 600 or value["quantity"] > (10000 if collateral is not None else 999) or type(value["advance_months"]) is not int or value["advance_months"] not in (0, 1):
        raise ValueError("Use a supported tenure, quantity and zero or one advance month.")
    for field, limit in (("number",64), ("source_reference",160), ("description",255), ("monitoring_reason",255)):
        value[field] = _text(value[field], field.replace("_", " "), limit)
    for field in ("principal", "cash_paid"):
        value[field] = _amount(value[field], field, positive=True)
    value["rate"] = _amount(value["rate"], "monthly rate", places=6)
    if Decimal(value["rate"]) > 999:
        raise ValueError("Monthly rate is outside the supported range.")
    for field in ("gross_weight", "net_weight", "purity"):
        value[field] = _amount(value[field], field, places=4, positive=True)
    if Decimal(value["net_weight"]) > Decimal(value["gross_weight"]) or Decimal(value["purity"]) > 100:
        raise ValueError("Net weight cannot exceed gross weight; purity cannot exceed 100%.")
    if value["metal"] not in ("GOLD", "SILVER") or value["monitoring_method"] not in (
            "CALCULATED_METAL_VALUE", "LATEST_APPRAISAL", "LOWER_OF_CALCULATED_AND_APPRAISAL"):
        raise ValueError("Select a supported metal and monitoring method.")
    value["monitoring_ltv"] = _amount(value["monitoring_ltv"], "monitoring LTV ratio", places=6, positive=True)
    if Decimal(value["monitoring_ltv"]) > 1:
        raise ValueError("Monitoring LTV cannot exceed 100%.")
    day, through = date.fromisoformat(value["date"]), date.fromisoformat(value["complete_through"])
    if not day <= through <= timezone.localdate() or (through - day).days > 3660:
        raise ValueError("History must run from the actual loan date through a date no later than today, within ten years.")
    if (type(value["confirmed_history"]) is not bool or value["confirmed_rule"] is not True
            or (routine is None and value["confirmed_history"] is not True)):
        raise ValueError("Confirm the complete paper history and the exact agreed anniversary-interest rule.")
    if routine:
        value["recording_mode"] = routine
    if entry_note is not None:
        value["entry_note"] = entry_note
    if collateral is not None:
        if sum((Decimal(row["principal"]) for row in collateral), Decimal("0")) != Decimal(value["principal"]):
            raise ValueError("Loan principal must equal the actual item amounts.")
        if effective_rate(collateral) != Decimal(value["rate"]):
            raise ValueError("The display rate must reconcile to actual item rates.")
        value["collateral"] = collateral
    if value["final_state"] not in ("ACTIVE", "CLOSED"):
        raise ValueError("Confirm whether the last loan is still held or fully returned.")
    if type(value["events"]) is not list or len(value["events"]) > 30:
        raise ValueError("Enter at most 30 dated transactions in their original order.")
    previous, refs, renewals = day, set(), 0
    for index, row in enumerate(value["events"]):
        item_split = row.pop("item_principal_split", None) if isinstance(row, dict) else None
        base_fields = {"kind", "date", "amount", "reference", "number", "rate", "tenure", "recipient"}
        renewal_fields = {"renewal_method", "new_principal", "cash_paid", "interest_offset", "custody"}
        if not isinstance(row, dict) or set(row) not in (base_fields, base_fields | renewal_fields,
                base_fields | {"closure_basis"}, base_fields | renewal_fields | {"closure_basis"}):
            raise ValueError("A timeline row is incomplete or unsupported.")
        if "closure_basis" in row:
            if row["kind"] == "CLOSE":
                if row["closure_basis"] not in ("RETURNED", "PAPER_SETTLEMENT"):
                    raise ValueError("Select a confirmed return or closure from the paper record.")
            else:
                row.pop("closure_basis")
        explicit_renewal = bool(set(row) & renewal_fields)
        if explicit_renewal and row["kind"] != "RENEW":
            if any(row[name] not in (None, "") for name in renewal_fields):
                raise ValueError("Enter renewal fields only for a renewal transaction.")
            for name in renewal_fields:
                del row[name]
        if row["kind"] not in ("PAYMENT", "RENEW", "CLOSE"):
            raise ValueError("Only receipts, renewals and full closures are supported.")
        if item_split is not None:
            from .paper_repayments import normalize_item_split
            if row["kind"] != "PAYMENT":
                raise ValueError("Item receipt splits apply only to payments.")
            row["item_principal_split"] = normalize_item_split(item_split)
        actual = date.fromisoformat(row["date"])
        if not previous <= actual <= through:
            raise ValueError("Enter transactions chronologically, no later than the records-complete-through date.")
        previous = actual
        row["amount"] = _amount(row["amount"], "amount received", positive=row["kind"] == "PAYMENT")
        row["reference"] = _text(row["reference"], "a distinct paper transaction reference")
        if identity(row["reference"]) in refs:
            raise ValueError("Each paper transaction needs its own distinct receipt or book/page reference.")
        refs.add(identity(row["reference"]))
        if row["kind"] == "RENEW":
            if collateral is not None and len(collateral) > 1:
                raise ValueError("Record multi-item paper loans independently. This optional linked-history shortcut requires separate successor item agreements.")
            renewals += 1
            if explicit_renewal:
                if row["renewal_method"] not in ("CARRY", "REPAY_REDRAW") or row["custody"] not in ("HELD", "RETURNED_REPLEDGED"):
                    raise ValueError("Select how the renewal was funded and whether collateral stayed held or was returned and repledged.")
                for name in ("new_principal", "cash_paid", "interest_offset"):
                    row[name] = _amount(row[name], name.replace("_", " "), positive=name == "new_principal")
                if row["custody"] == "RETURNED_REPLEDGED":
                    row["recipient"] = _text(row["recipient"], "who actually received and repledged the collateral", 255)
                elif row["recipient"]:
                    raise ValueError("Collateral stayed held; remove the collateral-return recipient.")
            row["number"] = _text(row["number"], "the successor loan number", 64)
            row["rate"] = _amount(row["rate"], "successor monthly rate", places=6)
            if type(row["tenure"]) is not int or not 1 <= row["tenure"] <= 600 or Decimal(row["rate"]) > 999:
                raise ValueError("Enter the successor's agreed rate and tenure.")
        elif row["kind"] == "CLOSE":
            row["number"] = _text(row["number"], "the original release number", 64) if row["number"] else ""
            row["recipient"] = (None if historical_source and row["recipient"] is None else _text(row["recipient"], "who actually received the collateral", 255)
                if row.get("closure_basis", "RETURNED") == "RETURNED" else "")
            if index != len(value["events"]) - 1:
                raise ValueError("Full return must be the final transaction.")
    if renewals > 5 or (value["final_state"] == "CLOSED") != bool(value["events"] and value["events"][-1]["kind"] == "CLOSE"):
        raise ValueError("A closed history needs a final full return; at most five renewals are supported.")
    monthly = monthly_interest(collateral, quantum) if collateral is not None else (Decimal(value["principal"]) * Decimal(value["rate"]) / 100).quantize(quantum.normalize(), rounding=ROUND_HALF_UP)
    if Decimal(value["cash_paid"]) != Decimal(value["principal"]) - monthly * value["advance_months"] - Decimal(value.get("document_charge", "0")):
        raise ValueError("Original proceeds must equal principal less agreed advance interest and document charge.")
    value["currency_quantum"] = str(quantum.normalize())
    return value


def _authorize(workspace, actor, data=None):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied("Paper entry requires the matching active Workspace.")
    require_workspace_action(workspace, actor, "data.create", "loan.disburse")
    if data and data["events"]:
        require_workspace_action(workspace, actor, "loan.repay", "loan.accrue")
        if any(r["kind"] != "PAYMENT" for r in data["events"]):
            require_workspace_action(workspace, actor, "loan.release")


def new_recording_intent(*, workspace, actor, draft_id=None):
    _authorize(workspace, actor)
    return signing.dumps(dict(workspace=workspace.pk, actor=actor.pk, key=str(uuid4()), draft_id=draft_id), salt=INTENT_SALT)


def _intent(token, workspace, actor, draft_id=None):
    try:
        intent = signing.loads(token or "", salt=INTENT_SALT)
        if (intent["workspace"], intent["actor"]) != (workspace.pk, actor.pk):
            raise PermissionDenied("This paper-entry form belongs to another Workspace or user.")
        if intent.get("draft_id") != draft_id:
            raise ValueError("This submission belongs to a different draft or entry purpose.")
        return UUID(intent["key"])
    except (signing.BadSignature, KeyError, TypeError, ValueError) as exc:
        raise ValueError("Open a fresh paper-entry form; its submission reference is invalid.") from exc


@transaction.atomic
def preview_recorded_history(*, workspace, actor, data, intent_token, draft_id=None):
    data = validate_input(data)
    _authorize(workspace, actor, data)
    key = _intent(intent_token, workspace, actor, draft_id)
    Company.all_objects.select_for_update().get(pk=workspace.pk)
    with transaction.atomic():
        _, review = _admit(workspace, actor, data, key, draft_id=draft_id)
        transaction.set_rollback(True)
    token = signing.dumps(dict(workspace=workspace.pk, actor=actor.pk, key=str(key),
        data=_digest(data), review=review), salt=SALT, compress=True)
    return review, token


@transaction.atomic
def admit_recorded_history(*, workspace, actor, data, intent_token, review_token, confirmed=False, draft_id=None):
    data = validate_input(data)
    _authorize(workspace, actor, data)
    key = _intent(intent_token, workspace, actor, draft_id)
    Company.all_objects.select_for_update().get(pk=workspace.pk)
    if draft_id is not None:
        from .completed_payouts import draft_source
        candidate = draft_source(workspace, actor, draft_id)
        existing = candidate if candidate.disbursal_snapshots.exists() else None
        if existing and (not existing.disbursal_snapshot or existing.disbursal_snapshot.evidence.get("recording", {}).get("admission", {}).get("key") != str(key)):
            raise ValueError("Another payout has already been recorded for this draft. Open its existing loan.")
    else:
        existing = m.PawnLoan.objects.filter(workspace=workspace, creation_submission_id=key).first()
    if existing:
        admission = existing.disbursal_snapshot.evidence["recording"]["admission"]
        if admission["request_sha256"] != _digest(data):
            raise ValueError("This submission already recorded different facts. Open its existing history.")
        return existing, False
    if confirmed is not True:
        raise ValueError("Review and confirm the reconciled history before recording it.")
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except (signing.BadSignature, TypeError, ValueError) as exc:
        raise ValueError("Preview the history again; its review is missing or expired.") from exc
    if any(signed.get(k) != v for k, v in dict(workspace=workspace.pk, actor=actor.pk, key=str(key), data=_digest(data)).items()):
        raise ValueError("The history or recording context changed. Preview again.")
    loan, review = _admit(workspace, actor, data, key, draft_id=draft_id)
    if signed["review"] != review:
        raise ValueError("Numbering or calculated results changed since review. Preview again.")
    return loan, True


def _make_contract(workspace, actor, data, key, *, number, day, principal, rate, tenure, advance, predecessor=None, custody_state="IN_VAULT", archive_ids=(), draft=None, historical_setup=None):
    series = m.LoanSeries.objects.select_related("license").get(pk=data["series_id"], workspace=workspace)
    product = m.LoanProductVersion.objects.select_related("product").get(pk=data["product_version_id"], workspace=workspace)
    if (product.status != "ACTIVE" and not draft and not historical_setup) or product.repayment_structure not in ("SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT") or product.amortisation_method != "NONE":
        raise ValueError("Select a non-amortising monthly bullet/flexible contract matching the paper agreement.")
    if not product.minimum_tenor_months <= tenure <= product.maximum_tenor_months:
        raise ValueError("The original tenure does not match the selected contract version.")
    claim_number(series, number, kind="PAWN_LOAN", actor=actor, archive_ids=archive_ids,
        existing_loan_id=draft.pk if draft else None)
    borrower = Party.objects.get(pk=data["borrower_id"], workspace=workspace, **({} if draft or historical_setup else {"status": "ACTIVE"}))
    loan = draft or m.PawnLoan(workspace=workspace, borrower=borrower, license=series.license,
        series=series, product_version=product, loan_number=number, loan_date=day, principal_amount=principal,
        monthly_interest_rate=rate, tenure_months=tenure, created_by=actor, updated_by=actor,
        creation_submission_id=key if predecessor is None else None)
    if not draft:
        if historical_setup:
            loan.license_revision = historical_setup["revision"]
        loan.full_clean()
        loan.save()
    from .recorded_items import contract_items, ITEM_PROFILE
    if draft:
        from .completed_payouts import apply_actual_contract
        items = apply_actual_contract(draft, data, actor=actor)
    else:
        items = []
    for facts in (() if draft else contract_items(dict(data, principal=str(principal), rate=str(rate)))):
        item = m.PawnCollateralItem(loan=loan, quantity=facts["quantity"], description=facts["description"], metal=facts["metal"],
            gross_weight=Decimal(facts["gross_weight"]), net_weight=Decimal(facts["net_weight"]), purity_percentage=Decimal(facts["purity"]),
            allocated_principal=Decimal(facts["principal"]) if data.get("collateral") else principal,
            monthly_interest_rate=Decimal(facts["rate"]) if data.get("collateral") else rate,
            renewed_from=predecessor, custody_state=custody_state)
        item.full_clean()
        item.save()
        items.append(item)
    quantum = Decimal(data.get("currency_quantum", "0.01")).normalize()
    policy = m.LoanPolicySnapshot.objects.create(loan=loan, policy_version=POLICY_VERSION, basis="RECORDED_CONTRACT", interest_method="SIMPLE",
        partial_month_method="FULL_MONTH", valuation_method=data["monitoring_method"], maximum_ltv_ratio=Decimal(data["monitoring_ltv"]),
        rounding_method="PER_ACCRUAL_PERIOD", currency_quantum=quantum)
    if draft:
        loan.policy_snapshot = policy
        loan.save(update_fields=["policy_snapshot"])
    tranches = []
    for item in items:
        charge = (item.allocated_principal * item.monthly_interest_rate / 100).quantize(quantum, rounding=ROUND_HALF_UP)
        tranches.append(dict(collateral_item_id=item.pk, allocated_principal=str(item.allocated_principal),
            monthly_interest_rate=str(item.monthly_interest_rate), monthly_interest=str(charge),
            advance_interest=str(charge * data.get("advance_months", 0))))
    monthly = sum((Decimal(row["monthly_interest"]) for row in tranches), Decimal("0"))
    # Legacy renewal callers supply an already calculated advance, with no itemized data.
    if not data.get("collateral"):
        tranches[0]["advance_interest"] = str(advance)
    fields = {name: str(getattr(policy, name)) if isinstance(getattr(policy, name), Decimal) else getattr(policy, name)
              for name in CONTRACT_POLICY_FIELDS}
    collateral = [dict(item_id=item.pk, description=item.description, metal=item.metal, quantity=item.quantity,
        gross_weight=str(item.gross_weight), net_weight=str(item.net_weight), purity_percentage=str(item.purity_percentage),
        monthly_interest_rate=str(item.monthly_interest_rate), latest_appraised_value=None) for item in items]
    recording = dict(schema="recorded-origination/1" if predecessor is None else "recorded-renewal/1",
        source_reference=data["source_reference"], payout_already_occurred=predecessor is None,
        original_actor=None, date_precision="DAY", occurred_on=day.isoformat(), collection_profile=RECORDED_PROFILE,
        advance_interest=str(advance), terms=dict(loan_number=number, principal_amount=str(principal),
            monthly_interest_rate=str(rate), tenure_months=tenure, interest_policy=fields, collateral=collateral),
        monitoring=dict(selected_on=timezone.localdate().isoformat(), valuation_method=policy.valuation_method,
            maximum_ltv_ratio=str(policy.maximum_ltv_ratio), reason=data["monitoring_reason"]),
        admission=dict(key=str(key), request_sha256=_digest(data), complete_through=data["complete_through"],
                       entered_by=actor.pk, confirmed_complete=data["confirmed_history"]))
    if data.get("entry_note"):
        recording["entry_note"] = data["entry_note"]
    if historical_setup:
        recording["source_claims"] = historical_setup["source_claims"]
        recording["original_actor"] = historical_setup["source_claims"]["original_actor"]
    return loan, items[0], policy, recording, tranches, monthly


def _admit(workspace, actor, data, key, *, archive=None, draft_id=None, historical_setup=None):
    draft = source = None
    if draft_id is not None:
        from .completed_payouts import draft_source, require_unpaid_draft, source_evidence
        draft = draft_source(workspace, actor, draft_id)
        require_unpaid_draft(draft)
        source = source_evidence(draft)
    references = () if historical_setup else m.PawnLoanEvent.objects.filter(loan__workspace=workspace,
            event_kind="DISBURSAL", payload__recording__collection_profile__in=(PROFILE, "recorded-anniversary/2", RECORDED_PROFILE)).values_list(
                "payload__recording__source_reference", flat=True)
    for reference in references:
        if isinstance(reference, str) and identity(reference) == identity(data["source_reference"]):
            raise ValueError("This paper loan source reference is already recorded; open its existing loan.")
    before = dict(m.LoanNumberSequence.objects.filter(workspace=workspace).values_list("pk", "next_number"))
    principal, rate = Decimal(data["principal"]), Decimal(data["rate"])
    from .recorded_items import monthly_interest, contract_items
    monthly = monthly_interest(contract_items(data), Decimal(data.get("currency_quantum", "0.01")))
    advance = monthly * data["advance_months"]
    original, item, policy, recording, tranches, monthly = _make_contract(workspace, actor, data, key,
        number=data["number"], day=date.fromisoformat(data["date"]), principal=principal, rate=rate,
        tenure=data["tenure"], advance=advance, archive_ids=archive["snapshot_ids"] if archive else (), draft=draft,
        historical_setup=historical_setup)
    if source:
        recording["draft_source"] = source
    fees = Decimal(data.get("document_charge", "0"))
    fee_rows = [dict(kind="DOCUMENT_CHARGE", amount=str(fees), deducted=True)] if fees else []
    if "payout_basis" in data:
        recording["funding"] = dict(basis=data["payout_basis"], proceeds_after_deductions=data["cash_paid"],
            actual_cash_paid=data["cash_paid"] if data["payout_basis"] == "CASH" else None,
            document_charge=str(fees))
    if archive:
        recording["archive_admission"] = archive
    payload = disbursal_payload(original, effective_date=original.loan_date, principal_amount=principal,
        net_cash_amount=Decimal(data["cash_paid"]), advance_interest_amount=advance, deducted_fee_amount=fees).to_dict()
    payload.update(recording=recording, recorded_admission=str(key), disbursal=dict(basis="RECORDED",
        approval_snapshot_id=None, policy_snapshot_id=policy.pk, advance_interest_periods=data["advance_months"],
        monthly_interest=str(monthly), tranches=tranches, fees=fee_rows))
    event, _ = record_loan_event(original.pk, event_kind="DISBURSAL", effective_date=original.loan_date, payload=payload, actor=actor)
    m.PawnLoanDisbursalSnapshot.objects.create(loan=original, basis="RECORDED", policy_snapshot=policy, loan_event=event,
        gross_principal=principal, monthly_interest=monthly, advance_interest_periods=data["advance_months"],
        advance_interest=advance, deducted_fees=fees, net_disbursed=Decimal(data["cash_paid"]),
        evidence=dict(recording=recording, tranches=tranches, fees=fee_rows), created_by=actor)
    _activate(original, event, actor)
    current, loans = original, [original]
    rows = [dict(kind="Paper proceeds" if data.get("payout_basis") == "PROCEEDS" else "Original payout", date=data["date"], number=data["number"], cash=data["cash_paid"],
                 cash_received="0", cash_paid=data["cash_paid"], principal=str(principal), interest=str(advance))]
    for index, row in enumerate(data["events"]):
        day, amount = date.fromisoformat(row["date"]), Decimal(row["amount"])
        request_key = f"admission:{key}:{index}"
        if row["kind"] == "PAYMENT":
            from .paper_repayments import _evidence
            from .pawn_repayment import _record_pawn_loan_repayment_at
            split = row.get("item_principal_split")
            if split is not None:
                item_ids = list(current.collateral_items.order_by("pk").values_list("pk", flat=True))
                if any(int(position) < 1 or int(position) > len(item_ids) for position in split):
                    raise ValueError("Receipt split references an unknown collateral row.")
                split = {str(item_ids[int(position) - 1]): amount for position, amount in split.items()}
            result = _record_pawn_loan_repayment_at(current.pk, amount=amount, request_key=request_key, actor=actor,
                effective_date=day, recording_evidence=_evidence(received_on=day, receipt_reference=row["reference"], amount=amount, item_principal_split=split),
                admission_key=str(key))
            rows.append(dict(kind="Receipt", date=row["date"], number=current.loan_number, cash=str(amount),
                cash_received=str(amount), cash_paid="0",
                principal=str(result.allocation.principal), interest=str(result.allocation.interest)))
        elif row["kind"] == "CLOSE":
            from .pawn_release import _release_pawn_loan_in_full_at
            result = _release_pawn_loan_in_full_at(current.pk, settlement_amount=amount, request_key=request_key,
                actor=actor, effective_date=day, interest_concession=Decimal("0"), concession_reason="",
                recorded_number=row["number"] or None, paper_evidence=dict(profile="recorded-history-closure/1", date_precision="DAY",
                    original_release_number=row["number"] or None,
                    number_basis="ORIGINAL_PAPER" if row["number"] else "SYSTEM_ASSIGNED",
                    paper_reference=row["reference"], collector_name=row["recipient"], original_actor=None, admission_key=str(key),
                    closure_basis=row.get("closure_basis", "RETURNED")))
            current.refresh_from_db()
            rows.append(dict(kind="Paper settlement; handover unconfirmed" if row.get("closure_basis") == "PAPER_SETTLEMENT" else "Full return", date=row["date"], number=current.loan_number, cash=str(amount),
                closing_number=result.release.release_number,
                number_basis="ORIGINAL_PAPER" if row["number"] else "SYSTEM_ASSIGNED",
                cash_received=str(amount), cash_paid="0",
                principal=str(result.release.principal_amount), interest=str(result.release.interest_amount)))
        else:
            from .recorded_renewals import record_admission_renewal
            current, summary = record_admission_renewal(workspace, actor, data, key, current, row, request_key)
            loans.append(current)
            rows.append(summary)
    if current.state != data["final_state"]:
        raise ValueError("The final financial and collateral state does not reconcile to the paper history.")
    summaries = []
    for loan in loans:
        loan.refresh_from_db()
        from .transaction_reviews import _store
        if data["confirmed_history"]:
            _store(loan, actor, through_date=date.fromisoformat(data["complete_through"]), confirmed_complete=True,
                   source_reference=data["source_reference"], request_key=f"admission:{key}")
        balance = collection_balance(loan, date.fromisoformat(data["complete_through"])) if loan.state == "ACTIVE" else get_pawn_loan_balance(loan, as_of_date=date.fromisoformat(data["complete_through"]))
        summaries.append(dict(number=loan.loan_number, state=loan.state, principal=str(balance.principal_outstanding),
                              interest=str(balance.interest_outstanding), custody=loan.collateral_items.order_by("pk").first().custody_state))
    counters = [dict(series=s.series_id, kind=s.document_kind, before=before[s.pk], after=s.next_number)
                for s in m.LoanNumberSequence.objects.filter(workspace=workspace).order_by("pk") if before[s.pk] != s.next_number]
    review = dict(rows=rows, loans=summaries, counters=counters,
        complete_through=data["complete_through"], confirmed_complete=data["confirmed_history"])
    if source:
        review["draft_source"] = source
    return original, review


def _activate(loan, event, actor):
    previous_state = loan.state
    persist_disbursal_repayment_schedule(loan, source_event=event, disbursed_on=event.effective_date,
                                       currency_quantum=loan.policy_snapshot.currency_quantum.normalize(), actor=actor)
    loan.state = "ACTIVE"
    loan.save(update_fields=["state"])
    m.LoanChangeLog.objects.create(loan=loan, event_kind="DISBURSED" if event.event_kind == "DISBURSAL" else "RENEWAL_SUCCESSOR_ACTIVATED", from_state=previous_state, to_state="ACTIVE",
        actor=actor, reason="Recorded completed payout and supported paper activity", metadata=dict(source_event_id=event.pk, recorded_history=True))
