"""Authorized downloads of immutable original source copies."""
import base64

from django.http import Http404, HttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.cache import never_cache

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.services.servicing_bundle_contract import sha
from .pawn_read_helpers import _pawn_loan_for_workspace


def source_copies(loan):
    if not hasattr(loan, 'historical_import'):
        return []
    packet = loan.historical_import.references.get('portable')
    if not packet:
        return []
    from apps.tenant_apps.loans.services.servicing_bundle import _loan_for
    copies = []
    for _ in range(8):
        root = packet['source_loan_id']
        tables = packet['document']['tables']
        for doc in packet['document']['documents']:
            kind = 'PawnLoanAuction' if doc['source_type'] == 'PawnLoanAuctionNotice' else doc['source_type']
            row = next((r for r in tables.get(kind, []) if str(r['id']) == doc['source_id']), None)
            if row and _loan_for(kind, row, tables) == root:
                copies.append(dict(index=len(copies), **doc, retained_files=packet['files']))
        origin = next((r for r in tables['HistoricalLoanImport'] if r['loan_id'] == root), None)
        packet = origin['references'].get('portable') if origin else None
        if not packet:
            break
    else:
        raise ValueError('Source document ancestry exceeds eight transfers.')
    return copies


@loans_workspace_required
@never_cache
@require_GET
def source_document(request, pk, index):
    loan = _pawn_loan_for_workspace(request, pk)
    doc = next((r for r in source_copies(loan) if r['index'] == index), None)
    if doc is None:
        raise Http404('Source document is unavailable for this loan.')
    data = base64.b64decode(doc['retained_files'][doc['pdf_sha256']], validate=True)
    if sha(data) != doc['pdf_sha256']:
        return HttpResponse('Retained source document checksum differs.', status=409, content_type='text/plain')
    response = HttpResponse(data, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="source-copy-{index}.pdf"'
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response
