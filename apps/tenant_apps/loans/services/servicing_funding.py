"""Version-four funding evidence, replayed through ordinary custody guards."""
from datetime import date
from decimal import Decimal

from apps.tenant_apps.loans import models as m
from .servicing_bundle_contract import ROWS, decode, require

KINDS = tuple(name for name in ROWS if name.startswith('Funding'))


def source_setup(workspace_id, namespace, loans):
    from apps.tenant_apps.data_portability.models import PartyIdentity
    result = {}
    for pk, loan in loans.items():
        identity, _ = PartyIdentity.objects.get_or_create(workspace_id=workspace_id, party_id=loan.lender_id)
        result[str(pk)] = dict(source_party_id=loan.lender_id,
            lender=dict(source_system='rokkad:'+str(namespace.public_id), id=str(identity.public_id)))
    return result


def funding_position(loan):
    from apps.tenant_apps.loans.selectors.funding_loans import get_funding_loan_detail
    summary = get_funding_loan_detail(loan.pk).summary
    return dict(state=summary.state, number=summary.funding_number,
        recorded={key:str(getattr(summary, key+'_outstanding')) for key in ('principal','interest','fees')},
        active_collateral_count=summary.active_collateral_count)


def validate_source_funding(document):
    from apps.tenant_apps.loans.domain.future_funding import (
        FundingLoanEvent, FundingLoanEventKind, calculate_funding_loan_balance)
    from .funding_loans import _fingerprint
    tables = document['tables']
    loans = {r['id']:r for r in tables['FundingLoan']}
    require(1 <= len(loans) <= 100 and set(document['funding_setup']) == set(document['funding_positions']) == {str(pk) for pk in loans},
        'Funding setup/position coverage differs.')
    require(len(tables['FundingLoanSequence']) == 1, 'Funding numbering needs its exact source counter.')
    items = {r['id']:r for r in tables['PawnCollateralItem']}
    pledge_items = {r['id']:r for r in tables['FundingPledgeItem']}
    funded_items = {r['collateral_item_id'] for r in pledge_items.values()}
    custody = {pk:'IN_VAULT' for pk in funded_items}
    for movement in tables['PawnCollateralCustodyEvent']:
        if movement['collateral_item_id'] in custody:
            require(movement['from_state']==custody[movement['collateral_item_id']], 'Funding custody does not continue its original chain.')
            custody[movement['collateral_item_id']]=movement['to_state']
    require(all(custody[pk]==items[pk]['custody_state'] for pk in custody), 'Funding custody projection differs.')
    for kind in ('FundingPledge','FundingReturn','FundingPledgeReversal','FundingReturnReversal'):
        for row in tables[kind]:
            require(date.fromisoformat(row['effective_date'])<=date.fromisoformat(document['as_of']), 'Future funding custody is unsupported.')
    for pk, loan in loans.items():
        setup = document['funding_setup'][str(pk)]
        require(type(setup) is dict and set(setup) == {'source_party_id','lender'} and setup['source_party_id'] == loan['lender_id'], 'Funding lender claim differs.')
        lender = setup['lender']
        require(type(lender) is dict and set(lender) == {'source_system','id'} and lender['source_system'] == 'rokkad:'+document['namespace'], 'Funding lender namespace differs.')
        from uuid import UUID
        UUID(lender['id'])
        terms = [r for r in tables['FundingLoanTermsSnapshot'] if r['funding_loan_id'] == pk]
        events = sorted((r for r in tables['FundingLoanEvent'] if r['funding_loan_id'] == pk),key=lambda r:r['sequence'])
        require([r['sequence'] for r in events] == list(range(1,len(events)+1)), 'Funding event sequence has a gap.')
        by_id = {r['id']:r for r in events}
        for event in events:
            require(date.fromisoformat(event['effective_date']) <= date.fromisoformat(document['as_of']), 'Future funding event is unsupported.')
            if event['reversal_of_id'] is not None:
                require(event['reversal_of_id'] in by_id and by_id[event['reversal_of_id']]['sequence'] < event['sequence'], 'Funding reversal lineage differs.')
        require(len(terms) <= 1 and (not events or len(terms) == 1), 'Funding terms are missing or duplicated.')
        domain = tuple(FundingLoanEvent(sequence=r['sequence'],kind=FundingLoanEventKind(r['event_kind']),
            principal_amount=Decimal(r['principal_amount']),interest_amount=Decimal(r['interest_amount']),fee_amount=Decimal(r['fee_amount']),
            reversal_of_sequence=by_id[r['reversal_of_id']]['sequence'] if r['reversal_of_id'] is not None else None) for r in events)
        balance = calculate_funding_loan_balance(domain,currency_quantum=Decimal(terms[0]['currency_quantum']) if terms else Decimal('.01'))
        pledges = [r for r in tables['FundingPledge'] if r['funding_loan_id'] == pk]
        active = sum(r['released_at'] is None for r in pledge_items.values() if r['funding_pledge_id'] in {p['id'] for p in pledges})
        require(document['funding_positions'][str(pk)] == dict(state=loan['state'],number=loan['funding_number'],
            recorded={key:str(getattr(balance,key+'_outstanding')) for key in ('principal','interest','fees')}, active_collateral_count=active), 'Funding financial position differs.')
        if loan['state'] in {'ACTIVE','SETTLEMENT_PENDING','CLOSED'}:
            require(len(terms) == len(pledges) == 1 and events and events[0]['event_kind'] == 'ACTIVATION'
                and Decimal(events[0]['principal_amount']) == Decimal(terms[0]['principal_amount']), 'Funding activation evidence differs.')
            require(terms[0]['schema_version']==1 and terms[0]['activated_on']==events[0]['effective_date']==pledges[0]['effective_date'],
                'Funding activation dates or calculation version differ.')
            maximum=(Decimal(pledges[0]['total_collateral_value'])*Decimal(terms[0]['maximum_funding_ltv_ratio'])).quantize(Decimal(terms[0]['currency_quantum']))
            require(Decimal(pledges[0]['maximum_funded_amount'])==maximum and Decimal(terms[0]['principal_amount'])<=maximum,
                'Funding activation exceeds its original evidenced LTV limit.')
        else:
            require(not events and not pledges and not terms, 'Unactivated funding contains posted evidence.')
        if loan['state'] == 'CLOSED':
            require(balance.total_due == 0 and active == 0, 'Closed funding has remaining debt or collateral.')
        for pledge in pledges:
            rows = [r for r in pledge_items.values() if r['funding_pledge_id'] == pledge['id']]
            require(rows and sum((Decimal(r['selected_collateral_value']) for r in rows),Decimal(0)) == Decimal(pledge['total_collateral_value']), 'Funding valuation total differs.')
            require(pledge['valuation_method'] == 'COMMAND_SELECTED_VALUE' and pledge['valuation_version'] == 1
                and pledge['valuation_snapshot'].get('items') == [dict(collateral_item_id=r['collateral_item_id'],selected_value=r['valuation_snapshot']['selected_value']) for r in sorted(rows,key=lambda r:r['collateral_item_id'])], 'Unsupported funding valuation evidence.')
            for r in rows:
                require(r['source_pawn_loan_id'] == items[r['collateral_item_id']]['loan_id']
                    and Decimal(r['valuation_snapshot']['selected_value']) == Decimal(r['selected_collateral_value'])
                    and r['valuation_fingerprint'] == _fingerprint(dict(collateral_item_id=r['collateral_item_id'],selected_value=r['valuation_snapshot']['selected_value'])), 'Funding item valuation or owner differs.')
            original = [r for r in tables['PawnCollateralCustodyEvent'] if r['funding_pledge_id']==pledge['id'] and r['funding_pledge_reversal_id'] is None]
            require(sorted(r['collateral_item_id'] for r in original)==sorted(r['collateral_item_id'] for r in rows)
                and all(r['from_state']=='IN_VAULT' and r['to_state']=='WITH_FUNDING_LENDER' and r['effective_date']==pledge['effective_date'] for r in original),
                'Funding original pledge custody differs.')
    for returned in tables['FundingReturn']:
        rows = [r for r in tables['FundingReturnItem'] if r['funding_return_id'] == returned['id']]
        require(rows and sorted(returned['evidence_snapshot'].get('returned_collateral_item_ids',[])) == sorted(pledge_items[r['pledge_item_id']]['collateral_item_id'] for r in rows), 'Funding return item evidence differs.')
        original = [r for r in tables['PawnCollateralCustodyEvent'] if r['funding_return_id']==returned['id'] and r['funding_return_reversal_id'] is None]
        require(sorted(r['collateral_item_id'] for r in original)==sorted(pledge_items[r['pledge_item_id']]['collateral_item_id'] for r in rows)
            and all(r['from_state']=='WITH_FUNDING_LENDER' and r['to_state']=='IN_VAULT' and r['effective_date']==returned['effective_date'] for r in original),
            'Funding original return custody differs.')
        from django.utils.dateparse import parse_datetime
        terms = next(r for r in tables['FundingLoanTermsSnapshot'] if r['funding_loan_id']==returned['funding_loan_id'])
        events = sorted((r for r in tables['FundingLoanEvent'] if r['funding_loan_id']==returned['funding_loan_id']),key=lambda r:r['sequence'])
        by_id = {r['id']:r for r in events}
        prefix = tuple(FundingLoanEvent(sequence=r['sequence'],kind=FundingLoanEventKind(r['event_kind']),
            principal_amount=Decimal(r['principal_amount']),interest_amount=Decimal(r['interest_amount']),fee_amount=Decimal(r['fee_amount']),
            reversal_of_sequence=by_id[r['reversal_of_id']]['sequence'] if r['reversal_of_id'] is not None else None)
            for r in events if parse_datetime(r['created_at'])<=parse_datetime(returned['created_at']))
        original_balance = calculate_funding_loan_balance(prefix,currency_quantum=Decimal(terms['currency_quantum']))
        require(original_balance.principal_outstanding==Decimal(returned['principal_outstanding']),
            'Funding return balance differs from its original recording-time evidence.')


class FundingRestore:
    """Replay headers at their first custody event, keeping SQL guards enabled.

    Pledges cannot all be inserted first: a later pledge may reuse an item after
    a prior return. The original custody-event order supplies that dependency.
    """
    def __init__(self, workspace, actor, document, refs, objects):
        from apps.tenant_apps.data_portability.children import parent_for
        self.workspace, self.actor, self.document = workspace, actor, document
        self.refs, self.objects = refs, objects
        self.rows = {kind:{r['id']:r for r in document['tables'][kind]} for kind in KINDS}
        self.lenders = {}
        for pk, setup in document['funding_setup'].items():
            parent = parent_for(dict(party_source_system=setup['lender']['source_system'],party_external_id=setup['lender']['id']),workspace.pk)
            require(parent is not None,'Import the exact source lender Party identity before funding restoration.')
            self.lenders[int(pk)] = parent.party_id
        sequence = next(iter(self.rows['FundingLoanSequence'].values()))
        existing = m.FundingLoanSequence.objects.filter(workspace=workspace).first()
        if existing:
            require(all(getattr(existing,k) == sequence[k] for k in ('prefix','width','maximum_value')), 'Funding counter configuration differs.')
            if existing.next_value < sequence['next_value']:
                existing.next_value = sequence['next_value']
                existing.save(update_fields=['next_value','updated_at'])
            refs['FundingLoanSequence'][sequence['id']] = existing.pk
            objects['FundingLoanSequence'][sequence['id']] = existing
        else:
            self.insert('FundingLoanSequence',sequence['id'])

    def insert(self, kind, pk):
        from .servicing_bundle import _new_row, _adapt, ACTORS
        from .funding_loans import _fingerprint
        if pk in self.objects[kind]:
            return self.objects[kind][pk]
        source = self.rows[kind][pk]
        values = decode(kind,source)
        values.update(id=self.refs[kind][pk],workspace_id=self.workspace.pk)
        for key, spec in ROWS[kind].items():
            parent = spec.get('reference','').removeprefix('loans.')
            if spec.get('reference') == ACTORS:
                values[key] = self.actor.pk
            elif parent in self.refs and source[key] is not None:
                values[key] = self.refs[parent][source[key]]
            elif spec['type'] == 'JSONField':
                values[key] = _adapt(source[key],refs=self.refs,external={'workspace_id':self.workspace.pk},numbers={},event_keys={})
        if kind == 'FundingLoan':
            values.update(state='DRAFT',lender_id=self.lenders[pk])
        if kind == 'FundingPledgeItem':
            values['released_at'] = None
            values['valuation_fingerprint'] = _fingerprint(dict(collateral_item_id=values['collateral_item_id'],selected_value=values['valuation_snapshot']['selected_value']))
        obj = _new_row(kind,values)
        self.objects[kind][pk] = obj
        return obj

    def ensure_loan(self, pk):
        if pk in self.objects['FundingLoan']:
            return
        self.insert('FundingLoan',pk)
        for kind in ('FundingLoanDraftTerms','FundingLoanDraftCollateral','FundingLoanTermsSnapshot','FundingLoanEvent','FundingLoanCancellation'):
            rows = [r for r in self.rows[kind].values() if r['funding_loan_id'] == pk]
            for r in sorted(rows,key=lambda r:r.get('sequence',r['id'])):
                self.insert(kind,r['id'])

    def ensure_pledge(self, pk):
        if pk in self.objects['FundingPledge']:
            return
        self.ensure_loan(self.rows['FundingPledge'][pk]['funding_loan_id'])
        self.insert('FundingPledge',pk)
        for r in self.rows['FundingPledgeItem'].values():
            if r['funding_pledge_id'] == pk:
                self.insert('FundingPledgeItem',r['id'])

    def ensure_return(self, pk):
        if pk in self.objects['FundingReturn']:
            return
        row = self.rows['FundingReturn'][pk]
        self.ensure_loan(row['funding_loan_id'])
        self.insert('FundingReturn',pk)
        for r in self.rows['FundingReturnItem'].values():
            if r['funding_return_id'] == pk:
                pledge_pk = self.rows['FundingPledgeItem'][r['pledge_item_id']]['funding_pledge_id']
                self.ensure_pledge(pledge_pk)
                returned = self.insert('FundingReturnItem',r['id'])
                item = self.objects['FundingPledgeItem'][r['pledge_item_id']]
                item.released_at = returned.returned_at
                item.save(update_fields=['released_at'])

    def before_custody(self, source):
        if source['funding_pledge_id']:
            self.ensure_pledge(source['funding_pledge_id'])
        if source['funding_return_id']:
            self.ensure_return(source['funding_return_id'])
        for kind, field, parent, parent_field in (
                ('FundingPledgeReversal','funding_pledge_reversal_id','FundingPledge','funding_pledge_id'),
                ('FundingReturnReversal','funding_return_reversal_id','FundingReturn','funding_return_id')):
            pk = source[field]
            if not pk or pk in self.objects[kind]:
                continue
            row = self.rows[kind][pk]
            if parent == 'FundingPledge':
                self.ensure_pledge(row[parent_field])
                affected = [r for r in self.rows['FundingPledgeItem'].values() if r['funding_pledge_id'] == row[parent_field]]
            else:
                self.ensure_return(row[parent_field])
                affected = [self.rows['FundingPledgeItem'][r['pledge_item_id']] for r in self.rows['FundingReturnItem'].values() if r['funding_return_id'] == row[parent_field]]
            reversal = self.insert(kind,pk)
            for r in affected:
                item = self.objects['FundingPledgeItem'][r['id']]
                item.released_at = decode('FundingPledgeItem',r)['released_at'] if parent == 'FundingPledge' else None
                item.save(update_fields=['released_at'])

    def finish(self):
        for pk, source in self.rows['FundingLoan'].items():
            self.ensure_loan(pk)
            obj = self.objects['FundingLoan'][pk]
            states = ('CANCELLED',) if source['state'] == 'CANCELLED' else ('ACTIVE','SETTLEMENT_PENDING','CLOSED')[:{'DRAFT':0,'ACTIVE':1,'SETTLEMENT_PENDING':2,'CLOSED':3}[source['state']]]
            for state in states:
                obj.state = state
                obj.save(update_fields=['state'])
            require(funding_position(obj) == self.document['funding_positions'][str(pk)], 'Restored funding position differs.')
        for kind in KINDS:
            require(set(self.objects[kind]) == set(self.rows[kind]), 'Funding custody graph did not cover '+kind+'.')
        for pk, source in self.rows['FundingPledgeItem'].items():
            actual = self.objects['FundingPledgeItem'][pk].released_at
            expected = decode('FundingPledgeItem',source)['released_at']
            require(actual == expected,'Restored funding return position differs.')
