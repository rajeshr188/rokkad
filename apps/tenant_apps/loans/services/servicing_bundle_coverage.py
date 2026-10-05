"""Validate source completeness claims using frozen source-local identities."""
from datetime import date
from types import SimpleNamespace

from .servicing_bundle_contract import decode, require
from apps.tenant_apps.loans.selectors.transaction_completeness import transaction_fingerprint, capture_contract_fingerprint


def validate_source_coverage(document):
    tables = document['tables']
    as_of = date.fromisoformat(document['as_of'])
    for source in tables['PawnLoan']:
        loan = SimpleNamespace(**decode('PawnLoan', source), pk=source['id'])
        events = [SimpleNamespace(**decode('PawnLoanEvent', row), pk=row['id']) for row in tables['PawnLoanEvent'] if row['loan_id']==loan.pk]
        reviews = [SimpleNamespace(**decode('LoanTransactionReview', row), pk=row['id']) for row in tables['LoanTransactionReview'] if row['loan_id']==loan.pk]
        coverage = document['positions'][str(loan.pk)]['coverage']
        require(type(coverage['complete']) is bool, 'Invalid source coverage claim.')
        if not coverage['complete']:
            continue
        if not reviews:
            policy = next((r for r in tables['LoanPolicySnapshot'] if r['id']==loan.policy_snapshot_id), None)
            required = (policy and policy['basis']=='RECORDED_CONTRACT') or any(e.event_kind=='MIGRATION_OPENING' or e.payload.get('repayment',{}).get('recording') or e.payload.get('release',{}).get('paper_closure') for e in events)
            require(not required and coverage['status']=='SYSTEM_RECORDED', 'Source completeness is missing its required book review.')
            continue
        review = max(reviews,key=lambda r:r.pk)
        require(review.confirmed_complete and review.pk==coverage['review_id'] and review.through_date.isoformat()==coverage['through_date'], 'Source completeness differs from its latest retained review.')
        if review.future_capture=='PAPER_MIXED':
            required_through = min(as_of,max(e.effective_date for e in events)) if loan.state=='CLOSED' else as_of
            require(review.source_fingerprint==transaction_fingerprint(loan,events=events) and review.through_date>=required_through and coverage['status']=='CONFIRMED', 'Source complete book review is stale or changed.')
            continue
        baseline = [e for e in events if review.capture_event_id and e.pk<=review.capture_event_id]
        following = [e for e in events if e not in baseline]
        items = [SimpleNamespace(**decode('PawnCollateralItem',r),pk=r['id']) for r in tables['PawnCollateralItem'] if r['loan_id']==loan.pk]
        require(coverage['status']=='ROKKAD_ONLY' and as_of>=review.through_date and baseline and review.capture_state=='ACTIVE'
            and transaction_fingerprint(loan,events=baseline,state='ACTIVE')==review.source_fingerprint
            and capture_contract_fingerprint(loan,items=items)==review.capture_contract_fingerprint, 'Source future-capture checkpoint changed.')
        ids = {e.pk for e in following}
        allowed = {'INTEREST_ACCRUAL','REPAYMENT','RELEASE_RECEIPT','RENEWAL_SETTLEMENT','AUCTION_RECOVERY','REVERSAL'}
        for e in following:
            p = e.payload
            paper = p.get('history_correction') or p.get('recorded_admission') or p.get('repayment',{}).get('recording') or p.get('release',{}).get('paper_closure') or p.get('recording')
            policy = next((r for r in tables['LoanPolicySnapshot'] if r['id']==loan.policy_snapshot_id), None)
            derived = e.event_kind=='INTEREST_ACCRUAL' and p.get('accrual') and not paper and policy and policy['policy_version']==2 and policy['basis']!='RECORDED_CONTRACT' and any(r['loan_event_id']==e.pk for r in tables['PawnLoanInterestAccrual'])
            require(e.event_kind in allowed and not paper and (e.effective_date>=review.through_date or derived) and e.created_at>=review.reviewed_at
                and (not e.reversal_of_id or e.reversal_of_id in ids)
                and not p.get('recorded_collection',{}).get('request_key','').startswith(('admission:','correction:')), 'Source future-capture suffix contains a historical or unreviewed action.')
        reversed_ids = {e.reversal_of_id for e in events if e.reversal_of_id}
        terminal = any(e.event_kind in {'RELEASE_RECEIPT','RENEWAL_SETTLEMENT','AUCTION_RECOVERY'} and e.pk not in reversed_ids for e in following)
        require(loan.state==('CLOSED' if terminal else 'ACTIVE'), 'Source capture lifecycle differs from its operation suffix.')
