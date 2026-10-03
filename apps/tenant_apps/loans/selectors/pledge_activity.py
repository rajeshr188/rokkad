"""Annotation aid: recorded dates reveal late business events; never claims filing."""
from django.utils import timezone

from apps.tenant_apps.loans.models import PawnLoanEvent, PledgeBookEntry, PawnLoanRelease
from apps.tenant_apps.loans.selectors.pledge_book import COLLECTIONS, _event_line, UNKNOWN
from apps.tenant_apps.loans.services.pledge_book import authorize


def daily_activity(book, *, actor, start, end, basis='recorded'):
    authorize(book.workspace, actor)
    if basis not in {'recorded', 'business'} or not start <= end <= timezone.localdate():
        raise ValueError('Choose valid dates and a recording-date or business-date filter.')
    kinds = (*COLLECTIONS, 'REVERSAL', 'RENEWAL_SETTLEMENT', 'RENEWAL_OPENING', 'DISBURSAL')
    field = 'created_at__date__range' if basis == 'recorded' else 'effective_date__range'
    events = list(PawnLoanEvent.objects.filter(workspace=book.workspace, loan__series=book.series,
        event_kind__in=kinds, **{field: (start, end)}).select_related('loan', 'created_by', 'reversal_of').order_by('created_at', 'pk')[:501])
    if len(events) > 500:
        raise ValueError('More than 500 events: narrow the date range before printing this activity list.')
    entries = {e.loan_id: e for e in PledgeBookEntry.objects.filter(loan_id__in=[e.loan_id for e in events], workspace=book.workspace).select_related('batch__book')}
    releases = {r.loan_event_id: r for r in PawnLoanRelease.objects.filter(loan_event_id__in=[e.pk for e in events]).select_related('batch_line')}
    reversed_ids = set(PawnLoanEvent.objects.filter(reversal_of_id__in=[e.pk for e in events]).values_list('reversal_of_id', flat=True))
    rows = []
    for event in events:
        entry = entries.get(event.loan_id)
        if event.event_kind in COLLECTIONS:
            detail = _event_line(event, reversed_ids)
        elif event.event_kind == 'REVERSAL':
            original = event.reversal_of
            detail = f'Reversal of event {original.pk} ({original.event_kind}, business date {original.effective_date:%d/%m/%Y}). Preserve the original and annotate the correction.'
        elif event.event_kind.startswith('RENEWAL'):
            detail = 'Renewal: review both linked pledges; not assumed to be a cash receipt or physical redemption.'
            from .recorded_settlements import correction_label
            if correction_label(event):
                detail += ' ' + correction_label(event) + '.'
        else:
            detail = 'New payout: use the pending pledge queue. A later correction does not replace the saved page.'
        release = releases.get(event.pk)
        line = getattr(release, 'batch_line', None) if release else None
        if release:
            detail += ' Full redemption.' if release.is_full_release else ' Partial collateral release; remaining pledge continues.'
        if event.event_kind in {'RELEASE_RECEIPT', 'AUCTION_RECOVERY'}:
            recipient = line.collector_name if line else (event.payload.get('release', {}).get('paper_closure', {}).get('collector_name')
                or event.payload.get('auction', {}).get('buyer_name', UNKNOWN))
            detail += f' Recipient: {recipient}; recipient address: {UNKNOWN}.'
        rows.append(dict(event=event, entry=entry, detail=detail,
            reference=f'{entry.batch.book.reference}, pages {entry.first_page}-{entry.last_page}' if entry else 'No saved page; check earlier paper book / pending queue',
            included=bool(entry and event.created_at <= entry.batch.created_at and event.effective_date <= entry.batch.cutoff),
            late=timezone.localdate(event.created_at) > event.effective_date))
    return rows
