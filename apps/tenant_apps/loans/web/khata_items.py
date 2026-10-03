"""Read-only collateral browser and bounded exchange search responses."""
from django import forms
from django.core.paginator import Paginator
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import KhataAccount
from apps.tenant_apps.loans.selectors.khata_items import collateral_items, filter_items, suggested_values
from .khata_views import _private


class CollateralSearchForm(forms.Form):
    q = forms.CharField(label="Item ID, UUID, description or storage", required=False, max_length=160)
    metal = forms.ChoiceField(required=False, choices=(("", "All metals"), ("GOLD", "Gold"), ("SILVER", "Silver")))
    custody = forms.ChoiceField(required=False, choices=(("", "All custody"), ("held", "Held"), ("pending", "Return pending"), ("returned", "Returned")))
    from_date = forms.DateField(label="Received from", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    to_date = forms.DateField(label="Received through", required=False, widget=forms.DateInput(attrs={"type": "date"}))
    sort = forms.ChoiceField(required=False, choices=(("newest", "Newest received first"), ("oldest", "Oldest received first")))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-select" if isinstance(field.widget, forms.Select) else "form-control"

    def clean(self):
        data = super().clean()
        if data.get("from_date") and data.get("to_date") and data["from_date"] > data["to_date"]:
            self.add_error("to_date", "Received-through date must be on or after received-from date.")
        return data


def item_rows(account, items):
    items = list(items)
    values = suggested_values(account, items)
    return [dict(id=i.pk, uuid=str(i.public_id), description=i.description, metal=i.get_metal_display(),
        quantity=i.quantity, gross=str(i.gross_weight), net=str(i.net_weight), purity=str(i.purity),
        storage=i.storage_reference, received=i.received_operation.business_date.isoformat(),
        custody={"held": "Held", "pending": "Return pending", "returned": "Returned"}[i.custody],
        parent=i.reservation_id if i.custody == "pending" else None,
        value=str(values[i.pk]) if values[i.pk] is not None else None,
        photo=reverse("workspace_loans:khata_photo", args=(account.workspace.slug, account.pk, i.photo_pk)) if i.photo_pk else None,
        thumbnail=reverse("workspace_loans:khata_photo", args=(account.workspace.slug, account.pk, i.photo_pk)) + "?thumbnail=1" if i.photo_pk else None,
        scan=reverse("workspace_loans:khata_item_scan", args=(account.workspace.slug, i.public_id))) for i in items]


@loans_workspace_required
@never_cache
@require_GET
def browse(request, pk):
    account = get_object_or_404(KhataAccount, workspace=request.loans_workspace, pk=pk)
    mode = request.GET.get("mode", "browse")
    if mode not in ("browse", "outgoing", "incoming", "held", "pending"):
        raise Http404
    form = CollateralSearchForm(request.GET)
    if not form.is_valid():
        if request.GET.get("format") == "json":
            return _private(JsonResponse({"error": "Check search filters.", "fields": form.errors.get_json_data()}, status=400))
        items = collateral_items(account).none()
    else:
        items = filter_items(collateral_items(account, mode=mode), form.cleaned_data)
    page = Paginator(items, 25).get_page(request.GET.get("page"))
    rows = item_rows(account, page.object_list)
    if request.GET.get("format") == "json":
        return _private(JsonResponse(dict(items=rows, page=page.number, pages=page.paginator.num_pages,
            count=page.paginator.count, next=page.has_next(), previous=page.has_previous())))
    params = request.GET.copy()
    params.pop("page", None)
    from .khata_workflows import action_links
    actions = {name for name, label in action_links(request, account)}
    return _private(render(request, "loans/khata/collateral.html", dict(account=account,
        form=form, page=page, rows=rows, query=params.urlencode(),
        mode=mode, can_handover="handover" in actions, can_photo="photo" in actions,
        received=account.collateral.filter(pk=request.GET.get("received")).first()
            if request.GET.get("received", "").isdecimal() and len(request.GET["received"]) <= 18 else None)))
