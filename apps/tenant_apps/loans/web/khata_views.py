"""Scoped read-only khata register/detail and private document issuance."""
import uuid
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.http import HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import KhataDocumentIssue, KhataSeries, KhataCollateralPhoto, KhataOperation, KhataAccount
from apps.tenant_apps.loans.selectors.khata_history import history_operations
from apps.tenant_apps.loans.selectors.khata_collections import collection_rows, recorded_exchange_warnings
from apps.tenant_apps.loans.selectors.khata_events import event_operations, event_details
from apps.tenant_apps.loans.selectors.khata_items import collateral_items
from apps.tenant_apps.loans.selectors.khata_documents import saved_documents
from apps.tenant_apps.loans.selectors.khata_summary import summary_accounts, account_summary, portfolio_summary, collateral_cover
from apps.tenant_apps.loans.services.khata_documents import issue_document, document_bytes, TITLES
from apps.tenant_apps.loans.services.action_access import require_workspace_action


class RegisterForm(forms.Form):
    q = forms.CharField(required=False, max_length=120, label="Number or borrower")
    state = forms.ChoiceField(required=False, choices=(("", "All states"), ("ACTIVE", "Active"),
        ("DRAFT", "Draft"), ("APPROVED", "Approved"), ("SETTLED_RETURN_PENDING", "Settled, return pending"),
        ("CLOSED", "Closed"), ("CANCELLED", "Cancelled")))
    attention = forms.ChoiceField(required=False, choices=(("", "All accounts"), ("due", "Interest due"),
        ("overdue", "Interest overdue"), ("returns", "Returns pending")))
    association = forms.ChoiceField(required=False, choices=(("", "Any association"),
        ("independent", "No licence associated"), ("associated", "Licence associated")))
    series = forms.ModelChoiceField(required=False, queryset=KhataSeries.objects.none())
    borrower = forms.IntegerField(required=False, min_value=1, widget=forms.HiddenInput())
    sort = forms.ChoiceField(required=False, choices=(("newest", "Newest first"), ("oldest", "Oldest first")))

    def __init__(self, *args, workspace, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["series"].queryset = KhataSeries.objects.filter(workspace=workspace).order_by("name")
        for field in self.fields.values():
            if not field.widget.is_hidden:
                field.widget.attrs["class"] = "form-select" if isinstance(field, forms.ChoiceField) else "form-control"


class DocumentForm(forms.Form):
    request_key = forms.UUIDField(widget=forms.HiddenInput())
    source = forms.ChoiceField(label="Document", choices=())

    def __init__(self, *args, account, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("statement", "Today's dated statement")]
        has_terms = False
        for op in account.operations.only("pk", "account_id", "kind", "business_date", "agreement_id", "sequence").order_by("sequence"):
            if op.kind in ("APPROVE", "WITHDRAW", "REVISE"):
                has_terms = True
            if op.kind in TITLES and (has_terms or op.agreement_id):
                choices.append((str(op.pk), f"{op.business_date} - {TITLES[op.kind]} / operation {op.pk}"))
        self.fields["source"].choices = choices
        self.fields["source"].widget.attrs["class"] = "form-select"


class CollectionForm(RegisterForm):
    status = forms.ChoiceField(label="Collection status", required=False, choices=(
        ("attention", "Due, overdue and upcoming"), ("overdue", "Overdue"),
        ("due", "Due today, no older arrears"), ("upcoming", "Upcoming, no arrears"), ("all", "All active accounts")))
    horizon = forms.TypedChoiceField(label="Upcoming window", required=False, coerce=int, empty_value=7,
        choices=((7, "Next 7 days"), (30, "Next 30 days"), (90, "Next 90 days")))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("state", "attention", "sort"):
            self.fields.pop(name)


class HistoryForm(forms.Form):
    kind = forms.ChoiceField(label="Event type", required=False, choices=(("", "All events"), *KhataOperation.Kind.choices))
    q = forms.CharField(label="Item ID, UUID, description or payment reference", required=False, max_length=160)
    operation = forms.IntegerField(label="Operation ID", required=False, min_value=1, max_value=2**63 - 1)
    from_date = forms.DateField(label="Business date from", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    to_date = forms.DateField(label="Business date through", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    sort = forms.ChoiceField(label="Date order", required=False, choices=(("newest", "Newest first"), ("oldest", "Oldest first")))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, prefix="history", **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean(self):
        data = super().clean()
        if data.get("from_date") and data.get("to_date") and data["from_date"] > data["to_date"]:
            self.add_error("to_date", "Through date must be on or after the from date.")
        return data


class SavedDocumentForm(forms.Form):
    q = forms.CharField(label="Title, payment reference, issue/source/item ID or label UUID", required=False, max_length=160)
    kind = forms.ChoiceField(label="Document type", required=False, choices=(("", "All documents"), *KhataDocumentIssue._meta.get_field("kind").choices))
    from_date = forms.DateField(label="Document date from", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    to_date = forms.DateField(label="Document date through", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    sort = forms.ChoiceField(label="Issued order", required=False, choices=(("newest", "Newest first"), ("oldest", "Oldest first")))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, prefix="documents", **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean(self):
        data = super().clean()
        if data.get("from_date") and data.get("to_date") and data["from_date"] > data["to_date"]:
            self.add_error("to_date", "Through date must be on or after the from date.")
        return data


def _documents_context(request, account):
    form = SavedDocumentForm(request.GET)
    issues = saved_documents(account, form.cleaned_data) if form.is_valid() else account.document_issues.none()
    page = Paginator(issues, 25).get_page(request.GET.get("documents-page"))
    params = QueryDict(mutable=True)
    params["tab"] = "documents"
    for name in form.fields:
        key = form.add_prefix(name)
        if request.GET.get(key):
            params[key] = request.GET[key]
    return dict(documents_form=form, documents_page=page, issues=page, documents_query=params.urlencode())


def _history_context(request, account):
    form = HistoryForm(request.GET)
    operations = history_operations(account, form.cleaned_data) if form.is_valid() else account.operations.none()
    page = Paginator(operations, 25).get_page(request.GET.get("history-page"))
    guidance = None
    if form.is_valid() and form.cleaned_data.get("operation"):
        source = next(iter(page.object_list), None)
        if source is not None:
            from apps.tenant_apps.loans.services.khata_corrections import correction_guidance
            guidance = correction_guidance(account, source)
    params = QueryDict(mutable=True)
    params["section"] = "history"
    for name in form.fields:
        key = form.add_prefix(name)
        if request.GET.get(key):
            params[key] = request.GET[key]
    return dict(history_form=form, history_page=page, history_query=params.urlencode(),
        correction_guidance=guidance,
        open_history=request.GET.get("section") == "history" or any(key.startswith("history-") for key in request.GET))


def _private(response):
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response


def _detail_tab(request, form=None):
    if form is not None and form.errors:
        return "documents"
    if request.GET.get("section") in ("collateral", "history"):
        return request.GET["section"]
    tab = request.GET.get("tab")
    if tab in ("overview", "actions", "collateral", "interest", "history", "documents"):
        return tab
    if any(key.startswith("history-") for key in request.GET):
        return "history"
    if any(key.startswith("documents-") for key in request.GET):
        return "documents"
    return "overview"


def _action_groups(actions):
    labels = dict(actions)
    groups = (("Agreement & opening", ("proposal", "approve", "approve-change", "activate-change")),
        ("Collateral", ("deposit", "photo", "exchange", "handover", "return-unopened")),
        ("Withdrawals & interest", ("withdraw", "interest", "finalize")),
        ("Settlement & corrections", ("settle", "cancel", "correct")))
    return [(heading, [(name, labels[name]) for name in names if name in labels])
        for heading, names in groups if any(name in labels for name in names)]


@loans_workspace_required
@never_cache
@require_GET
def index(request):
    workspace = request.loans_workspace
    form = RegisterForm(request.GET, workspace=workspace)
    rows = []
    if form.is_valid():
        data = form.cleaned_data
        rows = portfolio_summary(workspace=workspace, filters=data)["rows"]
        attention = {"due": "due_interest", "overdue": "overdue_interest", "returns": "pending_returns"}.get(data["attention"])
        if attention:
            rows = [r for r in rows if r.get(attention, 0) > 0 or r.get("unavailable")]
        rows.sort(key=lambda r: (r["account"].opened_on or timezone.localdate(r["account"].created_at), r["account"].pk), reverse=data["sort"] != "oldest")
    else:
        rows = []
    unavailable = any(r.get("unavailable") for r in rows)
    totals = {key: None if unavailable else sum((r.get(key, Decimal(0)) for r in rows), Decimal(0))
        for key in ("principal", "interest", "due_interest", "overdue_interest")}
    page = Paginator(rows, 25).get_page(request.GET.get("page"))
    params = request.GET.copy()
    params.pop("page", None)
    return _private(render(request, "loans/khata/list.html", dict(form=form, page=page,
        totals=totals, total_count=len(rows), query=params.urlencode(), unavailable=unavailable,
        can_export=request.loans_workspace_access.can("data.export"),
        can_create=request.loans_workspace_access.can("data.create"),
        can_setup=request.loans_workspace_access.can("workspace.settings.manage"))))


@loans_workspace_required
@never_cache
@require_GET
def collections(request):
    workspace = request.loans_workspace
    form = CollectionForm(request.GET, workspace=workspace)
    rows = collection_rows(workspace=workspace, filters=form.cleaned_data,
        status=form.cleaned_data["status"] or "attention", horizon=form.cleaned_data["horizon"]) if form.is_valid() else []
    unavailable = any(r.get("unavailable") for r in rows)
    totals = {key: None if unavailable else sum((r[key] for r in rows), Decimal(0))
        for key in ("due_interest", "overdue_interest")}
    page = Paginator(rows, 25).get_page(request.GET.get("page"))
    warnings = recorded_exchange_warnings(workspace=workspace, account_ids=[r["account"].pk for r in page])
    for row in page:
        row["cover"] = collateral_cover(row["account"], row)
        row["recorded_warning"] = warnings.get(row["account"].pk)
    params = request.GET.copy()
    params.pop("page", None)
    return _private(render(request, "loans/khata/collections.html", dict(form=form, page=page, query=params.urlencode(),
        totals=totals, unavailable=unavailable, as_of=timezone.localdate(),
        can_receive=request.loans_workspace_access.can("loan.repay"))))


@loans_workspace_required
@never_cache
@require_GET
def event(request, pk, operation_pk):
    account = get_object_or_404(KhataAccount.objects.select_related("borrower", "series"), workspace=request.loans_workspace, pk=pk)
    operation = get_object_or_404(event_operations(account), pk=operation_pk)
    return _private(render(request, "loans/khata/event.html", dict(account=account, **event_details(operation))))


@loans_workspace_required
@never_cache
@require_http_methods(["GET", "POST"])
def detail(request, pk):
    workspace = request.loans_workspace
    account = get_object_or_404(KhataAccount.objects.select_related("workspace", "borrower", "series__license"), workspace=workspace, pk=pk)
    # Resolve the panel before constructing any source choices or financial/custody graph.
    form = None
    tab = _detail_tab(request)
    if request.method == "POST" or tab == "documents":
        form = DocumentForm(request.POST if request.method == "POST" else None, account=account,
            initial=dict(request_key=uuid.uuid4(), source="statement"))
    if request.method == "POST":
        require_workspace_action(workspace, request.user, "data.edit")
        require_workspace_action(workspace, request.user, "data.export")
        if form.is_valid():
            try:
                issue = issue_document(workspace=workspace, actor=request.user, account_id=pk,
                    request_key=form.cleaned_data["request_key"],
                    source_operation_id=None if form.cleaned_data["source"] == "statement" else int(form.cleaned_data["source"]))
            except (ValueError, ValidationError) as exc:
                form.add_error(None, str(exc))
            else:
                return redirect("workspace_loans:khata_document", workspace_slug=workspace.slug, pk=pk, issue_pk=issue.pk)
        tab = "documents"
    from .khata_workflows import action_links
    actions = action_links(request, account)
    context = dict(account=account, actions=actions, action_groups=_action_groups(actions), active_tab=tab,
        can_review_correction=request.loans_workspace_access.can("workspace.settings.manage"),
        exchange_recorded=account.operations.filter(pk=request.GET.get("exchange"), kind="EXCHANGE").first()
            if request.GET.get("exchange", "").isdecimal() and len(request.GET["exchange"]) <= 18 else None,
        can_export=request.loans_workspace_access.can("data.export"),
        can_issue=request.loans_workspace_access.can("data.edit") and request.loans_workspace_access.can("data.export"))
    if tab in ("overview", "interest", "actions"):
        account = summary_accounts(workspace=workspace, balances_only=True).get(pk=pk)
        context["account"] = account
        try:
            context["summary"] = account_summary(account)
        except (ValueError, ArithmeticError, TypeError):
            context["summary"] = dict(unavailable=True)
        if tab == "overview":
            context["cover"] = collateral_cover(account, context["summary"])
    elif tab == "history":
        context.update(_history_context(request, account))
    elif tab == "collateral":
        items = collateral_items(account).order_by("pk")
        selected = request.GET.get("item", "")
        if selected:
            try:
                items = items.filter(public_id=uuid.UUID(selected))
            except ValueError:
                items = items.none()
        page = Paginator(items, 25).get_page(request.GET.get("collateral-page"))
        context.update(custody_page=page, selected_item=selected,
            items=[dict(item=item, photo_id=item.photo_pk,
                status={"held": "Held", "pending": "Awaiting handover", "returned": "Returned"}[item.custody]) for item in page])
    elif tab == "documents":
        context.update(form=form,
            photos=KhataCollateralPhoto.objects.filter(workspace=workspace, item__account=account).select_related("item").order_by("-pk")[:25])
        context.update(_documents_context(request, account))
    from apps.tenant_apps.loans.selectors.khata_workflow import workflow_state
    workflow = workflow_state(context["account"], summary=context.get("summary"), actor=request.user if tab == "actions" else None)
    actions = action_links(request, context["account"], workflow)
    context.update(workflow=workflow, actions=actions, action_groups=_action_groups(actions),
        suggested_action=next(((name, label) for name in workflow["suggested"] for key, label in actions if name == key), None))
    return _private(render(request, "loans/khata/detail.html", context))


@loans_workspace_required
@never_cache
@require_GET
def download(request, pk, issue_pk):
    get_object_or_404(KhataDocumentIssue, workspace=request.loans_workspace, account_id=pk, pk=issue_pk)
    try:
        issue, content = document_bytes(workspace=request.loans_workspace, actor=request.user, account_id=pk, issue_id=issue_pk)
    except (ValueError, OSError) as exc:
        return _private(HttpResponse(str(exc), status=409, content_type="text/plain"))
    response = HttpResponse(content, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="khata-{issue.request_key}.pdf"'
    return _private(response)
