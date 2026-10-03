import uuid

from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import KhataAccount, KhataCollateralItem
from apps.tenant_apps.loans.selectors.khata import held_items
from apps.tenant_apps.loans.selectors.khata_items import collateral_items, filter_items
from apps.tenant_apps.loans.services.action_access import require_workspace_action
from apps.tenant_apps.loans.services.khata_labels import issue_labels
from .khata_forms import StyledForm
from .khata_views import _private


class ItemSelectionField(forms.Field):
    widget = forms.SelectMultiple

    def clean(self, value):
        values = value or []
        if len(values) > 100:
            raise ValidationError("Select at most 100 items per batch.")
        try:
            ids = [int(v) for v in values]
        except (ValueError, TypeError):
            raise ValidationError("Choose valid item numbers.")
        if any(i <= 0 for i in ids) or len(set(ids)) != len(ids):
            raise ValidationError("Choose distinct item numbers.")
        return ids


class LabelForm(StyledForm):
    mode = forms.ChoiceField(label="Print layout", choices=(("SELECTED", "One label per selected item (up to 100)"),
        ("ALL", "One combined label for all held collateral"),
        ("EACH", "One label per held item (multiple pages)"), ("ONE", "One selected held item")))
    item = forms.ModelChoiceField(label="Item (only for one selected item)", required=False, queryset=KhataCollateralItem.objects.none())
    items = ItemSelectionField(required=False)

    def __init__(self, *args, account, page_ids, **kwargs):
        super().__init__(*args, **kwargs)
        ids = list(page_ids)
        if self.is_bound and str(self.data.get("item", "")).isdecimal():
            ids.append(int(self.data["item"]))
        self.fields["item"].queryset = account.collateral.filter(pk__in=ids).order_by("pk")
        self.style()

    def clean(self):
        data = super().clean()
        if data.get("mode") == "ONE" and not data.get("item"):
            self.add_error("item", "Choose a held collateral item.")
        elif data.get("mode") in ("ALL", "EACH") and data.get("item"):
            self.add_error("item", "Clear the item selection to label all held collateral.")
        if data.get("mode") == "SELECTED":
            if not data.get("items"):
                self.add_error("items", "Select at least one held item or print the displayed batch.")
            if data.get("item"):
                self.add_error("item", "Clear the single-item selection to print a selected batch.")
        elif data.get("items"):
            self.add_error("items", "Clear the checkboxes or choose the selected-item layout.")
        return data


@loans_workspace_required
@never_cache
@require_http_methods(["GET", "POST"])
def labels(request, pk):
    workspace = request.loans_workspace
    account = get_object_or_404(KhataAccount, workspace=workspace, pk=pk)
    require_workspace_action(workspace, request.user, "data.edit", "data.export")
    q = request.GET.get("q", "").strip()[:120]
    items = filter_items(collateral_items(account, mode="held"), {"q": q}).order_by("pk")
    page = Paginator(items, 100).get_page(request.GET.get("page"))
    page_ids = [item.pk for item in page]
    data = request.POST.copy() if request.method == "POST" else None
    if data is not None and data.get("print_page") == "1":
        data["mode"] = "SELECTED"
        data["item"] = ""
        data.setlist("items", data.getlist("page_items"))
    form = LabelForm(data, account=account, page_ids=page_ids,
        initial=dict(request_key=uuid.uuid4(), mode="SELECTED"))
    if request.method == "POST" and form.is_valid():
        try:
            item = form.cleaned_data["item"]
            issue = issue_labels(workspace=workspace, actor=request.user, account_id=pk,
                request_key=form.cleaned_data["request_key"], mode=form.cleaned_data["mode"],
                item_id=item.pk if item else None, item_ids=form.cleaned_data["items"],
                origin=request.build_absolute_uri("/").rstrip("/"))
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
        else:
            return redirect("workspace_loans:khata_document", workspace_slug=workspace.slug, pk=pk, issue_pk=issue.pk)
    selected = {str(i) for i in data.getlist("items")} if data is not None else set()
    rows = [dict(item=item, selected=str(item.pk) in selected) for item in page]
    return _private(render(request, "loans/khata/labels.html", dict(account=account, form=form,
        item_page=page, rows=rows, q=q, held_count=held_items(account).count())))


@loans_workspace_required
@never_cache
@require_GET
def item_scan(request, public_id):
    item = get_object_or_404(KhataCollateralItem, workspace=request.loans_workspace, public_id=public_id)
    target = reverse("workspace_loans:khata_detail", kwargs=dict(workspace_slug=request.loans_workspace.slug, pk=item.account_id))
    return _private(redirect(target + "?section=collateral&item=" + str(item.public_id) + "#collateral-item-" + str(item.public_id)))


@loans_workspace_required
@never_cache
@require_GET
def account_scan(request, public_id):
    account = get_object_or_404(KhataAccount, workspace=request.loans_workspace, public_id=public_id)
    target = reverse("workspace_loans:khata_detail", kwargs=dict(workspace_slug=request.loans_workspace.slug, pk=account.pk))
    return _private(redirect(target + "?section=collateral#collateral-custody"))


@loans_workspace_required
@never_cache
@require_GET
def readiness(request):
    from apps.tenant_apps.loans.services.khata_readiness import assess_readiness
    report = assess_readiness(workspace=request.loans_workspace, actor=request.user)
    return _private(render(request, "loans/khata/readiness.html", dict(report=report)))
