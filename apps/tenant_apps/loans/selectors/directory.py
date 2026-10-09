"""Paged ordinary loans and retained closed source records, without admission."""
from django.core.paginator import Paginator
from django.db.models import BinaryField, BooleanField, Case, CharField, Exists, F, Func, IntegerField, OuterRef, Q, Value, When
from django.db.models.fields.json import KT
from django.db.models.functions import Cast, Coalesce, Concat, Length, Replace

from apps.tenant_apps.loans.models import HistoricalLoanEvidence, HistoricalLoanImport, PawnLoan
from apps.tenant_apps.loans.models import current_tenant_workspace_id
from .archive import historical_loan_summary


ARCHIVE_CANDIDATE_LIMIT = 500


def _source_bindings(prefix=''):
    system, source_id = F(prefix+'source_system'), F(prefix+'source_id')
    namespace_prefix = Concat(Value('legacy:'), Replace(Cast(F(prefix+'source_namespace'), CharField()), Value('-'), Value('')), Value(':'))
    valid_legacy = (Q(**{prefix+'source_system__startswith':namespace_prefix,
        prefix+'source_system__regex':r'^legacy:[0-9a-f]{32}:[a-z][a-z0-9_]{0,62}$'})
        & ~Q(**{prefix+'source_system__endswith':':public'}))
    material = Concat(Cast(Length(system), CharField()), Value(':'), system, source_id)
    closed_key = Concat(Value('closed:'), Func(Func(Func(material, Value('UTF8'), function='convert_to', output_field=BinaryField()),
        function='sha256', output_field=BinaryField()), Value('hex'), function='encode', output_field=CharField()))
    return dict(valid_binding=Case(When(valid_legacy | ~Q(**{prefix+'source_system__startswith':'legacy:'}), then=Value(True)),
        default=Value(False), output_field=BooleanField()),
        binding=Case(When(valid_legacy, then=Concat(Func(system, Value(':'), Value(3), function='split_part', output_field=CharField()),
            Value(':'), source_id)), default=source_id, output_field=CharField()),
        closed_binding=Case(When(**{prefix+'source_system__startswith':'legacy:', 'then':Value(None)}),
            default=closed_key, output_field=CharField()))


def unadmitted_historical_records(workspace_id, *, candidate_ids=None):
    """Use the same scoped identity as find_source_origin; names never merge rows.

    Select one latest retained snapshot per exact source identity. Original archive
    pages retain all snapshots. Financially admitted identities are shown through
    their ordinary loan rather than as duplicate archive cards.
    """
    if current_tenant_workspace_id() != workspace_id:
        raise ValueError('Loan browsing requires the active Workspace.')
    rows = HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id)
    newer = rows.filter(source_namespace=OuterRef('source_namespace'),
        source_system=OuterRef('source_system'), source_id=OuterRef('source_id'), pk__gt=OuterRef('pk'))
    if candidate_ids is not None:
        rows = rows.filter(pk__in=candidate_ids)
    rows = rows.annotate(**_source_bindings())
    # An FK alone does not prove admission: even certified closed positions must
    # match the exact namespace/system/source binding. This fast exclusion uses
    # compact metadata and never broadens the older identity checks below.
    closed_snapshots = HistoricalLoanImport.objects.filter(workspace_id=workspace_id,
        loan__workspace_id=workspace_id, loan__is_imported_closed_position=True,
        archive_evidence__workspace_id=workspace_id).annotate(**_source_bindings('archive_evidence__')).filter(
        valid_binding=True, source_namespace=F('archive_evidence__source_namespace')).filter(
        Q(source_id=F('binding')) | Q(source_id=F('closed_binding'))).values('archive_evidence_id')
    if candidate_ids is not None:
        closed_snapshots = closed_snapshots.filter(archive_evidence_id__in=candidate_ids)
    rows = rows.exclude(pk__in=closed_snapshots)
    origins = HistoricalLoanImport.objects.filter(workspace_id=workspace_id,
        source_namespace=OuterRef('source_namespace')).annotate(
            old_id=KT('document__loan__id'), old_system=KT('document__loan__borrower__source_system'))
    # Separate EXISTS lets PostgreSQL hash the two scoped identity sets instead
    # of rescanning every Workspace import for each retained archive snapshot.
    bound_matches = origins.filter(source_id=OuterRef('binding'))
    old_matches = origins.filter(loan__is_imported_closed_position=False, source_id=OuterRef('source_id'),
        old_id=OuterRef('source_id'), old_system=OuterRef('source_system'))
    closed_matches = origins.filter(source_id=OuterRef('closed_binding'))
    return rows.filter(~Exists(newer)).annotate(admitted=Exists(bound_matches) | Exists(old_matches) | Exists(closed_matches)).filter(
        Q(admitted=False) | Q(valid_binding=False))


def loan_directory_page(*, workspace_id, loan_filter, page):
    """Filter/sort references in SQL, then hydrate only the selected 25 cards."""
    if current_tenant_workspace_id() != workspace_id:
        raise ValueError('Loan browsing requires the active Workspace.')
    archives = HistoricalLoanEvidence.objects.none()
    valid = loan_filter.is_valid()
    fields = loan_filter.form.cleaned_data if valid else {}
    mode = fields.get('records') or 'all'
    loans = loan_filter.qs.filter(workspace_id=workspace_id) if valid else PawnLoan.objects.none()
    if mode == 'historical':
        loans = loans.none()
    # An archive has no trusted local Party/licence/series FK. These filters cannot
    # establish that mapping from a name or from source-local database IDs.
    mapped_filters = any(fields.get(k) for k in ('borrower', 'license', 'series'))
    if valid and mode != 'ordinary' and fields.get('state') in (None, '', 'CLOSED') and not mapped_filters:
        predicate = Q()
        query = (fields.get('q') or '').strip()
        if query:
            predicate &= Q(source_id__icontains=query) | Q(search_loan_number__icontains=query) | Q(search_borrower_name__icontains=query)
        borrower = (fields.get('borrower_q') or '').strip()
        if borrower:
            predicate &= Q(search_borrower_name__icontains=borrower)
        for field, lookup in (('loan_date_from','gte'), ('loan_date_to','lte')):
            if fields.get(field):
                predicate &= Q(search_opened_on__isnull=False, **{'search_opened_on__'+lookup:fields[field].isoformat()})
        candidates = None
        if predicate:
            candidates = list(HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id).filter(predicate)
                .order_by().values_list('pk', flat=True)[:ARCHIVE_CANDIDATE_LIMIT + 1])
            if len(candidates) > ARCHIVE_CANDIDATE_LIMIT:
                candidates = None  # Complete SQL fallback, never truncated results.
        archives = unadmitted_historical_records(workspace_id, candidate_ids=candidates).filter(predicate)
        if candidates is None:
            # After admission, only a few unresolved identities usually remain.
            # Reuse their fully checked IDs instead of repeating the expensive
            # source checks in both UNION count and page. Larger pending cohorts
            # keep the complete query; this bound never truncates real results.
            pending_ids = list(archives.order_by().values_list('pk', flat=True)[:ARCHIVE_CANDIDATE_LIMIT + 1])
            if len(pending_ids) <= ARCHIVE_CANDIDATE_LIMIT:
                archives = HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id, pk__in=pending_ids)

    columns = ('directory_kind','directory_rank','directory_day','directory_at','directory_pk')
    ordinary = loans.order_by().annotate(directory_kind=Value('ordinary',output_field=CharField()),
        directory_rank=Case(When(state__in=('DRAFT','APPROVED','ACTIVE'), then=Value(0)), default=Value(1),output_field=IntegerField()),
        directory_day=Coalesce(Cast('loan_date',CharField()),Value('')),
        directory_at=F('created_at'), directory_pk=F('pk')).values(*columns)
    historical = archives.order_by().annotate(directory_kind=Value('historical',output_field=CharField()),
        directory_rank=Value(1, output_field=IntegerField()), directory_day=Coalesce('search_opened_on',Value(''),output_field=CharField()),
        directory_at=F('accepted_at'), directory_pk=F('pk')).values(*columns)
    references = ordinary.union(historical,all=True).order_by('directory_rank','-directory_day','-directory_at','directory_kind','-directory_pk')
    result = Paginator(references,25).get_page(page)
    selected = list(result.object_list)
    loan_ids = [r['directory_pk'] for r in selected if r['directory_kind']=='ordinary']
    archive_ids = [r['directory_pk'] for r in selected if r['directory_kind']=='historical']
    local = PawnLoan.objects.filter(workspace_id=workspace_id,pk__in=loan_ids).select_related('borrower','license','series').prefetch_related('series__number_sequences').in_bulk()
    retained = HistoricalLoanEvidence.objects.filter(workspace_id=workspace_id,pk__in=archive_ids).in_bulk()
    result.object_list = [dict(kind=r['directory_kind'],loan=local[r['directory_pk']]) if r['directory_kind']=='ordinary'
        else dict(kind='historical',evidence=retained[r['directory_pk']],summary=historical_loan_summary(retained[r['directory_pk']].document)) for r in selected]
    return result, bool(mapped_filters)
