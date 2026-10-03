"""Workspace-scoped manual statutory notice screens and private downloads."""
import hashlib
import uuid

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from apps.tenant_apps.loans.access import loans_setup_required, loans_workspace_required
from apps.tenant_apps.loans.forms_statutory import CatalogueForm, FORMS
from apps.tenant_apps.loans.documents.display import display_date
from apps.tenant_apps.loans.models import PawnLoanAuction
from apps.tenant_apps.loans.models.statutory import StatutoryAuctionNotice, StatutoryNoticeEvidence
from apps.tenant_apps.loans.services.statutory_notices import (
    StatutoryNoticeError, auction_readiness, prepare_catalogue, record_handling,
)


def _auction(request, pk):
    return get_object_or_404(PawnLoanAuction.objects.select_related('loan__borrower', 'loan__license', 'workspace'),
        pk=pk, workspace=request.loans_workspace)


def _private(response):
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


def _style(form):
    for field in form.fields.values():
        if not field.widget.is_hidden:
            field.widget.attrs['class'] = 'form-check-input' if getattr(field.widget, 'input_type', '') == 'checkbox' else 'form-control'
    return form


@loans_workspace_required
@require_GET
def guide(request):
    return _private(render(request, 'loans/statutory/guide.html'))


@loans_setup_required
@require_http_methods(['GET', 'POST'])
def detail(request, auction_pk):
    auction = _auction(request, auction_pk)
    notice = StatutoryAuctionNotice.objects.filter(auction=auction).first()
    kind = request.POST.get('kind') if request.method == 'POST' else request.GET.get('step', '')
    if kind and kind not in FORMS:
        raise Http404('Unknown handling step')
    if kind and not notice:
        raise Http404('Prepare the catalogue first')
    initial = {'request_key': uuid.uuid4().hex, 'occurred_on': timezone.localdate()}
    if not notice:
        licence = auction.loan.license
        address = auction.loan.borrower.addresses.order_by('-is_default', 'pk').first()
        initial.update(business_name=licence.business_name or licence.name,
            business_address=licence.business_address, borrower_address=str(address) if address else '')
    form_type = FORMS.get(kind, CatalogueForm)
    form = form_type(request.POST if request.method == 'POST' else None, request.FILES or None, initial=initial)
    if request.method == 'POST' and form.is_valid():
        try:
            if not kind:
                result = prepare_catalogue(auction.pk, data=request.POST, actor=request.user, preview=request.POST.get('operation') == 'preview')
                if isinstance(result, bytes):
                    return _private(HttpResponse(result, content_type='application/pdf'))
            else:
                record_handling(auction.pk, kind=kind, data=request.POST, attachment=request.FILES.get('attachment'), actor=request.user)
        except (StatutoryNoticeError, ValidationError, ValueError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, 'Statutory notice evidence saved. No email, WhatsApp message or postal booking was sent.')
            return redirect('workspace_loans:statutory_auction_notice', workspace_slug=request.workspace.slug, auction_pk=auction.pk)
    readiness = auction_readiness(auction)
    events = list(notice.evidence.select_related('created_by')) if notice else []
    for event in events:
        fields = FORMS[event.kind].base_fields
        event.display_details = [(fields[key].label or key.replace('_', ' ').title(),
            ('Yes' if value else 'No') if isinstance(value, bool) else display_date(value))
            for key, value in event.details.items() if key in fields and key != 'notes']
    recorded = {event.kind for event in events}
    steps = []
    if notice and 'WITHDRAWN' not in recorded and auction.state in {'INITIATED', 'IN_PROGRESS'}:
        for value, label in StatutoryNoticeEvidence.Kind.choices:
            if value not in recorded or value == 'REVIEWED':
                prerequisite = {'POSTED': 'PRINTED', 'ACKNOWLEDGED': 'POSTED', 'RETURNED': 'POSTED', 'REFERRED': 'RETURNED', 'OFFICER_RECEIVED': 'REFERRED', 'CERTIFIED': 'OFFICER_RECEIVED'}
                if value in prerequisite and prerequisite[value] not in recorded:
                    continue
                if value == 'ACKNOWLEDGED' and 'RETURNED' in recorded:
                    continue
                steps.append((value, label))
    response = render(request, 'loans/statutory/auction_notice.html', {
        'auction': auction, 'loan': auction.loan, 'notice': notice,
        'form': _style(form) if not notice or kind else None, 'kind': kind,
        'step_title': StatutoryNoticeEvidence.Kind(kind).label if kind else 'Prepare the auction catalogue',
        'steps': steps, 'events': events, 'readiness': readiness,
    })
    return _private(response)


@loans_setup_required
@require_GET
def download(request, auction_pk, evidence_pk=None):
    auction = _auction(request, auction_pk)
    notice = get_object_or_404(StatutoryAuctionNotice, auction=auction, workspace=request.loans_workspace)
    if evidence_pk:
        row = get_object_or_404(StatutoryNoticeEvidence, pk=evidence_pk, notice=notice, workspace=request.loans_workspace)
        field, digest = row.attachment, row.attachment_sha256
    else:
        field, digest = notice.artifact, notice.artifact_sha256
    if not field:
        raise Http404('No attachment')
    try:
        with field.open('rb') as handle:
            content = handle.read()
    except (OSError, ValueError):
        raise Http404('Stored evidence is unavailable')
    if hashlib.sha256(content).hexdigest() != digest:
        return _private(HttpResponse('Stored evidence failed its integrity check.', status=409))
    extension = field.name.rsplit('.', 1)[-1].lower()
    response = HttpResponse(content, content_type={'pdf': 'application/pdf', 'png': 'image/png', 'jpg': 'image/jpeg'}.get(extension, 'application/octet-stream'))
    response['Content-Disposition'] = f'inline; filename="statutory-{notice.pk}-{evidence_pk or "catalogue"}.{extension}"'
    return _private(response)
