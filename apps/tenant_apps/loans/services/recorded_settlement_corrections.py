"""Receipt restatement across an unchanged renewal agreement or full return.

Financial compensation never implies a physical undo/redo. The original document
and custody events remain authoritative for the actual handover and agreement.
"""
from copy import deepcopy
from decimal import Decimal
from django.utils import timezone

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.integrations import release_receipt_payload, renewal_settlement_payload
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from apps.tenant_apps.loans.selectors.recorded_settlements import current_settlement
from .action_access import require_loan_action
from .event_recording import record_loan_event
from .obligations import allocate_event_to_obligations, terminate_active_repayment_schedule
from .pawn_repayment import _locked_loan
from .recorded_collections import collection_balance, recording_for, recognize_collection_interest, scheduled_interest
from .recorded_renewals import reconcile_renewal_cash

TERMINAL_KINDS = ("RELEASE_RECEIPT", "RENEWAL_SETTLEMENT")


def renewal_cash(event):
    """Retain paper facts or explain the original current-system net settlement."""
    detail = event.payload["renewal"]
    if detail.get("cash_evidence"):
        return deepcopy(detail["cash_evidence"])
    if detail.get("returned_source_item_ids") or len(detail.get("retained_source_item_ids", [])) != 1:
        raise ValueError("Current renewal correction requires one unchanged retained collateral group.")
    principal = Decimal(event.payload["values"]["principal"])
    interest = Decimal(event.payload["values"]["interest"])
    paid, advance = Decimal(detail["principal_paid"]), Decimal(detail["top_up_amount"])
    deduction = Decimal(detail["successor_advance_interest"]) + Decimal(detail["successor_deducted_fees"])
    net = advance - paid - interest - deduction
    return dict(schema="recorded-renewal-cash/1", method="NET_SETTLEMENT", custody="HELD",
        source_principal=str(principal), interest_settled=str(interest), principal_paid=str(paid),
        principal_carried=str(principal-paid), gross_advance=str(advance), successor_principal=detail["successor_principal"],
        new_advance_interest=detail["successor_advance_interest"], new_document_charge=detail["successor_deducted_fees"],
        cash_received=str(max(-net, Decimal("0"))), cash_paid=str(max(net, Decimal("0"))),
        interest_offset=str(min(interest, advance)), recipient="", original_basis="CURRENT_SYSTEM_RENEWAL")


def terminal_for(loan, active, *, batch_id=None):
    terminals = [e for e in active if e.event_kind in TERMINAL_KINDS]
    if not terminals:
        return None
    if len(terminals) != 1 or loan.state != "CLOSED":
        raise ValueError("Exactly one completed full closure or renewal is required.")
    items = list(loan.collateral_items.all())
    if len(items) != 1:
        raise ValueError("Settlement correction requires one unchanged collateral group.")
    event = terminals[0]
    if any((e.effective_date, e.pk) > (event.effective_date, event.pk) for e in active if e is not event):
        raise ValueError("Activity after this loan's settlement needs separate reconciliation.")
    root = event.payload.get("history_correction", {}).get("root_event_id") or event.pk
    if event.event_kind == "RELEASE_RECEIPT":
        document = m.PawnLoanRelease.objects.get(loan=loan, loan_event_id=root)
        if not document.is_full_release or hasattr(document, "reversal") or document.interest_concession_amount:
            raise ValueError("Only an unchanged full release without concession is supported.")
        if hasattr(document, "batch_line") and document.batch_line.batch_id != batch_id:
            raise ValueError("A combined release batch needs reconciliation of its shared receipt; single-loan settlement correction cannot change that total.")
        expected = ("PAPER_CLOSED" if event.payload.get("release", {}).get("paper_closure", {}).get("closure_basis") == "PAPER_SETTLEMENT" else "WITH_CUSTOMER")
        from .paper_handover import confirmation_for
        handover = confirmation_for(document) if expected == "PAPER_CLOSED" else None
        restated = event.payload.get("history_correction", {}).get("custody_restatement", {})
        superseded = set(restated.get("superseded", []))
        expected_count = (2 if handover else 1) + len(superseded)
        if document.items.count() != 1 or document.custody_events.count() != expected_count:
            raise ValueError("The original full-return custody evidence is incomplete.")
    else:
        document = m.PawnLoanRenewal.objects.get(source_loan=loan, settlement_event_id=root)
        cash = renewal_cash(event)
        if not recording_for(loan) or hasattr(document, "reversal"):
            raise ValueError("Renewal correction requires the recorded cash profile and unchanged agreement.")
        expected = "RENEWAL_TRANSFERRED" if cash["custody"] == "HELD" else "WITH_CUSTOMER"
        opening = document.successor_loan.loan_events.filter(event_kind="RENEWAL_OPENING", reversed_by_event__isnull=True).last()
        if not opening or Decimal(cash["successor_principal"]) != Decimal(opening.payload["values"]["principal"]):
            raise ValueError("The successor opening has changed; its agreement requires separate reconciliation.")
        successor_items = list(document.successor_loan.collateral_items.all())
        if len(successor_items) != 1 or successor_items[0].renewed_from_id != items[0].pk:
            raise ValueError("The successor collateral no longer matches the recorded agreement.")
    if Decimal(event.payload["values"].get("fees", "0")) or Decimal(event.payload["values"].get("interest_concession", "0")):
        raise ValueError("Settlement fees or concessions require a wider correction profile.")
    if current_settlement(document.loan_event if event.event_kind == "RELEASE_RECEIPT" else document.settlement_event).pk != event.pk:
        raise ValueError("The active settlement does not match its retained document.")
    current_expected = "WITH_CUSTOMER" if event.event_kind == "RELEASE_RECEIPT" and handover else expected
    if len(items) != 1 or items[0].custody_state != current_expected:
        raise ValueError("Collateral custody differs from the recorded settlement; reconcile the physical history first.")
    custody = document.custody_events.filter(collateral_item=items[0], from_state="IN_VAULT", to_state=expected)
    restated = event.payload.get("history_correction", {}).get("custody_restatement", {})
    if restated:
        custody = custody.exclude(pk__in=restated["superseded"])
    custody = custody.first()
    if not custody or custody.from_state != "IN_VAULT" or custody.to_state != expected or custody.effective_date != event.effective_date:
        raise ValueError("The original custody handover does not match this settlement.")
    if event.event_kind == "RELEASE_RECEIPT" and handover:
        confirmation = document.custody_events.filter(pk__in=handover["custody_event_ids"], collateral_item=items[0],
            from_state="PAPER_CLOSED", to_state="WITH_CUSTOMER", effective_date=handover["facts"]["date"]).first()
        if confirmation is None:
            raise ValueError("The later handover confirmation does not match custody evidence.")
    return event


def dependent_state(loan, *, actor, batch_id=None):
    """Lock forward lineage; signed review binds even unchanged later activity."""
    rows, state, current, seen = [], [], loan, set()
    for _ in range(6):
        if current.pk in seen:
            raise ValueError("Renewal lineage contains a cycle.")
        seen.add(current.pk)
        recorded = recording_for(current)
        from .recorded_corrections import dependencies
        _, _, blockers = dependencies(current, batch_id=batch_id) if recorded else (None, None, [])
        if blockers:
            raise ValueError(f"Loan {current.loan_number}: " + " ".join(blockers))
        events = list(current.loan_events.order_by("pk")[:1001])
        if len(events) > 1000:
            raise ValueError("Dependent history exceeds the supported 1,000-event review limit.")
        items = list(current.collateral_items.select_for_update().order_by("pk"))
        custody = list(m.PawnCollateralCustodyEvent.objects.filter(collateral_item__loan=current).order_by("pk").values_list(
            "pk", "collateral_item_id", "from_state", "to_state", "effective_date"))
        state.append(dict(loan=current.pk, status=current.state, policy=current.policy_snapshot_id, as_of=timezone.localdate().isoformat(),
            date=current.loan_date.isoformat(), principal=str(current.principal_amount), rate=str(current.monthly_interest_rate),
            events=[[e.pk, e.payload_fingerprint] for e in events],
            items=[[i.pk, i.custody_state, i.renewed_from_id] for i in items],
            custody=[[pk, item, old, new, day.isoformat()] for pk, item, old, new, day in custody]))
        balance = collection_balance(current, timezone.localdate()) if recorded else get_pawn_loan_balance(current, as_of_date=timezone.localdate())
        rows.append(dict(loan=current.pk, number=current.loan_number, status=current.get_state_display(), date=current.loan_date.isoformat(),
            agreed_principal=str(current.principal_amount), rate=str(current.monthly_interest_rate), tenure=current.tenure_months,
            principal=str(balance.principal_outstanding), interest=str(balance.interest_outstanding),
            custody=", ".join(i.get_custody_state_display() for i in items), events=len(events)))
        renewal = m.PawnLoanRenewal.objects.filter(source_loan=current).first()
        if renewal is None:
            return state, rows
        if hasattr(renewal, "reversal"):
            raise ValueError("Reversed renewal lineage requires separate reconciliation.")
        # Admission creates successors after predecessors. Refuse anomalous links
        # rather than acquire forward locks in the opposite order.
        if renewal.successor_loan_id <= current.pk:
            raise ValueError("Renewal lineage has an unsupported lock order.")
        require_loan_action(current, actor, "loan.release")
        current = _locked_loan(renewal.successor_loan_id)
        require_loan_action(current, actor, "loan.repay", "loan.accrue")
    raise ValueError("This correction supports at most five later renewals.")


def restate_settlement(loan, source, *, actor, facts, context, successor_terms=None, custody_restatement=None):
    from datetime import date
    day = date.fromisoformat(facts["date"]) if facts.get("date") else source.effective_date
    meta = dict(context, role="SETTLEMENT", description="Corrected historical settlement; agreement and custody retained",
        source_event_id=source.pk, root_event_id=source.payload.get("history_correction", {}).get("root_event_id") or source.pk,
        settlement_reference=facts["reference"])
    previous_custody = source.payload.get("history_correction", {}).get("custody_restatement")
    if custody_restatement or previous_custody:
        meta["custody_restatement"] = custody_restatement or previous_custody
    recognize_collection_interest(loan, day, actor=actor, request_key="correction:" + context["request_key"] + ":settlement",
                                  correction_evidence=dict(meta, role="REPLAY", description="Recalculated settlement interest"))
    balance = get_pawn_loan_balance(loan, as_of_date=day)
    principal, interest = balance.principal_outstanding, balance.interest_outstanding
    if balance.fees_outstanding or balance.capitalized_interest_principal_outstanding:
        raise ValueError("Fees and capitalized interest require a wider correction profile.")
    received, paid_out, offset = (Decimal(facts[key]) for key in ("cash_received", "cash_paid", "interest_offset"))
    if source.event_kind == "RELEASE_RECEIPT":
        if received != balance.total_due or paid_out or offset:
            raise ValueError(f"Closure cash does not reconcile: actual received {received}, required {balance.total_due}. "
                             "A full return needs exact settlement; no refund or concession is inferred.")
        payload = release_receipt_payload(loan, effective_date=day, principal_amount=principal,
            interest_amount=interest, fee_amount=0, original_principal_amount=principal,
            capitalized_interest_principal_amount=0).to_dict()
        payload["release"] = deepcopy(source.payload["release"])
        if "recipient" in facts:
            payload["release"]["paper_closure"]["collector_name"] = facts["recipient"]
        old_in = sum((Decimal(source.payload["values"].get(key, "0")) for key in ("principal", "interest", "fees")), Decimal("0"))
        old_out, old_offset = "0", "0"
        paper_settlement = source.payload.get("release", {}).get("paper_closure", {}).get("closure_basis") == "PAPER_SETTLEMENT"
        if facts.get("date"):
            terms = ("Full closure; corrected closing facts; cash method and customer handover unconfirmed"
                if paper_settlement else "Full closure; corrected date and confirmed return recipient")
        else:
            terms = ("Full closure; original closing date retained; cash method and customer handover unconfirmed"
                if paper_settlement else "Full closure; original return date and recipient retained")
        termination = "FULL_RELEASE"
    else:
        renewal = deepcopy(source.payload["renewal"])
        cash = renewal_cash(source)
        if successor_terms is not None:
            cash.update(successor_principal=str(successor_terms["principal"]),
                new_advance_interest=str(successor_terms["advance"]), new_document_charge=str(successor_terms["fees"]))
            renewal.update(successor_principal=str(successor_terms["principal"]), successor_control_principal=str(successor_terms["principal"]),
                successor_advance_interest=str(successor_terms["advance"]), successor_deducted_fees=str(successor_terms["fees"]))
        new_principal = Decimal(cash["successor_principal"])
        paid, advance = reconcile_renewal_cash(principal=principal, interest=interest, new_principal=new_principal,
            method=cash["method"], received=received, paid_out=paid_out, offset=offset,
            new_advance_interest=Decimal(cash.get("new_advance_interest", "0")),
            new_document_charge=Decimal(cash.get("new_document_charge", "0")))
        old_in, old_out, old_offset = cash["cash_received"], cash["cash_paid"], cash["interest_offset"]
        cash.update(source_principal=str(principal), principal_paid=str(paid), interest_settled=str(interest),
            principal_carried=str(principal-paid), gross_advance=str(advance), cash_received=str(received),
            cash_paid=str(paid_out), interest_offset=str(offset))
        renewal.update(principal_paid=str(paid), top_up_amount=str(advance), source_control_principal=str(principal), amount_received=str(received))
        renewal["cash_evidence"] = cash
        payload = renewal_settlement_payload(loan, effective_date=day, principal_amount=principal,
            capitalized_interest_principal_amount=0, interest_amount=interest, fee_amount=0).to_dict()
        payload.update(renewal=renewal)
        if "recorded_admission" in source.payload:
            payload["recorded_admission"] = source.payload["recorded_admission"]
        method = "full principal repayment and fresh advance" if cash['method'] == 'REPAY_REDRAW' else "principal carry with reduction or top-up"
        custody = "stayed held" if cash['custody'] == 'HELD' else "returned and repledged"
        terms = f"Successor {renewal['successor_loan_number']}: {method}; collateral {custody}"
        termination = "RENEWAL_SETTLEMENT"
    payload["history_correction"] = meta
    event, _ = record_loan_event(loan.pk, event_kind=source.event_kind, effective_date=day, payload=payload, actor=actor)
    allocate_event_to_obligations(source_event=event, principal_amount=principal,
        interest_amount=scheduled_interest(loan, day, interest), actor=actor)
    terminate_active_repayment_schedule(loan=loan, source_event=event, reason=termination, actor=actor)
    item = loan.collateral_items.get()
    m.PawnLoanPrincipalClosingLine.objects.create(loan_event=event, collateral_item=item, allocation_order=1,
        monthly_interest_rate=item.monthly_interest_rate, balance_before=principal, principal_settled=principal, balance_after=0)
    if collection_balance(loan, day).total_due:
        raise ValueError("The corrected settlement did not reconcile to zero.")
    return dict(source=source.pk, action="Restate settlement; no physical movement", date=day.isoformat(),
        reference=facts["reference"], amount=str(old_in), new_amount=str(received),
        old_cash_paid=str(old_out), cash_paid=str(paid_out), old_offset=str(old_offset), offset=str(offset), terms=terms,
        old_principal=source.payload["values"]["principal"], old_interest=source.payload["values"]["interest"],
        principal=str(principal), interest=str(interest))
