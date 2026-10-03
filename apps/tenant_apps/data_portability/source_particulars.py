"""Read-only particulars from completed migration inputs, never current Party fields."""
from collections import defaultdict

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.services.history_contract import digest
from .models import ImportRow, LoanHistoryBatch


def imported_loan_particulars(loans):
    """Bounded internal reader for an already-authorized loan report.

    The calling report owns actor authorization. Enforce context here too. Returned
    identity is explicitly source-snapshot evidence, not a pawning-day attestation.
    """
    if not loans:
        return {}
    wid = current_workspace_id()
    if not wid or any(loan.workspace_id != wid for loan in loans):
        raise PermissionDenied('Source particulars require the matching Workspace context.')
    if len(loans) > 100:
        raise ValueError('Read source particulars for at most 100 loans at a time.')
    parties = {loan.borrower_id for loan in loans}
    masters, addresses = defaultdict(list), defaultdict(list)
    rows = ImportRow.objects.filter(workspace_id=wid, batch__state='COMPLETED', committed_at__isnull=False).filter(
        Q(batch__contract_version='party-master/1', identity__party_id__in=parties)
        | Q(batch__contract_version='party-address/1', child_identity__parent__party_id__in=parties)
    ).values('batch__source_system', 'batch__contract_version', 'canonical', 'external_id',
             'identity__party_id', 'child_identity__parent__party_id')
    for row in rows:
        profile = row['batch__contract_version']
        party_id = row['identity__party_id'] if profile == 'party-master/1' else row['child_identity__parent__party_id']
        target = masters if profile == 'party-master/1' else addresses
        target[party_id, row['batch__source_system']].append(dict(row['canonical'], _external_id=row['external_id']))
    by_id = {loan.pk: loan for loan in loans}
    result = {}
    batches = LoanHistoryBatch.objects.filter(workspace_id=wid, state='COMPLETED', profile='legacy-opening/1',
        result__loan_id__in=by_id).select_related('result').only(
            'id', 'document', 'source_sha256', 'result_id', 'result__id', 'result__loan_id',
            'result__document', 'result__source_sha256')
    for batch in batches:
        origin = batch.result
        if (batch.source_sha256 != origin.source_sha256 or digest(origin.document) != origin.source_sha256
                or batch.document.get('opening') != origin.document):
            continue  # Inconsistent evidence cannot become a printed fact.
        review = origin.document['review']
        loan = by_id[origin.loan_id]
        if review['mapping']['borrower_id'] != loan.borrower_id:
            continue
        key = loan.borrower_id, review['mapping']['borrower_source_system']
        # Ambiguous/reimported identities are not resolved by choosing a newest row.
        candidates = masters[key]
        value = {'snapshot_date': review['cutover']['date'], 'borrower': '', 'address': '',
                 'tenure_months': None, 'tenure_basis': ''}
        if len(candidates) == 1:
            master = candidates[0]
            value['borrower'] = master.get('name') or ''
            source_addresses = [a for a in addresses[key] if a.get('party_external_id') == master['_external_id']]
            preferred = [a for a in source_addresses if a.get('is_default') and a.get('address_type') == 'HOME']
            selected = preferred[0] if len(preferred) == 1 else source_addresses[0] if len(source_addresses) == 1 else None
            if selected:
                value['address'] = ', '.join(str(selected[k]) for k in ('line1','line2','area','city','state','postal_code') if selected.get(k))
        maturity = batch.document.get('source_evidence', {}).get('maturity_review', {})
        value['tenure_basis'] = maturity.get('basis', '')
        if (maturity.get('basis') == 'RECORDED_TENURE'
                and maturity.get('tenure_months') == origin.document['setup']['tenure_months']):
            value['tenure_months'] = maturity['tenure_months']
        result[loan.pk] = value
    return result
