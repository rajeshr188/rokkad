from uuid import uuid4
from django import forms
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods
from apps.tenant_apps.loans import models as m
from apps.tenant_apps.loans.access import loans_action_required
from apps.tenant_apps.loans.services.paper_backlog import record_backlog_checkpoint
from apps.tenant_apps.loans.services.batch_transaction_reviews import preview_batch_transaction_review, confirm_batch_transaction_review
from .recorded_history import _style
from .transaction_reviews import TransactionReviewForm


class BacklogForm(forms.Form):
    book_reference = forms.CharField(max_length=160, label="Paper book reference")
    through_date = forms.DateField(label="Book activity through", widget=forms.DateInput(attrs={"type": "date"}))
    last_page_reference = forms.CharField(max_length=160, label="Last page checked / entered")
    state = forms.ChoiceField(choices=m.PaperBacklogCheckpoint._meta.get_field("state").choices, label="Progress")
    note = forms.CharField(max_length=500, required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Missing pages or other progress notes")
    request_key = forms.CharField(max_length=120, widget=forms.HiddenInput)


@loans_action_required("data.edit")
@never_cache
@require_http_methods(["GET", "POST"])
def backlog(request):
    form = BacklogForm(request.POST if request.method == "POST" else None,
        initial=dict(through_date=timezone.localdate(), request_key=uuid4().hex))
    _style(form)
    if request.method == "POST" and form.is_valid():
        try:
            _, created = record_backlog_checkpoint(workspace=request.loans_workspace, actor=request.user, **form.cleaned_data)
            messages.success(request, "Paper-book progress recorded." if created else "This progress was already recorded.")
            return redirect("workspace_loans:paper_backlog", workspace_slug=request.workspace.slug)
        except ValueError as exc:
            form.add_error(None, str(exc))
    checkpoints = m.PaperBacklogCheckpoint.objects.filter(workspace=request.loans_workspace).select_related("recorded_by")[:100]
    from apps.orgs.access import resolve_workspace_access
    access = resolve_workspace_access(actor=request.user, workspace=request.loans_workspace)
    return render(request, "loans/pawn/paper_backlog.html", dict(form=form, checkpoints=checkpoints,
        can_export_recovery=access.can("data.export")))


class BatchReviewForm(TransactionReviewForm):
    numbers = forms.CharField(max_length=4000, label="Loan numbers (one per line)", widget=forms.Textarea(attrs={"rows": 6}),
        help_text="Enter at most 50 numbers. If a number exists in multiple series, review those loans individually.")


def _selected(workspace, numbers):
    from apps.tenant_apps.loans.services.recorded_numbers import identity
    requested = [line.strip() for line in numbers.splitlines() if line.strip()]
    if not 1 <= len(requested) <= 50 or len({identity(number) for number in requested}) != len(requested):
        raise ValueError("Enter one to fifty distinct loan numbers.")
    # Bounded exact-number lookup; preserve series ambiguity instead of guessing.
    selected = []
    for number in requested:
        rows = list(m.PawnLoan.objects.filter(workspace=workspace, loan_number=number).values_list("pk", flat=True)[:2])
        if len(rows) != 1:
            raise ValueError(f"Loan {number} is missing or occurs in multiple series. Open its individual record.")
        selected.append(rows[0])
    return selected


@loans_action_required("data.edit")
@never_cache
@require_http_methods(["GET", "POST"])
def batch_review(request):
    form = BatchReviewForm(request.POST if request.method == "POST" else None,
        initial=dict(through_date=timezone.localdate(), request_key=uuid4().hex))
    _style(form)
    review = None
    if request.method == "POST" and form.is_valid():
        try:
            data = dict(form.cleaned_data)
            selected = _selected(request.loans_workspace, data.pop("numbers"))
            token, acknowledged = data.pop("review_token"), data.pop("acknowledged")
            if request.POST.get("action") == "confirm":
                result = confirm_batch_transaction_review(selected, actor=request.user, **data, review_token=token, acknowledged=acknowledged)
                messages.success(request, f"Reviewed {len(result)} loans; {sum(created for _, created in result)} new confirmations recorded.")
                return redirect("workspace_loans:paper_backlog", workspace_slug=request.workspace.slug)
            review, token = preview_batch_transaction_review(selected, actor=request.user, **data)
            form.data = form.data.copy()
            form.data["review_token"] = token
        except (ValueError, ObjectDoesNotExist) as exc:
            form.add_error(None, str(exc))
    return render(request, "loans/pawn/batch_transaction_review.html", dict(form=form, review=review))


@loans_action_required("data.export")
@never_cache
@require_http_methods(["GET", "POST"])
def recovery_backup(request):
    from django.http import HttpResponse
    from hashlib import sha256
    from apps.tenant_apps.loans.services.pawn_recovery import export_archive
    error = ""
    if request.method == "POST":
        try:
            content = export_archive(workspace=request.loans_workspace, actor=request.user)
        except (ValueError, OSError) as exc:
            error = str(exc)
        else:
            response = HttpResponse(content, content_type="application/zip")
            checksum = sha256(content).hexdigest()
            response["Content-Disposition"] = f'attachment; filename="ordinary-loans-{checksum}.zip"'
            response["X-Rokkad-Archive-SHA256"] = checksum
            return response
    return render(request, "loans/pawn/recovery_backup.html", dict(error=error))
