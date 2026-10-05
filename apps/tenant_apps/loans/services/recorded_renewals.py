"""Renewal settlement with explicit paper cash and independent custody evidence."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.integrations import renewal_settlement_payload, renewal_opening_payload
from apps.tenant_apps.loans.selectors.balances import get_pawn_loan_balance
from .event_recording import record_loan_event
from .obligations import allocate_event_to_obligations, terminate_active_repayment_schedule
from .recorded_collections import recognize_collection_interest, scheduled_interest


def reconcile_renewal_cash(*, principal, interest, new_principal, method, received, paid_out, offset,
                          new_advance_interest=Decimal("0"), new_document_charge=Decimal("0")):
    """Reconcile actual cash against the unchanged agreed successor principal."""
    if method not in ("CARRY", "REPAY_REDRAW", "NET_SETTLEMENT"):
        raise ValueError("Unsupported recorded renewal funding method.")
    paid = principal if method == "REPAY_REDRAW" else max(principal - new_principal, Decimal("0"))
    advance = new_principal if method == "REPAY_REDRAW" else max(new_principal - principal, Decimal("0"))
    if method == "NET_SETTLEMENT":
        net = advance - paid - interest - new_advance_interest - new_document_charge
        if offset != min(interest, advance) or received != max(-net, Decimal("0")) or paid_out != max(net, Decimal("0")):
            raise ValueError("Net renewal cash does not reconcile to the retained new terms and deductions.")
        return paid, advance
    if offset < 0 or offset > min(interest, advance):
        raise ValueError("Interest offset cannot exceed the old interest due or the new advance.")
    required_in, required_out = paid + interest - offset, advance - offset
    if received != required_in or paid_out != required_out:
        raise ValueError(f"Renewal cash does not reconcile: actual received {received}, required {required_in}; "
                         f"actual paid out {paid_out}, required {required_out}. "
                         "Verify the paper cash facts; the agreed new principal remains unchanged.")
    return paid, advance


def record_admission_renewal(workspace, actor, data, key, source, row, request_key):
    from .recorded_history import _make_contract, _activate
    day, cash = date.fromisoformat(row["date"]), Decimal(row["amount"])
    opening_origin = source.loan_events.filter(event_kind="MIGRATION_OPENING").exists()
    catch_up, collection_detail, opening_state = None, None, None
    if opening_origin:
        from .opening_servicing import opening_release_context, opening_release_accrual_preview, payment_collection_detail
        from .pawn_release import _record_release_accrual
        _, opening_state = opening_release_context(source, as_of_date=day)
        collection_detail = payment_collection_detail(source, as_of_date=day, request_key=request_key, operation="RENEWAL_SETTLEMENT")
        preview = opening_release_accrual_preview(source, as_of_date=day)
        if preview:
            catch_up = _record_release_accrual(source, preview=preview, actor=actor,
                request_key=request_key, collection_detail=collection_detail)
    else:
        recognize_collection_interest(source, day, actor=actor, request_key=request_key)
    balance = get_pawn_loan_balance(source, as_of_date=day)
    if balance.fees_outstanding:
        raise ValueError("Paper renewal with fees needs a wider contract profile.")
    principal, interest = balance.principal_outstanding, balance.interest_outstanding
    method, custody = row.get("renewal_method", "CARRY"), row.get("custody", "HELD")
    advance_months = row.get("advance_months", 0)
    document_charge = Decimal(row.get("document_charge", "0"))
    if method == "NET_SETTLEMENT":
        new_principal = Decimal(row["new_principal"])
        paid, advance = max(principal-new_principal, Decimal("0")), max(new_principal-principal, Decimal("0"))
        new_interest = (new_principal * Decimal(row["rate"]) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * advance_months
        required_net = advance - paid - interest - new_interest - document_charge
        cash_out, offset = Decimal(row["cash_paid"]), min(interest, advance)
        if cash != max(-required_net, Decimal("0")) or cash_out != max(required_net, Decimal("0")):
            raise ValueError("Actual net collection/payout does not match old settlement and new deductions.")
    elif "renewal_method" in row:
        new_principal = Decimal(row["new_principal"])
        offset, cash_out = Decimal(row["interest_offset"]), Decimal(row["cash_paid"])
        paid, advance = reconcile_renewal_cash(principal=principal, interest=interest, new_principal=new_principal,
            method=method, received=cash, paid_out=cash_out, offset=offset)
    else:
        # Keep existing signed UR-03 requests and exact retries compatible.
        if not interest <= cash < balance.total_due:
            raise ValueError("A carry-forward renewal must settle all interest and leave positive principal.")
        paid, advance, offset, cash_out = cash - interest, Decimal("0"), Decimal("0"), Decimal("0")
        new_principal = principal - paid
    new_principal = new_principal.quantize(Decimal("0.01"))
    carried = principal - paid
    evidence = dict(schema="recorded-renewal-cash/1", method=method, custody=custody,
        source_principal=str(principal),
        cash_received=str(cash), cash_paid=str(cash_out), interest_offset=str(offset),
        interest_settled=str(interest), principal_paid=str(paid), principal_carried=str(carried),
        gross_advance=str(advance), successor_principal=str(new_principal),
        new_advance_interest=str((new_principal * Decimal(row["rate"]) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) * advance_months),
        new_document_charge=str(document_charge),
        recipient=row["recipient"] if custody == "RETURNED_REPLEDGED" else "")
    old_item = source.collateral_items.get()
    successor_data = dict(data)
    successor_data.pop("collateral", None)
    successor, item, policy, recording, tranches, monthly = _make_contract(workspace, actor, successor_data, key,
        number=row["number"], day=day, principal=new_principal, rate=Decimal(row["rate"]), tenure=row["tenure"],
        advance=Decimal(evidence["new_advance_interest"]), predecessor=old_item,
        custody_state="WITH_CUSTOMER" if custody == "RETURNED_REPLEDGED" else "IN_VAULT")
    recording.update(source_reference=row["reference"], funding_basis=method, cash_evidence=evidence,
                     payout_already_occurred=cash_out > 0)
    if row.get("request_sha256"):
        recording["renewal_request_sha256"] = row["request_sha256"]
    retained = [old_item.pk] if custody == "HELD" else []
    returned = [old_item.pk] if custody == "RETURNED_REPLEDGED" else []
    number = f"REN-{source.loan_number}"
    detail = dict(renewal_number=number, mode="PAY_AND_RENEW", source_loan_id=source.pk,
        source_loan_number=source.loan_number, successor_loan_id=successor.pk, successor_loan_number=successor.loan_number,
        principal_paid=str(paid), top_up_amount=str(advance), successor_principal=str(new_principal),
        source_control_principal=str(balance.principal_outstanding), successor_control_principal=str(new_principal),
        successor_advance_interest=evidence["new_advance_interest"], successor_deducted_fees=str(document_charge),
        catch_up_event_id=catch_up.loan_event_id if catch_up else None, request_key=request_key,
        retained_source_item_ids=retained, returned_source_item_ids=returned, paper_reference=row["reference"], cash_evidence=evidence,
        amount_received=str(cash), allocation_basis="DERIVED_FROM_AGREED_TERMS", date_precision="DAY", original_actor=None)
    payload = renewal_settlement_payload(source, effective_date=day, principal_amount=balance.principal_outstanding,
        capitalized_interest_principal_amount=0, interest_amount=balance.interest_outstanding, fee_amount=0).to_dict()
    payload.update(renewal=detail, recorded_admission=str(key))
    if opening_origin:
        from .opening_servicing import _record_opening_servicing_event
        payload["opening_collection"] = collection_detail
        settlement, _ = _record_opening_servicing_event(source.pk, event_kind="RENEWAL_SETTLEMENT", effective_date=day, payload=payload, actor=actor)
    else:
        settlement, _ = record_loan_event(source.pk, event_kind="RENEWAL_SETTLEMENT", effective_date=day, payload=payload, actor=actor)
    allocate_event_to_obligations(source_event=settlement, principal_amount=balance.principal_outstanding,
        interest_amount=min(opening_state.remaining.interest, balance.interest_outstanding) if opening_origin else
            scheduled_interest(source, day, balance.interest_outstanding), actor=actor)
    terminate_active_repayment_schedule(loan=source, source_event=settlement, reason="RENEWAL_SETTLEMENT", actor=actor)
    m.PawnLoanPrincipalClosingLine.objects.create(loan_event=settlement, collateral_item=old_item, allocation_order=1,
        monthly_interest_rate=old_item.monthly_interest_rate, balance_before=balance.principal_outstanding,
        principal_settled=balance.principal_outstanding, balance_after=0)
    payload = renewal_opening_payload(successor, effective_date=day, principal_amount=new_principal,
                                     capitalized_interest_principal_amount=0).to_dict()
    payload.update(recording=recording, recorded_admission=str(key), renewal=dict(
        renewal_number=number, source_loan_id=source.pk, settlement_event_id=settlement.pk, operational_opening=True,
        retained_source_item_ids=retained, repledged_source_item_ids=returned,
        additional_successor_item_ids=[], successor_economics=dict(
            policy_snapshot_id=policy.pk, approval_snapshot_id=None, advance_interest_periods=advance_months,
            monthly_interest=str(monthly), advance_interest=evidence["new_advance_interest"],
            deducted_fees=str(document_charge), tranches=tranches,
            fees=[dict(kind="DOCUMENT_CHARGE", amount=str(document_charge), deducted=True)] if document_charge else [])))
    opening, _ = record_loan_event(successor.pk, event_kind="RENEWAL_OPENING", effective_date=day, payload=payload, actor=actor)
    m.PawnLoanPrincipalOpeningLine.objects.create(loan_event=opening, collateral_item=item, predecessor_collateral_item=old_item,
        allocation_order=1, monthly_interest_rate=item.monthly_interest_rate, principal_opened=new_principal)
    _activate(successor, opening, actor)
    renewal = m.PawnLoanRenewal.objects.create(workspace=workspace, source_loan=source, successor_loan=successor,
        renewal_number=number, request_key=request_key, mode="PAY_AND_RENEW", renewal_date=day,
        source_principal_amount=balance.principal_outstanding, source_capitalized_principal_amount=0,
        interest_settled=balance.interest_outstanding, fees_settled=0, principal_paid=paid, top_up_amount=advance,
        successor_principal_amount=new_principal, successor_capitalized_principal_amount=0,
        successor_advance_interest=Decimal(evidence["new_advance_interest"]), successor_deducted_fees=document_charge,
        valuation_snapshot=dict(recorded_admission=str(key), paper_reference=row["reference"], original_valuation=None,
                                principal_carried=str(carried), net_cash_received=str(cash-cash_out), cash_evidence=evidence),
        settlement_event=settlement, opening_event=opening, catch_up_accrual=catch_up, created_by=actor)
    from .storage_operations import carry_storage_to_renewal_successor, remove_collateral_from_storage
    from .collateral_media import _inherit_collateral_photos
    _inherit_collateral_photos(old_item, item, actor=actor)
    if custody == "HELD":
        carry_storage_to_renewal_successor(old_item, item, renewal=renewal, actor=actor)
    else:
        remove_collateral_from_storage(old_item, workflow_source="RENEWAL_RETURN", source_reference=str(renewal.pk), actor=actor)
    target = "RENEWAL_TRANSFERRED" if custody == "HELD" else "WITH_CUSTOMER"
    m.PawnCollateralCustodyEvent.objects.create(collateral_item=old_item, renewal=renewal,
        from_state="IN_VAULT", to_state=target, effective_date=day, actor=actor)
    if custody == "RETURNED_REPLEDGED":
        m.PawnCollateralCustodyEvent.objects.create(collateral_item=item, renewal=renewal,
            from_state="WITH_CUSTOMER", to_state="IN_VAULT", effective_date=day, actor=actor)
        item.custody_state = "IN_VAULT"
        item.save(update_fields=["custody_state", "updated_at"])
    old_item.custody_state = target
    old_item.save(update_fields=["custody_state", "updated_at"])
    source.state = "CLOSED"
    source.updated_by = actor
    source.save(update_fields=["state", "updated_by", "updated_at"])
    m.LoanChangeLog.objects.create(loan=source, event_kind="RENEWAL_COMPLETED", from_state="ACTIVE", to_state="CLOSED",
        actor=actor, metadata=dict(renewal_id=renewal.pk, successor_loan_id=successor.pk, recorded_history=True))
    return successor, dict(kind="Net renewal settlement" if method == "NET_SETTLEMENT" else "Carry-forward renewal" if method == "CARRY" else "Full repayment and fresh advance",
        date=row["date"], number=source.loan_number, successor=successor.loan_number,
        reference=row["reference"], new_advance_interest=evidence["new_advance_interest"], new_document_charge=str(document_charge),
        cash=str(cash), cash_received=str(cash), cash_paid=str(cash_out), principal=str(paid),
        interest=str(interest), carried=str(carried), advance=str(advance), new_principal=str(new_principal),
        old_principal=str(principal),
        interest_offset=str(offset), custody="Stayed held" if custody == "HELD" else "Returned and repledged", recipient=evidence["recipient"])
