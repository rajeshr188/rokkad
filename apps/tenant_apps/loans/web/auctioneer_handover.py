"""Administrator review and manual handover; no automatic communications."""
import csv
import io

from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_GET

from apps.tenant_apps.loans.access import loans_setup_required
from apps.tenant_apps.loans.documents.display import display_date, display_money
from apps.tenant_apps.loans.models import AuctioneerHandover, AuctioneerHandoverRevision, LoanLicense
from apps.tenant_apps.loans.services import auctioneer_handover as service
from .pledge_books import style
from .statutory_notices import _private


class HandoverForm(forms.Form):
    license = forms.ModelChoiceField(queryset=LoanLicense.objects.none(), label='Licence')
    title = forms.CharField(max_length=160, label='List label', help_text='For example: October auctioneer review')
    auctioneer = forms.CharField(max_length=200, label='Intended auctioneer / firm')
    numbers = forms.CharField(max_length=10000, widget=forms.Textarea(attrs={'rows': 6}),
        label='Full loan numbers', help_text='Paste one per line or separate with commas, including prefixes and leading zeroes. Up to 100 loans per list; all must belong to this licence.')

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['license'].queryset = LoanLicense.objects.filter(workspace=workspace)


def decorated_rows(rows):
    result = []
    for row in rows:
        copy = dict(row)
        for key in ('principal', 'interest', 'fees', 'previous_principal'):
            copy[key + '_display'] = 'Not available' if row.get(key) is None else '₹' + display_money(row[key], grouping=True)
        copy['date_display'] = display_date(row['loan_date'])
        copy['due_display'] = display_date(row['due_date']) if row['due_date'] else 'Not available'
        copy['sale_display'] = display_date(row['scheduled_date']) if row['scheduled_date'] else 'Not scheduled'
        result.append(copy)
    return result


def save_post(request):
    if request.POST.get('reviewed') != 'yes':
        raise ValueError('Confirm that you reviewed the changes and remaining-loan selection.')
    return service.save_review(workspace=request.loans_workspace, actor=request.user,
        token=request.POST.get('token', ''), included_ids=request.POST.getlist('included'), notes=request.POST.get('notes', ''))


@loans_setup_required
@require_http_methods(['GET', 'POST'])
def index(request):
    workspace = request.loans_workspace
    service.authorize(workspace, request.user)
    form = HandoverForm(request.POST if request.method == 'POST' else None, workspace=workspace)
    preview, token, error = None, None, None
    if request.method == 'POST':
        try:
            if request.POST.get('action') == 'save':
                revision = save_post(request)
                return redirect('workspace_loans:auctioneer_handover_detail', workspace_slug=workspace.slug, handover_pk=revision.handover_id)
            if form.is_valid():
                data = form.cleaned_data
                ids = service.resolve_numbers(workspace, data['license'].pk, data['numbers'])
                preview = service.plan(workspace=workspace, actor=request.user, license_id=data['license'].pk,
                    loan_ids=ids, title=data['title'], auctioneer=data['auctioneer'])
                token = service.review_token(preview, request.user)
        except (ValueError, ValidationError) as exc:
            error = str(exc)
    return _private(render(request, 'loans/statutory/auctioneer_handovers.html', dict(form=style(form), error=error,
        preview=preview, token=token, rows=decorated_rows(preview['rows']) if preview else [],
        handovers=Paginator(AuctioneerHandover.objects.filter(workspace=workspace).select_related('license', 'created_by').order_by('-pk'), 25).get_page(request.GET.get('page')))))


@loans_setup_required
@require_http_methods(['GET', 'POST'])
def detail(request, handover_pk):
    workspace = request.loans_workspace
    handover = get_object_or_404(AuctioneerHandover.objects.select_related('license'), workspace=workspace, pk=handover_pk)
    service.authorize(workspace, request.user)
    error = None
    if request.method == 'POST':
        # Bind the signed confirmation to this URL as well as user and Workspace.
        from django.core import signing
        try:
            payload = signing.loads(request.POST.get('token', ''), salt=service.SALT, max_age=3600)
            if payload['handover_id'] != handover.pk:
                raise ValueError('This review belongs to another list.')
            revision = save_post(request)
            return redirect('workspace_loans:auctioneer_handover_detail', workspace_slug=workspace.slug, handover_pk=revision.handover_id)
        except (ValueError, ValidationError, signing.BadSignature) as exc:
            error = str(exc)
    preview = service.plan(workspace=workspace, actor=request.user, handover=handover)
    return _private(render(request, 'loans/statutory/auctioneer_handover_detail.html', dict(handover=handover,
        preview=preview, token=service.review_token(preview, request.user, handover), rows=decorated_rows(preview['rows']),
        error=error, revisions=Paginator(handover.revisions.select_related('created_by').order_by('-number'), 25).get_page(request.GET.get('page')))))


def csv_cell(value):
    value = str(value if value is not None else '')
    # Spreadsheet applications must never interpret borrower-supplied text as formulas.
    return "'" + value if value.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else value


@loans_setup_required
@require_GET
def export(request, handover_pk, revision_pk):
    service.authorize(request.loans_workspace, request.user, exporting=True)
    revision = get_object_or_404(AuctioneerHandoverRevision.objects.select_related('handover', 'created_by'),
        pk=revision_pk, handover_id=handover_pk, workspace=request.loans_workspace)
    if service.digest(revision.snapshot) != revision.snapshot_sha256:
        return _private(HttpResponse('Saved list failed its integrity check.', status=409))
    rows = decorated_rows(revision.snapshot['rows'])
    if request.GET.get('format') == 'csv':
        stream = io.StringIO(newline='')
        writer = csv.writer(stream)
        writer.writerow(['Administrative handover — not a statutory notice or auction permission'])
        writer.writerow(['Reference', revision.handover.reference, 'Revision', revision.number,
                         'Reviewed at', display_date(revision.created_at), 'Auctioneer', csv_cell(revision.snapshot['auctioneer'])])
        writer.writerow(['Loan', 'Loan date', 'Licence', 'Series', 'Borrower', 'Relation', 'Current default address', 'Contact',
            'State', 'Recorded principal INR', 'Recorded interest INR', 'Recorded fees INR', 'Articles / custody', 'Scheduled sale', 'Readiness checks'])
        for row in rows:
            if not row['included']:
                continue
            articles = '; '.join(f"{i['description']} ({i['metal']}, qty {i['quantity'] if i['quantity'] is not None else 'unknown'}, gross {i['gross'] or 'unknown'} g, net {i['net']} g, {i['custody']})" for i in row['items'])
            writer.writerow([csv_cell(v) for v in (row['number'], row['date_display'], row['license'], row['series'],
                row['borrower'], row['relation'], row['address'], row['phone'], row['state'], row['principal'], row['interest'], row['fees'],
                articles, row['sale_display'], '; '.join(row['readiness']) or 'Recorded checks clear as of review; recheck before sale')])
        response = HttpResponse('\ufeff' + stream.getvalue(), content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{revision.handover.reference}-v{revision.number}.csv"'
        return _private(response)
    return _private(render(request, 'loans/statutory/auctioneer_handover_print.html', dict(revision=revision,
        snapshot=revision.snapshot, rows=[r for r in rows if r['included']],
        excluded=[r for r in rows if not r['included']], as_of_display=display_date(revision.snapshot['as_of']))))
