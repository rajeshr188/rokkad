"""Read-only Form E working register. Unknown evidence never becomes a guessed fact."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q, Min, F
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import (
    HistoricalLoanEvidence, LoanDocumentIssue, LoanLicense, LoanSeries, PawnLoan,
    PawnLoanDisbursalSnapshot, PawnLoanEvent, PawnLoanRelease,
)
from apps.tenant_apps.loans.documents.display import display_date, display_money
from apps.tenant_apps.loans.services.action_access import require_workspace_action
from apps.tenant_apps.loans.services.opening_evidence import read_opening_evidence

MAX_ENTRIES = 100
ORIGINS = ('DISBURSAL', 'MIGRATION_OPENING', 'RENEWAL_OPENING')
COLLECTIONS = ('REPAYMENT', 'RELEASE_RECEIPT', 'AUCTION_RECOVERY')
UNKNOWN = 'Not recorded'


@dataclass
class PledgeBookReport:
    license: object
    series: object
    start: date
    end: date
    cutoff: date
    generated_at: object
    entries: list
    archive_count: int
    excluded_count: int
    pending_count: int = 0


def _money(value):
    return UNKNOWN if value is None else 'Rs ' + display_money(value, grouping=True)


def _number(value):
    return UNKNOWN if value is None else format(Decimal(str(value)).normalize(), 'f')


def _event_line(event, reversed_ids):
    values = event.payload.get('values', {})
    amounts = {k: Decimal(str(values.get(k, '0'))) for k in ('principal', 'interest', 'fees')}
    amount = sum(amounts.values(), Decimal('0'))
    prefix = 'REVERSED ' if event.pk in reversed_ids else ''
    label = {'REPAYMENT': 'Payment', 'RELEASE_RECEIPT': 'Release receipt', 'AUCTION_RECOVERY': 'Auction recovery'}[event.event_kind]
    if event.payload.get('release', {}).get('paper_closure', {}).get('closure_basis') == 'PAPER_SETTLEMENT':
        label = 'Paper closing settlement (physical cash unconfirmed)'
    # Concessions are not money received and must not inflate the receipt.
    text = f"{prefix}{display_date(event.effective_date)} {label}: {_money(amount)} (principal {_money(amounts['principal'])}, interest {_money(amounts['interest'])}, fees {_money(amounts['fees'])}); event {event.pk}"
    if Decimal(str(values.get('interest_concession', '0'))):
        text += '; interest concession ' + _money(values['interest_concession'])
    correction = event.payload.get('history_correction')
    if correction:
        text += f"; historical correction: {correction.get('description', 'Revised historical evidence')}; source event {correction.get('source_event_id') or 'missing receipt'}; recorded {display_date(event.created_at)}; no new collection"
    return text


def _entry(loan, tickets, *, start, end, imported_particulars=None):
    events = loan.register_events
    reversed_ids = {event.reversal_of_id for event in events if event.reversal_of_id}
    origins = [e for e in events if e.event_kind in ORIGINS]
    warnings = []
    native = [s for s in loan.register_disbursals if start <= s.loan_event.effective_date <= end]
    live_native = [s for s in native if s.loan_event_id not in reversed_ids]
    snapshot = (live_native or native or [None])[-1]
    opening = next((e for e in origins if e.event_kind == 'MIGRATION_OPENING'), None)
    recorded_renewal = next((e for e in origins if e.event_kind == 'RENEWAL_OPENING'
                            and e.payload.get('recording', {}).get('schema') == 'recorded-renewal/1'), None)
    approval_id = None
    if snapshot:
        if snapshot.basis == "RECORDED":
            recording = snapshot.evidence["recording"]
            source = recording["terms"]
            source_label = f'Recorded paper payout {snapshot.loan_event_id}; source {recording["source_reference"]}'
            warnings.append('Original contract recorded afterward; no contemporaneous digital lending approval is claimed.')
        else:
            source = snapshot.approval_snapshot.payload
            source_label = f'Disbursal {snapshot.loan_event_id}; approval {snapshot.approval_snapshot_id}'
        approval_id = snapshot.approval_snapshot_id
        items = source.get('collateral', [])
        principal = snapshot.gross_principal
        loan_day = snapshot.loan_event.effective_date
        number = source.get('loan_number', loan.loan_number)
        tenure = str(source.get('tenure_months', UNKNOWN)) + ' months'
        if len(native) > 1 or snapshot.loan_event_id in reversed_ids:
            warnings.append('Disbursal correction/reversal exists. Review every attempt before assigning a permanent book entry.')
        for event in origins:
            if event.event_kind == 'DISBURSAL':
                values = event.payload.get('values', {})
                if Decimal(str(values.get('advance_interest', '0'))) or Decimal(str(values.get('fees', '0'))):
                    warnings.append(f"Disbursal {event.pk}: advance interest {_money(values.get('advance_interest', '0'))}, deducted fees {_money(values.get('fees', '0'))}; deductions, not a later cash payment.")
    elif recorded_renewal:
        recording = recorded_renewal.payload['recording']
        source = recording['terms']
        items = source['collateral']
        principal = Decimal(source['principal_amount'])
        loan_day = recorded_renewal.effective_date
        number = source['loan_number']
        tenure = str(source['tenure_months']) + ' months'
        source_label = f'Recorded paper renewal {recorded_renewal.pk}; source {recording["source_reference"]}'
        from .recorded_settlements import opening_cash
        cash, correction_status = opening_cash(recorded_renewal)
        if correction_status:
            warnings.append(correction_status)
        if cash:
            handling = 'stayed held' if cash['custody'] == 'HELD' else 'returned and repledged'
            warnings.append(f"Recorded renewal: principal carried {_money(cash['principal_carried'])}; gross new advance {_money(cash['gross_advance'])}; cash received {_money(cash['cash_received'])}; cash paid {_money(cash['cash_paid'])}; old interest offset {_money(cash['interest_offset'])}; collateral {handling}. No original digital approval is claimed.")
        else:
            warnings.append('Principal carried from the preceding loan; collateral remained held. No fresh cash payout or original digital approval is claimed.')
    elif opening:
        review = read_opening_evidence(loan, opening)['review']
        items = [dict(description=i['description'], quantity=i.get('quantity'), metal=i['metal'],
                      gross_weight=i.get('gross_weight'), net_weight=i['net_weight'],
                      latest_appraised_value=(i['valuation'].get('amount') if i['valuation'].get('date') == review['terms']['original_date'] else None), monthly_interest_rate=i['monthly_rate'])
                 for i in review['collateral']]
        principal = sum((Decimal(i['original_principal']) for i in review['collateral']), Decimal('0'))
        loan_day = date.fromisoformat(review['terms']['original_date'])
        number = review['source']['number']
        tenure = UNKNOWN
        source = {}
        source_label = f'Imported opening {opening.pk}'
        warnings.append('Imported opening: complete earlier payments and dated original valuation are not established. Reconcile the legacy pledge book.')
    else:
        # Retain an explicit row for legacy/native contracts lacking snapshots.
        source = {}
        items = []
        principal = None
        loan_day = next((e.effective_date for e in origins), loan.loan_date)
        number, tenure = loan.loan_number, UNKNOWN
        source_label = 'Origination event without supported frozen particulars'
        warnings.append('Origination/renewal evidence needs a dedicated mapping; no current collateral or balances substituted.')
    ticket = next((t for t in tickets.get(str(loan.pk), [])
                   if (t.source_snapshot or {}).get('approval_id') == approval_id and approval_id is not None), None)
    fields = (ticket.source_snapshot or {}).get('fields', {}) if ticket else {}
    borrower = fields.get('borrower.name') or UNKNOWN
    address = fields.get('borrower.address') or UNKNOWN
    if opening and not snapshot and imported_particulars:
        borrower = imported_particulars['borrower'] or UNKNOWN
        address = imported_particulars['address'] or UNKNOWN
        if imported_particulars['tenure_months'] is not None:
            tenure = str(imported_particulars['tenure_months']) + ' months (recorded in source)'
        elif imported_particulars['tenure_basis'] == 'OWNER_MISSING_MATURITY_RULE':
            warnings.append('Original tenure was not recorded; the migration uses a separately accepted maturity assumption.')
        warnings.append('Borrower/address are retained source-snapshot particulars as of '
                        + display_date(date.fromisoformat(imported_particulars['snapshot_date']))
                        + '; not proof of their particulars on the original pawning day. Current customer edits are not substituted.')
    elif not ticket:
        warnings.append('Original name/address snapshot unavailable. The current customer profile is not substituted.')
    else:
        warnings.append(f'Name/address from ticket issued {display_date(ticket.issued_at)}; verify these were the particulars at pawning.')
    descriptions, valuations, rates = [], [], []
    for index, item in enumerate(items, 1):
        descriptions.append(f"{index}. {item['description']}; {item.get('metal', UNKNOWN)}; qty {_number(item.get('quantity'))}; gross {_number(item.get('gross_weight'))} g; net {_number(item.get('net_weight'))} g")
        valuations.append(f"{index}. {_money(item.get('latest_appraised_value'))}")
        rate = item.get('monthly_interest_rate')
        if rate is None:
            rate = source.get('monthly_interest_rate')
        rates.append(f"{index}. {_number(rate)}% / month" if rate is not None else f'{index}. {UNKNOWN}')
    if any(i.get('latest_appraised_value') is None for i in items) or not items:
        warnings.append('Original article valuation is missing for one or more items.')
    payments = [_event_line(e, reversed_ids) for e in events if e.event_kind in COLLECTIONS]
    closures, recipients = [], []
    release_by_event = {r.loan_event_id: r for r in loan.register_releases}
    financial_restatements = {e.reversal_of_id for e in events if e.event_kind == 'REVERSAL'
        and e.payload.get('history_correction', {}).get('schema') == 'recorded-history-correction/1'}
    for e in events:
        if e.event_kind not in {'RELEASE_RECEIPT', 'AUCTION_RECOVERY', 'REVERSAL', 'RENEWAL_SETTLEMENT', 'RENEWAL_OPENING'}:
            continue
        if e.event_kind == 'REVERSAL':
            warnings.append(f"{display_date(e.effective_date)} reversal of event {e.reversal_of_id}; recorded {display_date(e.created_at)}. Keep the original entry and correction trace.")
            continue
        if e.event_kind.startswith('RENEWAL'):
            renewal = e.payload.get('renewal', {})
            cash = renewal.get('cash_evidence')
            if e.event_kind == 'RENEWAL_SETTLEMENT' and e.pk in reversed_ids:
                warnings.append(f"Superseded renewal settlement event {e.pk}; original cash evidence retained in loan history.")
                continue
            if e.payload.get('history_correction', {}).get('role') == 'SETTLEMENT':
                from .recorded_settlements import correction_label
                warnings.append(correction_label(e))
            if e.event_kind == 'RENEWAL_SETTLEMENT' and cash:
                payments.append(f"{display_date(e.effective_date)} Renewal receipt: {_money(cash['cash_received'])}; cash paid {_money(cash['cash_paid'])}; principal paid {_money(cash['principal_paid'])}; interest settled {_money(cash['interest_settled'])} including offset {_money(cash['interest_offset'])}; principal carried {_money(cash['principal_carried'])}; gross new advance {_money(cash['gross_advance'])}")
                if cash['custody'] == 'RETURNED_REPLEDGED':
                    closures.append(f"{display_date(e.effective_date)} Returned and repledged to successor loan; event {e.pk}")
                    recipients.append(f"{display_date(e.effective_date)} {cash['recipient']}; address {UNKNOWN}")
                else:
                    warnings.append(f"{display_date(e.effective_date)} Renewal collateral stayed held; no physical return.")
                continue
            if e.event_kind == 'RENEWAL_SETTLEMENT' and e.payload.get('recorded_admission'):
                payments.append(f"{display_date(e.effective_date)} Renewal receipt: {_money(renewal['amount_received'])} (principal {_money(renewal['principal_paid'])}, interest {_money(e.payload['values']['interest'])}); principal carried {_money(renewal['successor_principal'])}")
            warnings.append(f"{display_date(e.effective_date)} {e.event_kind.replace('_', ' ').lower()} event {e.pk}; not treated as a cash receipt or physical redemption.")
            continue
        release = release_by_event.get(e.pk)
        if e.payload.get('history_correction', {}).get('role') == 'SETTLEMENT':
            from .recorded_settlements import correction_label
            warnings.append(correction_label(e))
            # The original custody entry already records the physical return.
            continue
        paper_settlement = e.payload.get('release', {}).get('paper_closure', {}).get('closure_basis') == 'PAPER_SETTLEMENT'
        label = ('Paper financial closure; customer handover unconfirmed' if paper_settlement else
            'Auction' if e.event_kind == 'AUCTION_RECOVERY' else ('Partial collateral release' if release and not release.is_full_release else 'Redemption'))
        status = ('Settlement corrected; handover remains unconfirmed: ' if paper_settlement else 'Settlement corrected; original handover retained: ') if e.pk in financial_restatements else ('REVERSED ' if e.pk in reversed_ids else '')
        if paper_settlement:
            warnings.append('Paper closure establishes financial settlement; physical cash and customer handover were not confirmed.')
        closures.append(f"{status}{display_date(e.effective_date)} {label}; event {e.pk}")
        line = getattr(release, 'batch_line', None) if release else None
        name = line.collector_name if line else (e.payload.get('release', {}).get('paper_closure', {}).get('collector_name') or e.payload.get('auction', {}).get('buyer_name', UNKNOWN))
        recipients.append(f'{display_date(e.effective_date)} {name}; address {UNKNOWN}')
    warnings.append('Separate article owner and address not recorded; do not assume the pawner is the owner.')
    if recipients:
        warnings.append('Redeemer/purchaser address requires source review; current customer address is not proof of recipient address.')
    return dict(loan_id=loan.pk, number=number, date=loan_day, borrower=borrower, address=address,
                principal=_money(principal), rates='\n'.join(rates) or UNKNOWN, tenure=tenure,
                descriptions='\n'.join(descriptions) or UNKNOWN, valuations='\n'.join(valuations) or UNKNOWN,
                payments='\n'.join(payments), closures='\n'.join(closures), owner=UNKNOWN,
                recipients='\n'.join(recipients), warnings=warnings, source=source_label,
                series=loan.series.pawn_display_name,
                blockers=(["Unsupported origination or renewal evidence."] if not snapshot and not opening and not recorded_renewal else []) +
                         (["Disbursal attempts/reversals require a dedicated original-entry reconciliation."] if snapshot and (len(native) > 1 or snapshot.loan_event_id in reversed_ids) else []))


def pledge_book_report(*, workspace, actor, license_id, series_id=None, start, end, cutoff, exporting=False, pending=False):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied('Pledge book requires the matching Workspace context.')
    require_workspace_action(workspace, actor, *(['data.export'] if exporting else []))
    if not start <= end <= cutoff <= timezone.localdate():
        raise ValueError('Use a loan-date range ending on or before the activity cutoff; future dates are unavailable.')
    license = LoanLicense.objects.get(pk=license_id, workspace=workspace)
    series = LoanSeries.objects.prefetch_related('number_sequences').get(pk=series_id, workspace=workspace, license=license) if series_id else None
    base = PawnLoan.objects.filter(workspace=workspace, license=license)
    if series:
        base = base.filter(series=series)
    # Paid-out evidence, rather than approval or current ACTIVE status, admits a row.
    origin_filter = Q(loan_events__event_kind__in=('DISBURSAL', 'RENEWAL_OPENING'), loan_events__effective_date__range=(start, end)) | Q(loan_events__event_kind='MIGRATION_OPENING', loan_events__effective_date__lte=cutoff, loan_date__range=(start, end))
    selected = base.filter(origin_filter).distinct()
    eligible_ids = selected.values('pk')
    if pending:
        selected = selected.filter(pledge_book_entry__isnull=True)
    pending_count = selected.count()
    if pending_count > MAX_ENTRIES and not pending:
        raise ValueError(f'Select a shorter loan-date range or a series: this working preview supports up to {MAX_ENTRIES} entries.')
    loans = list(selected.select_related('series__license').prefetch_related('series__number_sequences',
        Prefetch('loan_events', queryset=PawnLoanEvent.objects.filter(effective_date__lte=cutoff).order_by('effective_date', 'pk'), to_attr='register_events'),
        Prefetch('disbursal_snapshots', queryset=PawnLoanDisbursalSnapshot.objects.select_related('approval_snapshot', 'loan_event').filter(loan_event__effective_date__lte=cutoff).order_by('created_at', 'pk'), to_attr='register_disbursals'),
        Prefetch('releases', queryset=PawnLoanRelease.objects.select_related('batch_line').filter(effective_date__lte=cutoff), to_attr='register_releases'),
    ).annotate(register_day=Coalesce(Min('loan_events__effective_date', filter=Q(loan_events__event_kind__in=('DISBURSAL', 'RENEWAL_OPENING'))), F('loan_date')))
      .order_by('register_day', 'loan_number', 'pk')[:MAX_ENTRIES])
    tickets = {}
    for ticket in LoanDocumentIssue.objects.filter(workspace=workspace, document_type='loan_ticket', source_type='PawnLoan',
            source_id__in=[str(l.pk) for l in loans], issue_kind='OFFICIAL', source_snapshot__isnull=False).order_by('issued_at', 'pk'):
        tickets.setdefault(ticket.source_id, []).append(ticket)
    from apps.tenant_apps.data_portability.source_particulars import imported_loan_particulars
    imported = imported_loan_particulars([l for l in loans if any(e.event_kind == 'MIGRATION_OPENING' for e in l.register_events)])
    entries = [_entry(l, tickets, start=start, end=end, imported_particulars=imported.get(l.pk)) for l in loans]
    entries.sort(key=lambda e: (e['date'], e['number'], e['loan_id']))
    # Archive claims have no normalized licence/series binding. Never silently mix them.
    archive_count = HistoricalLoanEvidence.objects.filter(workspace=workspace).count()
    excluded_count = base.filter(loan_date__range=(start, end)).exclude(pk__in=eligible_ids).count()
    return PledgeBookReport(license, series, start, end, cutoff, timezone.now(), entries, archive_count, excluded_count, pending_count)
