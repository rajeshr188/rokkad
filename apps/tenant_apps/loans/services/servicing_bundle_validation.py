"""Financial reconciliation for the bounded portable admission command."""
from decimal import Decimal, ROUND_HALF_UP

from .servicing_bundle_contract import require


def reconcile(loan, events):
    from .pawn_tranches import get_pawn_principal_tranche_balances
    from apps.tenant_apps.loans.selectors.reports import _principal_evidence_issues
    from apps.tenant_apps.loans.selectors.balances import calculate_pawn_loan_balance
    from apps.tenant_apps.loans.domain.interest import calculate_period_interest
    from .pawn_interest import _partial_fraction

    items = tuple(loan.collateral_items.order_by('pk'))
    require(items, 'A portable agreement requires collateral evidence.')
    require(not _principal_evidence_issues(loan, events, items), 'Portable item settlement/opening evidence is incomplete.')
    get_pawn_principal_tranche_balances(loan)
    by_kind = {}
    for event in events:
        by_kind.setdefault(event.event_kind, []).append(event)
        values = event.payload['values']
        amount = lambda key: Decimal(str(values.get(key, '0')))
        if event.event_kind == 'REPAYMENT':
            if 'repayment' in event.payload:
                require(Decimal(str(event.payload['repayment']['amount_received'])) == sum((amount(k) for k in ('principal', 'interest', 'fees')), Decimal(0)), 'Portable receipt amount differs from its allocation.')
                recording = event.payload['repayment'].get('recording')
                if recording:
                    from .paper_repayments import validate_paper_repayment_evidence
                    validate_paper_repayment_evidence(recording, effective_date=event.effective_date, amount=Decimal(event.payload['repayment']['amount_received']))
                    if 'fees_paid' in recording:
                        require(Decimal(recording['fees_paid']) == amount('fees'), 'Explicit paper fee evidence differs from its financial allocation.')
                    if 'item_principal_split' in recording:
                        applied = {str(row['collateral_item_id']): Decimal(row['principal_applied']) for row in event.payload['repayment']['item_principal_allocations']}
                        expected = {key: Decimal(value) for key, value in recording['item_principal_split'].items()}
                        require(all(applied.get(key, Decimal(0)) == value for key, value in expected.items()) and
                            sum(expected.values(), Decimal(0)) == amount('principal'), 'Explicit paper item split differs from its financial allocation.')
            else:
                require(hasattr(loan, 'historical_import') and loan.historical_import.document.get('loan', {}).get('events'), 'Portable receipt lacks its original accepted source amounts.')
            if amount('principal'):
                require(event.repayment_allocation_lines.exists(), 'Portable principal receipt lacks item allocations.')
        if event.event_kind == 'DISBURSAL':
            snapshot = event.disbursal_snapshot
            require(snapshot.gross_principal == amount('principal') and snapshot.advance_interest == amount('advance_interest') and snapshot.net_disbursed == amount('net_cash'), 'Portable payout differs from its frozen snapshot.')
            if snapshot.basis=='APPROVED':
                from .pawn_renewals import _successor_approval_economics
                economics = _successor_approval_economics(loan,snapshot.approval_snapshot)
                require(all(getattr(snapshot,key)==economics[key] for key in ('gross_principal','monthly_interest','advance_interest_periods','advance_interest','deducted_fees','net_disbursed'))
                    and snapshot.evidence==economics['evidence'], 'Portable native payout differs from its genuine frozen approval.')
        if event.event_kind in {'RELEASE_RECEIPT', 'AUCTION_RECOVERY'}:
            related = loan.releases.filter(loan_event=event).first() if event.event_kind == 'RELEASE_RECEIPT' else loan.auctions.filter(loan_event=event).first()
            if related is None and event.event_kind=='RELEASE_RECEIPT' and event.payload.get('history_correction',{}).get('role')=='SETTLEMENT':
                from apps.tenant_apps.loans.selectors.recorded_settlements import restated_release
                root = event.payload['history_correction']['root_event_id']
                original = loan.releases.filter(loan_event_id=root).first()
                related = restated_release(original) if original else None
                require(related is not None and related.loan_event.pk==event.pk, 'Portable corrected settlement is not the active revision of its retained release.')
            require(related is not None, 'Portable settlement lacks its operation record.')
            require(related.principal_amount == amount('principal') and related.interest_amount == amount('interest') and related.fee_amount == amount('fees'), 'Portable settlement operation differs from its event.')
        # Fold every recorded prefix: a final zero cannot conceal overpayment or
        # an invalid intermediate balance followed by compensating fabricated debt.
        prefix = [r for r in events if r.pk <= event.pk]
        balance = calculate_pawn_loan_balance(loan, events=prefix, collateral_items=items, policy_snapshot=loan.policy_snapshot, as_of_date=event.effective_date)
        require(min(balance.principal_outstanding, balance.interest_outstanding, balance.fees_outstanding) >= 0, 'Portable financial prefix is negative.')

    require({s.loan_event_id for s in loan.disbursal_snapshots.all()} == {e.pk for e in by_kind.get('DISBURSAL', [])}, 'Portable payout/snapshot coverage differs.')
    accrual_ids = {a.loan_event_id for a in loan.interest_accruals.filter(loan_event__isnull=False)}
    for event in by_kind.get('INTEREST_ACCRUAL', []):
        if event.pk in accrual_ids:
            continue
        frozen = event.payload.get('recorded_collection')
        require(frozen and frozen.get('profile') in {'recorded-anniversary/1', 'recorded-anniversary/2', 'recorded-anniversary/3'}, 'Portable recognition lacks its supported calculation evidence.')
        additional = max(Decimal(0), Decimal(frozen['calculated'])-Decimal(frozen['advance'])-Decimal(frozen['already_recognized']))
        require(Decimal(event.payload['values']['interest']) == additional == Decimal(frozen['additional']), 'Portable recorded recognition amount differs from its calculation.')
    require(accrual_ids <= {e.pk for e in by_kind.get('INTEREST_ACCRUAL', [])}, 'Portable recognition/accrual coverage differs.')
    opening = bool(by_kind.get('MIGRATION_OPENING'))
    for accrual in loan.interest_accruals.all():
        if opening:
            # The checkpoint reader validates its different catch-up profile;
            # never replay or infer pre-cutover item charges.
            continue
        policy = loan.policy_snapshot
        fraction = _partial_fraction(policy, accrual.period_start, accrual.period_end, period_number=accrual.period_number)
        lines = tuple(accrual.lines.all())
        require(lines, 'Portable item recognition lacks calculation lines.')
        for line in lines:
            unrounded, calculated = calculate_period_interest(calculation_base=line.principal_base, monthly_interest_rate=line.monthly_interest_rate, period_fraction=fraction, currency_quantum=policy.currency_quantum)
            require(line.calculated_interest == calculated and line.unrounded_interest == unrounded.quantize(Decimal('.000000000001'), rounding=ROUND_HALF_UP) and line.recognized_interest == calculated-line.advance_interest_applied, 'Portable item recognition does not reconcile.')
        require(accrual.recognized_interest == sum((r.recognized_interest for r in lines), Decimal(0)) and accrual.calculation_base == sum((r.principal_base for r in lines), Decimal(0)), 'Portable recognition totals differ from item evidence.')
        if accrual.loan_event_id:
            require(Decimal(accrual.loan_event.payload['values']['interest']) == accrual.recognized_interest, 'Portable recognition event differs from its saved charge.')
