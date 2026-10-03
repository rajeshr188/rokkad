"""Scoped book opening, evidence review, permanent batches and exact downloads."""
import hashlib
import uuid

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from apps.tenant_apps.loans.access import loans_workspace_required, loans_setup_required
from apps.tenant_apps.loans.documents.pledge_book import render_pledge_book
from apps.tenant_apps.loans.forms_pledge_book import BookForm, EvidenceReviewForm, BatchForm
from apps.tenant_apps.loans.models import PledgeBook, PledgeBookBatch, PledgeBookReview
from apps.tenant_apps.loans.selectors.pledge_activity import daily_activity
from apps.tenant_apps.loans.services.pledge_book import open_book, pending_report, review_entry, batch_plan, finalise_batch, authorize
from .statutory_notices import _private


def style(form):
    for field in form.fields.values():
        if not field.widget.is_hidden:
            field.widget.attrs['class'] = ('form-check-input' if isinstance(field, forms.BooleanField)
                else 'form-select' if isinstance(field, (forms.ChoiceField, forms.ModelChoiceField)) else 'form-control')
    return form


def get_book(request, pk):
    return get_object_or_404(PledgeBook.objects.select_related('workspace', 'series__license').prefetch_related('series__number_sequences'),
                           pk=pk, workspace=request.loans_workspace)


@loans_workspace_required
@require_http_methods(['GET', 'POST'])
def books(request):
    form = BookForm(request.POST if request.method == 'POST' else None, workspace=request.loans_workspace,
                    initial={'starts_on': timezone.localdate(), 'layout': 'facing_a4'})
    if request.method == 'POST':
        authorize(request.loans_workspace, request.user, write=True)
        if form.is_valid():
            try:
                book = open_book(workspace=request.loans_workspace, actor=request.user, data=request.POST)
            except (ValueError, ValidationError) as exc:
                form.add_error(None, str(exc))
            else:
                return redirect('workspace_loans:pledge_book_detail', workspace_slug=request.workspace.slug, book_pk=book.pk)
    return _private(render(request, 'loans/statutory/pledge_books.html', dict(form=style(form),
        books=PledgeBook.objects.filter(workspace=request.loans_workspace).select_related('series__license').prefetch_related('series__number_sequences'),
        can_manage=request.loans_workspace_access.can('workspace.settings.manage'))))


class QueueForm(forms.Form):
    cutoff = forms.DateField(label='Include pledges and activity through', widget=forms.DateInput(attrs={'type': 'date'}))
    mode = forms.ChoiceField(choices=[('full', 'Full pages only'), ('partial', 'Include last partial page')])


@loans_workspace_required
@require_http_methods(['GET', 'POST'])
def detail(request, book_pk):
    book = get_book(request, book_pk)
    today = timezone.localdate()
    queue = QueueForm(request.POST if request.method == 'POST' else request.GET or {'cutoff': today, 'mode': 'partial'})
    confirm, plan = None, None
    if request.method == 'POST':
        authorize(request.loans_workspace, request.user, write=True, exporting=True)
        confirm = BatchForm(request.POST)
        if confirm.is_valid():
            try:
                batch = finalise_batch(workspace=request.loans_workspace, actor=request.user, book_id=book.pk, data=request.POST)
            except (ValueError, ValidationError) as exc:
                confirm.add_error(None, str(exc))
            else:
                messages.success(request, f'Saved pages {batch.first_page}-{batch.last_page}. Download, print and file them; saving does not mark physical filing complete.')
                return redirect('workspace_loans:pledge_book_detail', workspace_slug=request.workspace.slug, book_pk=book.pk)
    if queue.is_valid():
        try:
            plan = batch_plan(book, actor=request.user, **queue.cleaned_data)
            if request.method == 'GET' and request.GET.get('format') == 'pdf':
                authorize(request.loans_workspace, request.user, exporting=True)
                return _private(HttpResponse(render_pledge_book(plan['report'], book.layout), content_type='application/pdf'))
        except ValueError as exc:
            queue.add_error(None, str(exc))
    if plan and confirm is None:
        confirm = BatchForm(initial={**queue.cleaned_data, 'review_sha256': plan['review_sha256'], 'request_key': uuid.uuid4().hex})
    return _private(render(request, 'loans/statutory/pledge_book_detail.html', dict(book=book,
        queue=style(queue), confirm=style(confirm) if confirm else None, plan=plan,
        can_manage=request.loans_workspace_access.can('workspace.settings.manage'),
        can_export=request.loans_workspace_access.can('data.export'),
        batches=Paginator(book.batches.select_related('created_by').order_by('-first_page'), 25).get_page(request.GET.get('page')))))


@loans_setup_required
@require_http_methods(['GET', 'POST'])
def review(request, book_pk, loan_pk):
    book = get_book(request, book_pk)
    report = pending_report(book, actor=request.user, cutoff=timezone.localdate())
    row = next((r for r in report.entries if r['loan_id'] == loan_pk), None)
    if not row:
        raise Http404('Entry is not in this book pending queue')
    form = EvidenceReviewForm(request.POST if request.method == 'POST' else None,
        initial={'basis_sha256': row['basis_sha256'], 'request_key': uuid.uuid4().hex})
    if request.method == 'POST' and form.is_valid():
        try:
            review_entry(workspace=request.loans_workspace, actor=request.user, book_id=book.pk, loan_id=loan_pk, data=request.POST)
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            messages.success(request, 'Source review saved. Unknown facts and original evidence remain traceable.')
            return redirect('workspace_loans:pledge_book_detail', workspace_slug=request.workspace.slug, book_pk=book.pk)
    return _private(render(request, 'loans/statutory/pledge_book_review.html', dict(book=book, row=row, form=style(form),
        history=PledgeBookReview.objects.filter(workspace=request.loans_workspace, loan_id=loan_pk).select_related('created_by').order_by('-pk'))))


@loans_workspace_required
@require_GET
def download(request, book_pk, batch_pk):
    book = get_book(request, book_pk)
    authorize(request.loans_workspace, request.user, exporting=True)
    batch = get_object_or_404(PledgeBookBatch, pk=batch_pk, book=book, workspace=request.loans_workspace)
    try:
        with batch.artifact.open('rb') as stream:
            content = stream.read()
    except (OSError, ValueError):
        raise Http404('The retained PDF is unavailable; restore the original artifact, do not regenerate it.')
    if hashlib.sha256(content).hexdigest() != batch.artifact_sha256:
        return _private(HttpResponse('Stored PDF failed its integrity check. Restore the original artifact.', status=409))
    response = HttpResponse(content, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="form-e-{book.reference}-pages-{batch.first_page}-{batch.last_page}.pdf"'
    return _private(response)


class ActivityForm(forms.Form):
    start = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    end = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))
    basis = forms.ChoiceField(choices=[('recorded', 'Date entered in Rokkad (find late entries)'), ('business', 'Actual business date')])


@loans_workspace_required
@require_GET
def activity(request, book_pk):
    book = get_book(request, book_pk)
    today = timezone.localdate()
    form = ActivityForm(request.GET or {'start': today, 'end': today, 'basis': 'recorded'})
    rows = []
    if form.is_valid():
        try:
            rows = daily_activity(book, actor=request.user, **form.cleaned_data)
        except ValueError as exc:
            form.add_error(None, str(exc))
    return _private(render(request, 'loans/statutory/pledge_book_activity.html', dict(book=book, form=style(form), rows=rows,
        selection=form.cleaned_data if form.is_valid() else {})))
