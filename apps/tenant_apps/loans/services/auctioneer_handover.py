"""Reviewed, immutable auctioneer cohorts and current-state reconciliation."""
import hashlib
import json
import uuid

from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db import OperationalError, transaction
from django.utils import timezone

from apps.orgs.access import resolve_workspace_access
from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.models import AuctioneerHandover, AuctioneerHandoverRevision, LoanLicense, PawnLoan, PawnLoanAuction
from apps.tenant_apps.loans.selectors import get_pawn_loan_balance
from apps.tenant_apps.party.selectors import party_identification
from .action_access import require_workspace_action
from .statutory_notices import auction_readiness

LIMIT = 100
SALT = 'loans.auctioneer-handover.v1'


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def authorize(workspace, actor, *, write=False, exporting=False):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied('Auctioneer lists require the matching Workspace context.')
    access = resolve_workspace_access(actor=actor, workspace=workspace)
    access.require('data.view')
    access.require('workspace.settings.manage')
    if exporting:
        access.require('data.export')
    if write:
        require_workspace_action(workspace, actor, 'workspace.settings.manage')


def resolve_numbers(workspace, license_id, numbers):
    """Exact numbers only; no prefix guessing, ranges or cross-licence matches."""
    numbers = [n.strip().casefold() for n in numbers.replace(',', '\n').splitlines() if n.strip()]
    if not numbers or len(numbers) > LIMIT or len(set(numbers)) != len(numbers):
        raise ValueError(f'Enter 1–{LIMIT} distinct complete loan numbers, one per line or comma-separated.')
    from django.db.models.functions import Lower
    loans = list(PawnLoan.objects.filter(workspace=workspace, license_id=license_id)
                 .annotate(number_lower=Lower('loan_number')).filter(number_lower__in=numbers).order_by('pk'))
    if len(loans) != len(numbers) or len({l.loan_number.casefold() for l in loans}) != len(numbers):
        raise ValueError('Some numbers are missing or ambiguous in this licence. Use the full prefix and number, including leading zeroes.')
    return [loan.pk for loan in loans]


def rows_for(workspace, license_id, loan_ids, *, lock=False):
    if not 1 <= len(loan_ids) <= LIMIT or len(set(loan_ids)) != len(loan_ids):
        raise ValueError(f'A handover must contain 1–{LIMIT} distinct loans.')
    qs = PawnLoan.objects.filter(workspace=workspace, pk__in=loan_ids).order_by('pk')
    if lock:
        # Auction commands can hold an auction before touching its loan. NOWAIT
        # avoids introducing a lock cycle with ordinary lending/custody commands.
        try:
            list(PawnLoanAuction.objects.filter(workspace=workspace, loan_id__in=loan_ids)
                 .order_by('pk').select_for_update(nowait=True).values_list('pk', flat=True))
            list(qs.select_for_update(nowait=True).values_list('pk', flat=True))
        except OperationalError as exc:
            if getattr(exc.__cause__, 'sqlstate', None) != '55P03':
                raise
            raise ValueError('A loan is being updated. Wait for that action to finish, then refresh and review again.') from exc
    loans = list(qs.select_related('borrower', 'series', 'license')
                 .prefetch_related('collateral_items', 'series__number_sequences', 'auctions', 'loan_events'))
    if len(loans) != len(loan_ids):
        raise ValueError('A selected loan is no longer available in this Workspace. Reconcile the source list.')
    today = timezone.localdate()
    rows = []
    for loan in loans:
        identification = party_identification(loan.borrower)
        items = list(loan.collateral_items.all())
        holds = []
        if loan.license_id != license_id:
            holds.append('Licence changed — review separately')
        if loan.state != 'ACTIVE':
            holds.append(f'Loan is {loan.get_state_display()}')
        if not items or any(item.custody_state != 'IN_VAULT' for item in items):
            holds.append('Collateral is missing or not wholly in the vault; review release/custody')
        principal = interest = fees = None
        due_date = None
        try:
            balance = get_pawn_loan_balance(loan.pk, as_of_date=today)
            principal, interest, fees = (str(balance.principal_outstanding), str(balance.interest_outstanding), str(balance.fees_outstanding))
            due_date = balance.due_date.isoformat() if balance.due_date else None
            if balance.financially_settled:
                holds.append('Recorded debt is settled')
            elif not balance.is_overdue:
                holds.append('Not overdue under the existing auction initiation check')
        except (ValueError, ObjectDoesNotExist) as exc:
            holds.append('Financial evidence needs review: ' + str(exc))
        auctions = list(loan.auctions.all())
        open_auctions = [a for a in auctions if a.state in {'INITIATED', 'IN_PROGRESS'}]
        auction = max(open_auctions or auctions, key=lambda a: a.attempt_number, default=None)
        checks = ['No open auction; arrange and review each loan separately.']
        if open_auctions:
            auction.loan = loan
            checks = list(auction_readiness(auction).issues)
        rows.append(dict(loan_id=loan.pk, number=loan.loan_number, loan_date=loan.loan_date.isoformat(),
            series=str(loan.series.pawn_display_name), license=loan.license.license_number,
            borrower=loan.borrower.display_name, relation=loan.borrower.relation_display,
            address=identification['address'] or 'Not recorded', phone=identification['phone'] or 'Not recorded',
            state=loan.state, due_date=due_date, principal=principal, interest=interest, fees=fees,
            activity=[e.pk for e in loan.loan_events.all()],
            items=[dict(id=i.pk, description=i.description, metal=i.metal, quantity=i.quantity,
                        gross=str(i.gross_weight) if i.gross_weight is not None else None,
                        net=str(i.net_weight), custody=i.custody_state) for i in items],
            holds=holds, eligible=not holds, auction_id=auction.pk if auction else None,
            auction_number=auction.auction_number if auction else '',
            auction_state=auction.state if auction else '',
            scheduled_date=auction.scheduled_date.isoformat() if auction else None,
            readiness=checks))
    return rows


def plan(*, workspace, actor, license_id=None, loan_ids=None, title='', auctioneer='', handover=None, lock=False):
    authorize(workspace, actor)
    previous = None
    if handover:
        if handover.workspace_id != workspace.pk:
            raise PermissionDenied('Handover belongs to another Workspace.')
        license_id, loan_ids, title, auctioneer = handover.license_id, handover.loan_ids, handover.title, handover.auctioneer
        previous = handover.revisions.order_by('-number').first()
    licence = LoanLicense.objects.get(pk=license_id, workspace=workspace)
    rows = rows_for(workspace, license_id, loan_ids, lock=lock)
    prior = {r['loan_id']: r for r in previous.snapshot['rows']} if previous else {}
    for row in rows:
        old = prior.get(row['loan_id'])
        row['changes'] = [key for key in ('state', 'principal', 'interest', 'fees', 'items', 'borrower', 'relation',
            'address', 'phone', 'license', 'series', 'number', 'loan_date', 'due_date', 'holds', 'auction_id',
            'auction_state', 'scheduled_date', 'readiness', 'activity') if old and row[key] != old[key]]
        row['previous_principal'] = old['principal'] if old else row['principal']
        row['previous_state'] = old['state'] if old else row['state']
        row['suggested'] = row['eligible'] and (old['included'] if old else True)
    result = dict(workspace_id=workspace.pk, workspace_name=workspace.name, license_id=license_id, license=licence.license_number,
        title=title, auctioneer=auctioneer, loan_ids=sorted(loan_ids), as_of=timezone.localdate().isoformat(),
        previous=previous.number if previous else 0, rows=rows)
    return result


def review_token(plan, actor, handover=None):
    return signing.dumps(dict(workspace_id=plan['workspace_id'], actor_id=actor.pk,
        handover_id=handover.pk if handover else None, license_id=plan['license_id'], loan_ids=plan['loan_ids'],
        title=plan['title'], auctioneer=plan['auctioneer'], digest=digest(plan), request_key=uuid.uuid4().hex), salt=SALT, compress=True)


@transaction.atomic
def save_review(*, workspace, actor, token, included_ids, notes):
    authorize(workspace, actor, write=True)
    try:
        payload = signing.loads(token, salt=SALT, max_age=3600)
    except signing.BadSignature as exc:
        raise ValueError('Review expired or invalid. Refresh the list and review again.') from exc
    if payload['workspace_id'] != workspace.pk or payload['actor_id'] != actor.pk:
        raise PermissionDenied('Review belongs to another user or Workspace.')
    try:
        included_ids = sorted(set(int(pk) for pk in included_ids))
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid loan selection.') from exc
    notes = str(notes).strip()
    if not notes or len(notes) > 2000:
        raise ValueError('Add a review note (up to 2,000 characters), including why any remaining loan is withheld.')
    request_hash = digest(dict(token=payload, included=included_ids, notes=notes))
    # One lock also serializes repeated first-save requests, before a handover exists.
    LoanLicense.objects.select_for_update().get(pk=payload['license_id'], workspace=workspace)
    existing = AuctioneerHandoverRevision.objects.filter(workspace=workspace, request_key=payload['request_key']).first()
    if existing:
        if existing.request_sha256 != request_hash:
            raise ValueError('This review was already saved with different instructions. Open its saved version.')
        return existing
    handover = None
    if payload['handover_id']:
        handover = AuctioneerHandover.objects.select_for_update().get(pk=payload['handover_id'], workspace=workspace)
    current = plan(workspace=workspace, actor=actor, handover=handover, license_id=payload['license_id'],
        loan_ids=payload['loan_ids'], title=payload['title'], auctioneer=payload['auctioneer'], lock=True)
    if digest(current) != payload['digest']:
        raise ValueError('Loans or the saved list changed after preview. Refresh and review the changes before saving.')
    eligible = {r['loan_id'] for r in current['rows'] if r['eligible']}
    if not set(included_ids) <= eligible:
        raise ValueError('A selected loan is on hold or outside this list. Review the highlighted reasons.')
    if not handover and not included_ids:
        raise ValueError('Select at least one remaining loan for the initial handover.')
    if not handover:
        if not current['title'].strip() or not current['auctioneer'].strip():
            raise ValueError('A title and intended auctioneer are required.')
        handover = AuctioneerHandover.objects.create(workspace=workspace, created_by=actor,
            license_id=current['license_id'], loan_ids=current['loan_ids'], title=current['title'],
            auctioneer=current['auctioneer'], request_key=payload['request_key'])
    for row in current['rows']:
        row['included'] = row['loan_id'] in included_ids
    current.update(notes=notes, reviewed_by=actor.get_full_name() or actor.get_username(),
                   reviewed_at=timezone.now().isoformat(), reference=handover.reference, version='auctioneer-list-v1')
    return AuctioneerHandoverRevision.objects.create(workspace=workspace, created_by=actor, handover=handover,
        number=current['previous'] + 1, snapshot=current, snapshot_sha256=digest(current),
        request_key=payload['request_key'], request_sha256=request_hash)
