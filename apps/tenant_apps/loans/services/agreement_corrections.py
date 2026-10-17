"""Shared original-agreement correction review; no new cash or custody action."""

from copy import deepcopy
from datetime import date
from decimal import Decimal

from django.core import signing
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import LOANS_ADMIN_ACTION
from apps.tenant_apps.loans.selectors.transaction_completeness import (
    transaction_fingerprint,
    capture_contract_fingerprint,
)
from .action_access import require_loan_action
from .recorded_history import _digest
from .recorded_contract_corrections import _facts

PROFILE = "loan-agreement-correction/1"
SALT = "loans.agreement-correction.v1"


def locked_agreement(loan_id, actor):
    workspace = m.current_tenant_workspace_id()
    if workspace is None:
        raise ValueError("Agreement correction requires an active Workspace.")
    try:
        loan = m.PawnLoan.objects.select_for_update().get(
            pk=loan_id, workspace_id=workspace
        )
    except m.PawnLoan.DoesNotExist:
        raise ValueError("Loan was not found in the active Workspace.") from None
    require_loan_action(loan, actor, LOANS_ADMIN_ACTION, "loan.repay", "loan.accrue")
    return loan


def _agreement(loan_id):
    workspace = m.current_tenant_workspace_id()
    if workspace is None:
        raise ValueError("Agreement correction requires an active Workspace.")
    try:
        return m.PawnLoan.objects.get(pk=loan_id, workspace_id=workspace)
    except m.PawnLoan.DoesNotExist:
        raise ValueError("Loan was not found in the active Workspace.") from None


def agreement_revision(loan):
    snapshot = (
        loan.disbursal_snapshot
        if getattr(loan, "disbursal_snapshot_id", None)
        else None
    )
    return (
        snapshot.evidence.get("agreement_correction", {}).get("revision", 1)
        if snapshot
        else 1
    )


def agreement_notice_identity(loan):
    correction = (
        loan.change_log.filter(
            Q(metadata__agreement_correction__isnull=False)
            | Q(metadata__history_correction__operation="CONTRACT")
        )
        .order_by("pk")
        .last()
    )
    return dict(correction_id=correction.pk) if correction else None


def corrected_agreement_source(loan, source):
    snapshot = (
        loan.disbursal_snapshot
        if getattr(loan, "disbursal_snapshot_id", None)
        else None
    )
    if snapshot is None or snapshot.basis != "CORRECTED":
        return source
    validate_corrected_snapshot(snapshot)
    source = deepcopy(source)
    correction = snapshot.evidence["agreement_correction"]
    source.update(
        loan_date=correction["original_date"],
        principal_amount=str(snapshot.gross_principal),
        monthly_interest_rate=correction["rate"],
    )
    source["collateral_economics"] = dict(
        source.get("collateral_economics", {}),
        gross_principal=str(snapshot.gross_principal),
        monthly_interest=str(snapshot.monthly_interest),
        advance_interest=str(snapshot.advance_interest),
        net_disbursed=str(snapshot.net_disbursed),
        tranches=deepcopy(snapshot.evidence["tranches"]),
    )
    return source


def agreement_document_fingerprint(loan, source_fingerprint):
    opening = (
        loan.loan_events.filter(event_kind="OPENING_CORRECTION").order_by("pk").last()
        if hasattr(loan, "loan_events")
        else None
    )
    if opening:
        return _digest(
            dict(source=source_fingerprint, checkpoint=opening.payload_fingerprint)
        )
    if agreement_revision(loan) == 1:
        return source_fingerprint
    return _digest(
        dict(
            source=source_fingerprint,
            agreement=loan.disbursal_snapshot.loan_event.payload_fingerprint,
        )
    )


def correction_state(loan):
    """Bind all mutable facts, not just the financial event counter."""
    return _digest(
        dict(
            financial=transaction_fingerprint(loan),
            collateral=capture_contract_fingerprint(loan),
            updated_at=loan.updated_at.isoformat(),
            snapshot=loan.disbursal_snapshot_id,
            custody=list(
                loan.collateral_items.order_by("pk").values_list(
                    "pk", "custody_state", "current_storage_location_id"
                )
            ),
            logs=list(loan.change_log.order_by("pk").values_list("pk", "metadata")),
        )
    )


def funding_auction_blockers(loan):
    if (
        loan.auctions.exists()
        or m.FundingPledgeItem.objects.filter(collateral_item__loan=loan).exists()
        or m.FundingLoanDraftCollateral.objects.filter(
            collateral_item__loan=loan
        ).exists()
    ):
        return [
            "Auction or funding dependencies require a connected financial reconciliation."
        ]
    return []


def correction_dependencies(loan):
    from .recorded_collections import recording_for

    if recording_for(loan):
        from .recorded_corrections import dependencies

        events, active, blockers = dependencies(loan)
        blockers.extend(funding_auction_blockers(loan))
        return events, active, blockers
    events = list(loan.loan_events.order_by("effective_date", "pk")[:1001])
    reversed_ids = {e.reversal_of_id for e in events if e.reversal_of_id}
    active = [
        e for e in events if e.event_kind != "REVERSAL" and e.pk not in reversed_ids
    ]
    blockers = []
    if any(e.event_kind == "MIGRATION_OPENING" for e in events):
        blockers.append(
            "A verified opening needs its agreement and cutover balances reviewed separately; earlier transactions must not be invented."
        )
        return events, active, blockers
    from .recorded_settlement_corrections import terminal_for

    try:
        terminal = terminal_for(loan, active)
    except ValueError as exc:
        terminal = None
        blockers.append(str(exc))
    if loan.state != "ACTIVE" and terminal is None:
        blockers.append(
            "This agreement needs a connected settlement review before its financial history can be corrected."
        )
    policy = loan.policy_snapshot if loan.policy_snapshot_id else None
    product = loan.product_version
    if (
        not policy
        or policy.policy_version not in (1, 2)
        or policy.basis != "ORIGINATION"
        or policy.interest_method != "SIMPLE"
        or policy.partial_month_method != "FULL_MONTH"
        or policy.rounding_method != "PER_ACCRUAL_PERIOD"
        or policy.currency_quantum.normalize() not in (Decimal("0.01"), Decimal("1"))
        or product.repayment_structure
        not in ("SINGLE_PAYMENT_BULLET", "FLEXIBLE_PARTIAL_PAYMENT")
        or product.amortisation_method != "NONE"
    ):
        blockers.append(
            "This saved agreement needs a supported monthly financial correction contract."
        )
    if (
        policy
        and policy.policy_version == 1
        and (
            loan.state != "ACTIVE"
            or any(e.event_kind not in {"DISBURSAL", "REVERSAL"} for e in events)
            or loan.interest_accruals.exists()
        )
    ):
        blockers.append(
            "This legacy agreement requires an unserviced disbursal; later charges or payments need connected reconciliation."
        )
    origins = [e for e in active if e.event_kind == "DISBURSAL"]
    if (
        len(origins) != 1
        or not loan.disbursal_snapshot_id
        or loan.disbursal_snapshot.loan_event_id != (origins[0].pk if origins else None)
    ):
        blockers.append(
            "Exactly one current disbursal and its frozen agreement are required."
        )
    if any(
        e.event_kind not in {"DISBURSAL", "REPAYMENT", "INTEREST_ACCRUAL"}
        and e is not terminal
        for e in active
    ):
        blockers.append(
            "Renewal, settlement, capitalization or auction activity requires a connected reconciliation."
        )
    if (
        m.PawnLoanRenewal.objects.filter(source_loan=loan).exists()
        or m.PawnLoanRenewal.objects.filter(successor_loan=loan).exists()
    ):
        blockers.append("Linked renewal agreements require a connected reconciliation.")
    blockers.extend(funding_auction_blockers(loan))
    if not loan.collateral_items.exists() or (
        terminal is None
        and loan.collateral_items.exclude(custody_state="IN_VAULT").exists()
    ):
        blockers.append("Reconcile the retained collateral and custody history first.")
    if len(events) > 1000 or len(active) > 121:
        blockers.append("This history exceeds the supported correction review bound.")
    if any(e.effective_date > timezone.localdate() for e in events):
        blockers.append("Future financial activity must be reconciled first.")
    if any(
        e.event_kind == "REVERSAL"
        and e.payload.get("agreement_correction", {}).get("schema") != PROFILE
        for e in events
    ):
        blockers.append(
            "Earlier reversals outside this agreement correction need separate reconciliation."
        )
    if any(
        e.event_kind == "INTEREST_ACCRUAL" and not hasattr(e, "interest_accrual")
        for e in active
    ):
        blockers.append("Every native charge needs its retained item calculation.")
    return events, active, blockers


def balance_facts(loan):
    from apps.tenant_apps.loans.selectors.servicing_contract import (
        get_servicing_position,
    )

    balance = get_servicing_position(loan, as_of_date=timezone.localdate()).balance
    return {
        key: str(getattr(balance, key + "_outstanding"))
        for key in ("principal", "interest", "fees")
    } | {"total": str(balance.total_due)}


def validate_corrected_snapshot(snapshot):
    """Model/restore validation keeps revised terms distinct from old approval."""
    from django.core.exceptions import ValidationError

    detail = snapshot.evidence.get("agreement_correction", {})
    try:
        previous = m.PawnLoanDisbursalSnapshot.objects.get(
            pk=detail["disbursal_snapshot_id"],
            loan_id=snapshot.loan_id,
            workspace_id=snapshot.workspace_id,
        )
        event = snapshot.loan_event
        expected = (
            previous.evidence.get("agreement_correction", {}).get("revision", 1) + 1
        )
        policy_fields = [
            f.name
            for f in m.LoanPolicySnapshot._meta.fields
            if f.name not in ("id", "loan", "workspace", "created_at")
        ]
        if (
            detail.get("schema") != PROFILE
            or detail.get("role") != "AGREEMENT"
            or type(detail.get("revision")) is not int
            or detail["revision"] != expected
            or detail.get("source_event_id") != previous.loan_event_id
            or not m.PawnLoanEvent.objects.filter(
                reversal_of_id=previous.loan_event_id,
                payload__agreement_correction__request_key=detail["request_key"],
            ).exists()
            or not snapshot.created_by_id
            or event.created_by_id != snapshot.created_by_id
            or snapshot.approval_snapshot_id != previous.approval_snapshot_id
            or snapshot.policy_snapshot.basis != "ORIGINATION"
            or any(
                getattr(snapshot.policy_snapshot, key)
                != getattr(previous.policy_snapshot, key)
                for key in policy_fields
            )
            or event.payload.get("agreement_correction") != detail
            or event.payload.get("disbursal", {}).get("policy_snapshot_id")
            != snapshot.policy_snapshot_id
            or snapshot.evidence["tranches"] != event.payload["disbursal"]["tranches"]
            or Decimal(event.payload["values"]["principal"]) != snapshot.gross_principal
            or Decimal(event.payload["values"]["net_cash"]) != snapshot.net_disbursed
            or snapshot.gross_principal
            != snapshot.net_disbursed
            + snapshot.advance_interest
            + snapshot.deducted_fees
            or sum(
                Decimal(r["allocated_principal"]) for r in snapshot.evidence["tranches"]
            )
            != snapshot.gross_principal
            or sum(
                Decimal(r["monthly_interest"]) for r in snapshot.evidence["tranches"]
            )
            != snapshot.monthly_interest
            or sum(
                Decimal(r["advance_interest"]) for r in snapshot.evidence["tranches"]
            )
            != snapshot.advance_interest
            or not detail.get("reason")
            or not detail.get("reference")
        ):
            raise ValueError()
    except KeyError, TypeError, ValueError, m.PawnLoanDisbursalSnapshot.DoesNotExist:
        raise ValidationError(
            "Corrected agreement must reconcile to its retained source, compensation and reviewed financial facts."
        ) from None


def _native_run(loan, actor, facts, active):
    from .event_recording import record_loan_event
    from .obligations import (
        reverse_event_obligation_allocations,
        reverse_event_schedule_change,
        persist_disbursal_repayment_schedule,
    )
    from apps.tenant_apps.loans.integrations import disbursal_payload, reversal_payload
    from .recorded_items import monthly_interest
    from apps.tenant_apps.loans.domain.interest import calculate_period_interest
    from .pawn_repayment import _record_pawn_loan_repayment_at
    from .pawn_interest import recognize_due_monthly_interest

    if facts.get("adopt_shared_interest") or "predecessor" in facts:
        raise ValueError(
            "This agreement already retains its economic policy; connected settlement changes require their supported review."
        )
    terminal = next((e for e in active if e.event_kind == "RELEASE_RECEIPT"), None)
    if bool(terminal) != bool(facts.get("settlement")):
        raise ValueError(
            "Supply verified settlement cash when correcting a closed agreement; an active loan has no settlement to restate."
        )
    if terminal:
        require_loan_action(loan, actor, "loan.release")
    original = loan.disbursal_snapshot
    items = list(loan.collateral_items.select_for_update().order_by("pk"))
    source_tranches = {
        r["collateral_item_id"]: r for r in original.evidence.get("tranches", [])
    }
    saved_rate = original.evidence.get("agreement_correction", {}).get(
        "rate", original.approval_snapshot.payload.get("monthly_interest_rate")
    )
    if (
        loan.loan_date != original.loan_event.effective_date
        or loan.principal_amount != original.gross_principal
        or loan.policy_snapshot_id != original.policy_snapshot_id
        or set(source_tranches) != {i.pk for i in items}
        or any(
            i.allocated_principal
            != Decimal(source_tranches[i.pk]["allocated_principal"])
            or i.monthly_interest_rate
            != Decimal(source_tranches[i.pk]["monthly_interest_rate"])
            for i in items
        )
        or (
            saved_rate is not None
            and loan.monthly_interest_rate != Decimal(str(saved_rate))
        )
    ):
        raise ValueError(
            "Current agreement facts do not match their retained financial source. Reconcile that evidence first."
        )
    if len(items) > 1 and "items" not in facts:
        raise ValueError(
            "Correct every retained item's original principal and rate explicitly."
        )
    rows = facts.get(
        "items",
        [dict(item_id=items[0].pk, principal=facts["principal"], rate=facts["rate"])],
    )
    if len(rows) != len(items) or {r["item_id"] for r in rows} != {i.pk for i in items}:
        raise ValueError(
            "Corrected item agreements must match this loan's collateral exactly."
        )
    receipts = [e for e in active if e.event_kind == "REPAYMENT"]
    if set(facts.get("replay_item_splits", {})) - {str(e.pk) for e in receipts}:
        raise ValueError(
            "A replay split references a receipt outside this active history."
        )
    day = date.fromisoformat(facts["date"])
    if any(
        e.effective_date < day
        for e in active
        if e.event_kind in {"REPAYMENT", "RELEASE_RECEIPT"}
    ):
        raise ValueError(
            "The corrected original date cannot follow a retained receipt or settlement."
        )
    if (
        day == loan.loan_date
        and Decimal(facts["principal"]) == loan.principal_amount
        and all(
            Decimal(r["principal"]) == i.allocated_principal
            and Decimal(r["rate"]) == i.monthly_interest_rate
            for i in items
            for r in rows
            if r["item_id"] == i.pk
        )
    ):
        raise ValueError("No agreement facts have changed.")
    before_position = balance_facts(loan)
    before = dict(
        date=loan.loan_date.isoformat(),
        principal=str(loan.principal_amount),
        rate=str(loan.monthly_interest_rate),
        balance=before_position["total"],
        position=before_position,
        proceeds=str(original.net_disbursed),
    )
    item_review = [
        dict(
            item_id=i.pk,
            description=i.description,
            old_principal=str(i.allocated_principal),
            old_rate=str(i.monthly_interest_rate),
            principal=r["principal"],
            rate=r["rate"],
        )
        for i in items
        for r in rows
        if r["item_id"] == i.pk
    ]
    quantum = loan.policy_snapshot.currency_quantum.normalize()

    def retained_monthly(item_rows):
        if loan.policy_snapshot.policy_version == 1:
            return sum(
                (
                    calculate_period_interest(
                        calculation_base=row["principal"],
                        monthly_interest_rate=row["rate"],
                        period_fraction=Decimal("1"),
                        currency_quantum=quantum,
                    )[1]
                    for row in item_rows
                ),
                Decimal("0"),
            )
        return monthly_interest(item_rows, quantum)

    monthly = retained_monthly(rows)
    advance = monthly * original.advance_interest_periods
    if (
        Decimal(facts["principal"])
        != Decimal(facts["cash_paid"]) + advance + original.deducted_fees
    ):
        raise ValueError(
            "Corrected proceeds must equal principal less advance interest and the retained deducted document charge."
        )
    context = dict(
        schema=PROFILE,
        operation="CONTRACT",
        role="AGREEMENT",
        revision=agreement_revision(loan) + 1,
        request_key=facts["request_key"],
        request_sha256=_digest(facts),
        reason=facts["reason"],
        reference=facts["reference"],
        disbursal_snapshot_id=original.pk,
        source_event_id=original.loan_event_id,
        original_date=day.isoformat(),
        principal=facts["principal"],
        rate=facts["rate"],
        proceeds=facts["cash_paid"],
    )
    if loan.policy_snapshot.policy_version == 1:
        context["policy_version"] = 1
    for event in reversed(active):
        payload = reversal_payload(
            loan,
            effective_date=event.effective_date,
            original_event_id=event.pk,
            original_event_kind=event.event_kind,
            values=event.payload["values"],
            reason=facts["reason"],
        ).to_dict()
        payload["agreement_correction"] = dict(
            context, role="COMPENSATION", source_event_id=event.pk
        )
        reverse, _ = record_loan_event(
            loan.pk,
            event_kind="REVERSAL",
            effective_date=event.effective_date,
            payload=payload,
            actor=actor,
            reversal_of=event,
        )
        reverse_event_obligation_allocations(
            original_event=event, reversal_event=reverse, actor=actor
        )
        reverse_event_schedule_change(
            original_event=event, reversal_event=reverse, actor=actor
        )
    if terminal:
        # Private calculation state inside the atomic correction, never a public
        # reopening or a physical return reversal. Restore CLOSED before commit.
        loan.state = "ACTIVE"
        loan.save(update_fields=["state"])
    old_policy = loan.policy_snapshot
    policy = m.LoanPolicySnapshot.objects.create(
        workspace_id=loan.workspace_id,
        loan=loan,
        **{
            f.name: getattr(old_policy, f.name)
            for f in m.LoanPolicySnapshot._meta.fields
            if f.name not in ("id", "loan", "workspace", "created_at")
        },
    )
    loan.loan_date, loan.principal_amount, loan.monthly_interest_rate = (
        day,
        Decimal(facts["principal"]),
        Decimal(facts["rate"]),
    )
    loan.policy_snapshot = policy
    loan.save(
        update_fields=[
            "loan_date",
            "principal_amount",
            "monthly_interest_rate",
            "policy_snapshot",
            "updated_at",
        ]
    )
    tranches = []
    for item in items:
        row = next(r for r in rows if r["item_id"] == item.pk)
        item.allocated_principal, item.monthly_interest_rate = Decimal(
            row["principal"]
        ), Decimal(row["rate"])
        item.save(
            update_fields=["allocated_principal", "monthly_interest_rate", "updated_at"]
        )
        charge = retained_monthly([row])
        tranches.append(
            dict(
                collateral_item_id=item.pk,
                allocated_principal=row["principal"],
                monthly_interest_rate=row["rate"],
                monthly_interest=str(charge),
                advance_interest=str(charge * original.advance_interest_periods),
            )
        )
    payload = disbursal_payload(
        loan,
        effective_date=day,
        principal_amount=loan.principal_amount,
        net_cash_amount=Decimal(facts["cash_paid"]),
        advance_interest_amount=advance,
        deducted_fee_amount=original.deducted_fees,
    ).to_dict()
    payload["disbursal"] = dict(
        basis="CORRECTED",
        approval_snapshot_id=original.approval_snapshot_id,
        policy_snapshot_id=policy.pk,
        advance_interest_periods=original.advance_interest_periods,
        monthly_interest=str(monthly),
        tranches=tranches,
        fees=deepcopy(original.evidence.get("fees", [])),
    )
    payload["agreement_correction"] = context
    event, _ = record_loan_event(
        loan.pk,
        event_kind="DISBURSAL",
        effective_date=day,
        payload=payload,
        actor=actor,
    )
    snapshot = m.PawnLoanDisbursalSnapshot.objects.create(
        workspace_id=loan.workspace_id,
        loan=loan,
        basis="CORRECTED",
        approval_snapshot_id=original.approval_snapshot_id,
        policy_snapshot=policy,
        loan_event=event,
        gross_principal=loan.principal_amount,
        monthly_interest=monthly,
        advance_interest_periods=original.advance_interest_periods,
        advance_interest=advance,
        deducted_fees=original.deducted_fees,
        net_disbursed=Decimal(facts["cash_paid"]),
        created_by=actor,
        evidence=dict(
            agreement_correction=context,
            tranches=tranches,
            fees=deepcopy(original.evidence.get("fees", [])),
        ),
    )
    loan.disbursal_snapshot = snapshot
    loan.save(update_fields=["disbursal_snapshot", "updated_at"])
    persist_disbursal_repayment_schedule(
        loan,
        source_event=event,
        disbursed_on=day,
        currency_quantum=quantum,
        actor=actor,
    )
    review_rows = []
    for index, source in enumerate(active):
        if source.event_kind == "REPAYMENT":
            evidence = deepcopy(source.payload["repayment"].get("recording"))
            if str(source.pk) in facts.get("replay_item_splits", {}):
                if evidence is None:
                    raise ValueError(
                        "A system receipt retains its original allocation rule; paper item splits cannot be substituted."
                    )
                evidence["item_principal_split"] = facts["replay_item_splits"][
                    str(source.pk)
                ]
            result = _record_pawn_loan_repayment_at(
                loan.pk,
                amount=source.payload["repayment"]["amount_received"],
                request_key=f"agreement:{facts['request_key']}:{index}",
                actor=actor,
                effective_date=source.effective_date,
                recording_evidence=evidence,
                correction_evidence=dict(
                    context, role="REPLAY", source_event_id=source.pk
                ),
            )
            review_rows.append(
                dict(
                    date=source.effective_date.isoformat(),
                    reference=(evidence or {}).get("receipt_reference")
                    or f"Receipt #{source.pk}",
                    amount=source.payload["repayment"]["amount_received"],
                    principal=str(result.allocation.principal),
                    interest=str(result.allocation.interest),
                    old_principal=source.payload["values"]["principal"],
                    old_interest=source.payload["values"]["interest"],
                )
            )
        elif source.event_kind == "INTEREST_ACCRUAL":
            recognize_due_monthly_interest(
                loan, max(day, source.effective_date), actor=actor
            )
    if terminal:
        from .recorded_settlement_corrections import restate_settlement

        review_rows.append(
            restate_settlement(
                loan, terminal, actor=actor, facts=facts["settlement"], context=context
            )
        )
        loan.state = "CLOSED"
        loan.save(update_fields=["state"])
    after_position = balance_facts(loan)
    return dict(
        before=before,
        after=dict(
            date=day.isoformat(),
            principal=facts["principal"],
            rate=facts["rate"],
            balance=after_position["total"],
            position=after_position,
        ),
        rows=review_rows,
        proceeds=facts["cash_paid"],
        advance_interest=str(advance),
        reason=facts["reason"],
        reference=facts["reference"],
        history_basis="FROM_ORIGINATION",
        revision=context["revision"],
        items=item_review,
    )


@transaction.atomic
def preview_agreement_correction(loan_id, *, actor, data):
    loan = _agreement(loan_id)
    if loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
        from .opening_corrections import preview_opening_correction

        return preview_opening_correction(loan_id, actor=actor, data=data)
    facts = _facts(data)
    from .recorded_collections import recording_for

    if recording_for(loan):
        from .recorded_contract_corrections import preview_contract_correction, _lock

        _, _, loan = _lock(loan_id)
        require_loan_action(
            loan, actor, LOANS_ADMIN_ACTION, "loan.repay", "loan.accrue"
        )
        blockers = correction_dependencies(loan)[2]
        if blockers:
            raise ValueError(" ".join(blockers))
        review, token = preview_contract_correction(loan_id, actor=actor, data=data)
        return review, signing.dumps(
            dict(
                mode="KNOWN_TIMELINE",
                loan=loan.pk,
                workspace=loan.workspace_id,
                actor=actor.pk,
                facts=_digest(facts),
                source=correction_state(loan),
                review_token=token,
            ),
            salt=SALT,
            compress=True,
        )
    loan = locked_agreement(loan_id, actor)
    _, active, blockers = correction_dependencies(loan)
    if blockers:
        raise ValueError(" ".join(blockers))
    state = correction_state(loan)
    with transaction.atomic():
        review = _native_run(loan, actor, facts, active)
        transaction.set_rollback(True)
    token = signing.dumps(
        dict(
            loan=loan.pk,
            workspace=loan.workspace_id,
            actor=actor.pk,
            facts=_digest(facts),
            source=state,
            review=review,
        ),
        salt=SALT,
        compress=True,
    )
    return review, token


@transaction.atomic
def record_agreement_correction(loan_id, *, actor, data, review_token, confirmed=False):
    loan = _agreement(loan_id)
    if loan.loan_events.filter(event_kind="MIGRATION_OPENING").exists():
        from .opening_corrections import record_opening_correction

        return record_opening_correction(
            loan_id,
            actor=actor,
            data=data,
            review_token=review_token,
            confirmed=confirmed,
        )
    facts = _facts(data)
    from .recorded_collections import recording_for

    if recording_for(loan):
        from .recorded_contract_corrections import record_contract_correction, _lock

        _, _, loan = _lock(loan_id)
        require_loan_action(
            loan, actor, LOANS_ADMIN_ACTION, "loan.repay", "loan.accrue"
        )
        if confirmed is not True:
            raise ValueError("Confirm the complete agreement correction review.")
        if loan.change_log.filter(
            metadata__history_correction__request_key=facts["request_key"],
            metadata__history_correction__operation="CONTRACT",
        ).exists():
            return record_contract_correction(
                loan_id, actor=actor, data=data, review_token="", confirmed=True
            )
        blockers = correction_dependencies(loan)[2]
        if blockers:
            raise ValueError(" ".join(blockers))
        try:
            signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
        except signing.BadSignature:
            raise ValueError(
                "Preview this agreement correction again; its review is missing or expired."
            ) from None
        if (
            signed.get("mode"),
            signed.get("loan"),
            signed.get("workspace"),
            signed.get("actor"),
            signed.get("facts"),
            signed.get("source"),
        ) != (
            "KNOWN_TIMELINE",
            loan.pk,
            loan.workspace_id,
            actor.pk,
            _digest(facts),
            correction_state(loan),
        ):
            raise ValueError(
                "Loan or dependent facts changed. Preview this agreement correction again."
            )
        return record_contract_correction(
            loan_id,
            actor=actor,
            data=data,
            review_token=signed["review_token"],
            confirmed=True,
        )
    loan = locked_agreement(loan_id, actor)
    if confirmed is not True:
        raise ValueError("Confirm the complete agreement correction review.")
    existing = loan.change_log.filter(
        metadata__agreement_correction__request_key=facts["request_key"]
    ).first()
    if existing:
        if existing.actor_id != actor.pk or existing.metadata["agreement_correction"][
            "request_sha256"
        ] != _digest(facts):
            raise ValueError(
                "This correction request already records different agreement facts."
            )
        return existing, False
    _, active, blockers = correction_dependencies(loan)
    if blockers:
        raise ValueError(" ".join(blockers))
    try:
        signed = signing.loads(review_token or "", salt=SALT, max_age=3600)
    except signing.BadSignature:
        raise ValueError(
            "Preview this agreement correction again; its review is missing or expired."
        ) from None
    if (
        signed.get("loan"),
        signed.get("workspace"),
        signed.get("actor"),
        signed.get("facts"),
        signed.get("source"),
    ) != (loan.pk, loan.workspace_id, actor.pk, _digest(facts), correction_state(loan)):
        raise ValueError(
            "Loan or dependent facts changed. Preview this agreement correction again."
        )
    review = _native_run(loan, actor, facts, active)
    if _digest(review) != _digest(signed.get("review")):
        raise ValueError("The agreement correction calculation changed. Preview again.")
    log = m.LoanChangeLog.objects.create(
        workspace_id=loan.workspace_id,
        loan=loan,
        event_kind="REVERSAL_RECORDED",
        from_state=loan.state,
        to_state=loan.state,
        actor=actor,
        reason=facts["reason"],
        metadata=dict(
            agreement_correction=dict(
                schema=PROFILE,
                request_key=facts["request_key"],
                request_sha256=_digest(facts),
                source_fingerprint=signed["source"],
                review=review,
            )
        ),
    )
    loan.updated_by = actor
    loan.save(update_fields=["updated_by", "updated_at"])
    m.LoanRiskSnapshot.objects.filter(loan=loan).exclude(status="ERROR").update(
        status="STALE", error_message="Agreement corrected; reassessment required."
    )
    return log, True
