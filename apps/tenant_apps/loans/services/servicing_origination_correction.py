"""Version-2 transfer of retained neutral payout attempts, with local hash binding."""
from .origination_corrections import PROFILE
from .servicing_bundle_contract import require


def validate_source_correction(snapshot, tables):
    evidence = snapshot['evidence']['recording']['origination_correction']
    require(type(evidence) is dict and set(evidence) == {'profile', 'reason', 'attempts'}
        and evidence['profile'] == PROFILE and snapshot['basis'] == 'RECORDED'
        and type(evidence['reason']) is str and 0 < len(evidence['reason'].strip()) <= 500,
        'Invalid portable actual-paper correction evidence.')
    attempts = evidence['attempts']
    fields = {'payout_id', 'reversal_id', 'date', 'payout_sha256', 'reversal_sha256'}
    require(type(attempts) is list and 1 <= len(attempts) <= 20
        and all(type(row) is dict and set(row) == fields for row in attempts),
        'Invalid portable retained attempt inventory.')
    ids = [row[key] for row in attempts for key in ('payout_id', 'reversal_id')]
    require(all(type(pk) is int and pk > 0 for pk in ids) and len(set(ids)) == len(ids),
        'Retained portable attempts must be distinct.')
    events = {row['id']: row for row in tables['PawnLoanEvent']}
    native = {row['loan_event_id'] for row in tables['PawnLoanDisbursalSnapshot']
        if row['loan_id'] == snapshot['loan_id'] and row['basis'] == 'APPROVED'
        and row['loan_event_id'] < snapshot['loan_event_id']}
    require(native == {row['payout_id'] for row in attempts},
        'Portable correction must retain every earlier native payout attempt.')
    actual = events[snapshot['loan_event_id']]
    for row in attempts:
        payout, reversal = events.get(row['payout_id']), events.get(row['reversal_id'])
        require(payout is not None and reversal is not None
            and payout['loan_id'] == reversal['loan_id'] == snapshot['loan_id']
            and payout['event_kind'] == 'DISBURSAL' and reversal['event_kind'] == 'REVERSAL'
            and reversal['reversal_of_id'] == payout['id']
            and payout['effective_date'] == reversal['effective_date'] == row['date']
            and payout['effective_date'] >= actual['effective_date']
            and payout['id'] < reversal['id'] < actual['id']
            and payout['payload_fingerprint'] == row['payout_sha256']
            and reversal['payload_fingerprint'] == row['reversal_sha256']
            and payout['payload']['values'] == reversal['payload']['values'],
            'Portable correction differs from its retained payout/reversal pair.')


def remap_correction(evidence, *, refs, workspace_id):
    from apps.tenant_apps.loans.models import PawnLoanEvent
    attempts = []
    for row in evidence['attempts']:
        payout = PawnLoanEvent.objects.get(workspace_id=workspace_id,
            pk=refs['PawnLoanEvent'][row['payout_id']])
        reversal = PawnLoanEvent.objects.get(workspace_id=workspace_id,
            pk=refs['PawnLoanEvent'][row['reversal_id']])
        attempts.append(dict(row, payout_id=payout.pk, reversal_id=reversal.pk,
            payout_sha256=payout.payload_fingerprint, reversal_sha256=reversal.payload_fingerprint))
    return dict(evidence, attempts=attempts)
