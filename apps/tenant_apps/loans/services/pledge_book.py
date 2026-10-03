"""Form E evidence review and atomic, retry-safe permanent page allocation."""
import hashlib
import json
from dataclasses import replace

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.tenancy.context import current_workspace_id
from apps.tenant_apps.loans.documents.pledge_book import LAYOUTS, VERSION, paginate_entries, render_pledge_book
from apps.tenant_apps.loans.documents.display import display_date
from apps.tenant_apps.loans.forms_pledge_book import BookForm, EvidenceReviewForm, BatchForm, SUPPLEMENT_FIELDS
from apps.tenant_apps.loans.models import LoanSeries, PawnLoan, PledgeBook, PledgeBookBatch, PledgeBookEntry, PledgeBookReview
from apps.tenant_apps.loans.selectors.pledge_book import pledge_book_report, UNKNOWN
from .action_access import require_workspace_action


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), default=str).encode()).hexdigest()


def authorize(workspace, actor, *, write=False, exporting=False):
    if current_workspace_id() != workspace.pk:
        raise PermissionDenied('Form E requires the matching Workspace context.')
    actions = ['workspace.settings.manage'] if write else []
    if exporting:
        actions.append('data.export')
    require_workspace_action(workspace, actor, *actions)


def validate(form):
    if not form.is_valid():
        raise ValidationError(form.errors.as_text())
    return form.cleaned_data


@transaction.atomic
def open_book(*, workspace, actor, data):
    authorize(workspace, actor, write=True)
    values = validate(BookForm(data, workspace=workspace))
    series = LoanSeries.objects.select_for_update().get(pk=values['series'].pk, workspace=workspace)
    fields = {key: values[key] for key in ('title', 'layout', 'starts_on', 'first_page', 'opening_note')}
    existing = PledgeBook.objects.filter(series=series).first()
    if existing:
        if all(getattr(existing, key) == value for key, value in fields.items()):
            return existing
        raise ValueError('This series already has a book. Open its existing pending entries and saved batches.')
    return PledgeBook.objects.create(workspace=workspace, series=series, created_by=actor, **fields)


def original_basis(row):
    return digest({key: row[key] for key in ('loan_id', 'number', 'date', 'borrower', 'address', 'principal',
        'rates', 'tenure', 'descriptions', 'valuations', 'owner', 'source', 'blockers')})


def apply_reviews(report):
    latest = {}
    for review in PledgeBookReview.objects.filter(loan_id__in=[r['loan_id'] for r in report.entries]).select_related('created_by').order_by('pk'):
        latest[review.loan_id] = review
    rows = []
    for original in report.entries:
        row = dict(original, warnings=list(original['warnings']), basis_sha256=original_basis(original), review_id=None)
        review = latest.get(row['loan_id'])
        if review and review.basis_sha256 == row['basis_sha256']:
            row['review_id'] = review.pk
            for key, value in review.supplements.items():
                row[key] = value if row[key] == UNKNOWN else row[key] + '\nSource supplement: ' + value
            row['warnings'].append(f'Review {review.pk} by {review.created_by.get_username()} on {display_date(review.created_at)} (local time); source: {review.source_reference}; {review.notes}')
        else:
            row['warnings'].append('Administrator source review required before permanent printing (or earlier review is stale).')
        rows.append(row)
    return replace(report, entries=rows)


def pending_report(book, *, actor, cutoff):
    report = pledge_book_report(workspace=book.workspace, actor=actor, license_id=book.series.license_id,
        series_id=book.series_id, start=book.starts_on, end=cutoff, cutoff=cutoff, pending=True)
    return apply_reviews(report)


@transaction.atomic
def review_entry(*, workspace, actor, book_id, loan_id, data):
    authorize(workspace, actor, write=True)
    values = validate(EvidenceReviewForm(data))
    book = PledgeBook.objects.select_for_update().get(pk=book_id, workspace=workspace)
    loan = PawnLoan.objects.select_for_update().get(pk=loan_id, workspace=workspace, series=book.series)
    existing = PledgeBookReview.objects.filter(loan=loan, request_key=values['request_key']).first()
    supplements = {key: values[key] for key in SUPPLEMENT_FIELDS if values[key]}
    if existing:
        if existing.basis_sha256 != values['basis_sha256'] or existing.supplements != supplements or existing.source_reference != values['source_reference'] or existing.notes != values['notes']:
            raise ValueError('This review request was already saved with different details.')
        return existing
    if PledgeBookEntry.objects.filter(loan=loan).exists():
        raise ValueError('This pledge is already on a permanent page. Preserve that page; record corrections in the physical book with source evidence.')
    report = pending_report(book, actor=actor, cutoff=timezone.localdate())
    row = next((r for r in report.entries if r['loan_id'] == loan.pk), None)
    if not row or row['basis_sha256'] != values['basis_sha256']:
        raise ValueError('Source evidence changed or this entry is outside the current queue. Reload and review again.')
    if row['blockers']:
        raise ValueError(' '.join(row['blockers']))
    # Validate against the original projection, not a previous supplement.
    original = pledge_book_report(workspace=workspace, actor=actor, license_id=book.series.license_id,
        series_id=book.series_id, start=book.starts_on, end=timezone.localdate(), cutoff=timezone.localdate(), pending=True)
    raw = next(r for r in original.entries if r['loan_id'] == loan.pk)
    for key in supplements:
        if UNKNOWN not in raw[key]:
            raise ValueError(f'{key.title()} already has frozen evidence. A supplement cannot overwrite it.')
    return PledgeBookReview.objects.create(workspace=workspace, loan=loan, basis_sha256=values['basis_sha256'],
        supplements=supplements, source_reference=values['source_reference'], notes=values['notes'],
        request_key=values['request_key'], created_by=actor)


def batch_plan(book, *, actor, cutoff, mode):
    if mode not in {'full', 'partial'}:
        raise ValueError('Select full pages or include the last partial page.')
    report = pending_report(book, actor=actor, cutoff=cutoff)
    groups = paginate_entries(report.entries, book.layout) if report.entries else []
    config = LAYOUTS[book.layout]
    last_full = bool(groups) and sum(height for _, height in groups[-1]) + config['min_row'] > config['bottom'] - config['top']
    full_groups = groups if last_full else groups[:-1]
    selected = full_groups if mode == 'full' else groups
    ids = {r['loan_id'] for group in selected for r, _ in group}
    selected_report = replace(report, entries=[r for r in report.entries if r['loan_id'] in ids])
    next_page = (book.batches.aggregate(value=Max('last_page'))['value'] or (book.first_page - 1)) + 1
    problems = [f"{r['number']}: " + (' '.join(r['blockers']) if r['blockers'] else 'source review required')
                for r in selected_report.entries if r['blockers'] or not r['review_id']]
    basis = dict(book=book.pk, layout=book.layout, version=VERSION, first_page=next_page, cutoff=cutoff,
                 mode=mode, entries=selected_report.entries, archive_count=report.archive_count, excluded_count=report.excluded_count)
    return dict(report=selected_report, pending=report, next_page=next_page, mode=mode,
                full_groups=len(full_groups), problems=problems, review_sha256=digest(basis))


def finalise_batch(*, workspace, actor, book_id, data):
    authorize(workspace, actor, write=True, exporting=True)
    values = validate(BatchForm(data))
    artifact = None
    try:
        with transaction.atomic():
            book = PledgeBook.objects.select_for_update().select_related('series__license', 'workspace').get(pk=book_id, workspace=workspace)
            existing = book.batches.filter(request_key=values['request_key']).first()
            if existing:
                if existing.review_sha256 != values['review_sha256'] or existing.mode != values['mode'] or existing.cutoff != values['cutoff']:
                    raise ValueError('This print request was already used for different details.')
                return existing
            plan = batch_plan(book, actor=actor, cutoff=values['cutoff'], mode=values['mode'])
            list(PawnLoan.objects.select_for_update().filter(pk__in=[r['loan_id'] for r in plan['report'].entries], workspace=workspace).order_by('pk'))
            plan = batch_plan(book, actor=actor, cutoff=values['cutoff'], mode=values['mode'])
            if plan['review_sha256'] != values['review_sha256']:
                raise ValueError('Pending entries, evidence or page numbers changed. Preview and confirm the new batch.')
            if not plan['report'].entries:
                raise ValueError('No full pages are ready. Choose Include last partial page, or wait for more entries.')
            if plan['problems']:
                raise ValueError('Resolve Needs attention before finalising: ' + '; '.join(plan['problems']))
            report = plan['report']
            issuance = dict(first_page=plan['next_page'], reference=book.reference, title=book.title,
                            actor=actor.get_username(), opening_note=book.opening_note)
            pdf, manifest, pages = render_pledge_book(report, book.layout, issuance=issuance, with_manifest=True)
            snapshot = json.loads(json.dumps(dict(issuance=issuance, entries=report.entries, layout=book.layout,
                cutoff=report.cutoff, generated_at=report.generated_at, archive_count=report.archive_count,
                excluded_count=report.excluded_count, manifest=manifest), default=str))
            batch = PledgeBookBatch(workspace=workspace, book=book, first_page=plan['next_page'],
                last_page=plan['next_page'] + pages - 1, mode=values['mode'], cutoff=values['cutoff'],
                snapshot=snapshot, snapshot_sha256=digest(snapshot), review_sha256=values['review_sha256'],
                artifact_sha256=hashlib.sha256(pdf).hexdigest(), template_version=VERSION,
                request_key=values['request_key'], created_by=actor)
            batch.artifact.save('pledge-book.pdf', ContentFile(pdf), save=False)
            artifact = batch.artifact
            batch.save()
            for row in report.entries:
                first, last = manifest[row['loan_id']]
                PledgeBookEntry.objects.create(workspace=workspace, batch=batch, loan_id=row['loan_id'],
                    first_page=first, last_page=last, created_by=actor)
            return batch
    except Exception:
        if artifact:
            # Only bytes newly created by this failed command; never a retained batch.
            artifact.storage.delete(artifact.name)
        raise
