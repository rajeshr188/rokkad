"""Explicit forms and signed reviews over Loans-owned khata commands."""
import hashlib
import uuid
from decimal import Decimal
from io import BytesIO

from PIL import Image, ImageOps

from django.core import signing
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.tenant_apps.loans.access import loans_workspace_required
from apps.tenant_apps.loans.models import KhataAccount, KhataSeries, KhataSeriesStatusChange, KhataPolicyRevision, KhataCollateralPhoto
from apps.tenant_apps.loans.services.action_access import require_workspace_action
from apps.tenant_apps.loans.services import khata_accounts as accounts, khata_opening as opening
from apps.tenant_apps.loans.services import khata_revisions as revisions, khata_collateral as collateral
from apps.tenant_apps.loans.services import khata_servicing as servicing, khata_settlement as settlement, khata_corrections as corrections
from .khata_forms import TermsForm, SeriesForm, PolicyForm, ActionForm
from .khata_views import _private
from .khata_items import item_rows
from apps.tenant_apps.loans.selectors.khata_items import collateral_items
from apps.tenant_apps.loans.selectors.khata_workflow import opening_illustration
from apps.tenant_apps.loans.services.origination_settings import collateral_photos_required


ACTIONS = {
    "proposal": ("Propose agreement terms", ("data.edit",)),
    "deposit": ("Receive collateral", ("data.edit",)),
    "photo": ("Attach collateral photo", ("data.edit",)),
    "approve": ("Approve opening", ("loan.approve",)),
    "withdraw": ("Record actual withdrawal", ("loan.disburse",)),
    "interest": ("Receive interest", ("loan.repay",)),
    "finalize": ("Finalize completed interest", ("loan.repay",)),
    "approve-change": ("Approve agreement change", ("loan.approve",)),
    "activate-change": ("Activate approved agreement", ()),
    "exchange": ("Exchange collateral", ("data.edit", "loan.release")),
    "handover": ("Hand over reserved collateral", ("loan.release",)),
    "return-unopened": ("Return unopened collateral", ("loan.release",)),
    "settle": ("Collect full settlement", ("loan.repay",)),
    "correct": ("Correct eligible source operation", ("workspace.settings.manage",)),
    "cancel": ("Cancel unopened draft", ("data.edit",)),
}
SALT = "loans.khata.review.1"


def _return_context(account, action):
    tab = {
        "deposit": "collateral", "photo": "collateral", "exchange": "collateral",
        "handover": "collateral", "return-unopened": "collateral", "interest": "interest",
        "finalize": "interest", "correct": "history", "withdraw": "overview", "settle": "overview",
        "cancel": "overview",
    }.get(action, "actions")
    return dict(account_return_tab=tab, account_return_label={
        "collateral": "Collateral", "interest": "Interest", "history": "Source history",
        "overview": "Overview", "actions": "Actions",
    }[tab])


def action_links(request, account, workflow=None):
    access = request.loans_workspace_access
    names = []
    live = account.state in ("DRAFT", "APPROVED", "ACTIVE")
    if live:
        names.extend(("proposal", "deposit", "photo"))
    if live and not account.opened_on:
        names.extend(("approve", "return-unopened", "cancel"))
    if account.state in ("APPROVED", "ACTIVE"):
        names.append("withdraw")
    if account.state == "ACTIVE":
        names.extend(("interest", "finalize", "approve-change", "activate-change", "exchange", "settle", "correct"))
    if account.state in ("ACTIVE", "SETTLED_RETURN_PENDING"):
        names.append("handover")
    if workflow:
        names = [name for name in names if workflow["ready"].get(name, True)]
        approval = workflow["valid_approval"]
        if approval and "activate-change" in names:
            review = approval.evidence["review"]
            if not access.can("loan.repay" if Decimal(review["principal_repayment"]) else "loan.approve") or (review.get("outgoing_ids") and not access.can("loan.release")):
                names.remove("activate-change")
    return [(name, ACTIONS[name][0]) for name in names if all(access.can(cap) for cap in ACTIONS[name][1])
        and (name != "activate-change" or access.can("loan.approve") or access.can("loan.repay"))]


def _terms_initial(account):
    latest = account.agreement_revisions.order_by("-number").first()
    return dict(request_key=uuid.uuid4(), expected_revision=latest.number, agreed_limit=latest.agreed_limit,
        monthly_rate=latest.monthly_rate, ltv_percent=latest.ltv * 100, frequency=latest.frequency,
        lender_name=latest.lender_name, lender_address=latest.lender_address)


def _terms(data):
    return dict(agreed_limit=data["agreed_limit"], monthly_rate=data["monthly_rate"], ltv=data["ltv_percent"] / 100,
        frequency=data["frequency"], lender_name=data["lender_name"], lender_address=data["lender_address"], intended_on=timezone.localdate())


def _preview(action, args, data):
    if action == "approve":
        return opening.preview_opening(**args)
    if action == "withdraw":
        return opening.preview_withdrawal(**args, value=data["value"])
    if action == "interest":
        return servicing.preview_interest_payment(**args, value=data["value"])
    if action == "finalize":
        return servicing.preview_finalization(**args)
    if action == "approve-change":
        return revisions.preview_revision(**args, principal_repayment=data["principal_repayment"], outgoing_ids=[i.pk for i in data["outgoing"]])
    if action == "activate-change":
        return revisions.preview_activation(**args, approval_id=data["approval"].pk)
    if action == "exchange":
        return collateral.preview_exchange(**args, outgoing_ids=[i.pk for i in data["outgoing"]], incoming_ids=[i.pk for i in data["incoming"]])
    if action == "handover":
        return collateral.preview_handover(**args, item_id=data["item"].pk, parent_id=data["parent"].pk)
    if action == "settle":
        return settlement.preview_settlement(**args)
    if action == "correct":
        return corrections.preview_correction(**args, source_id=data["source"].pk)
    return {"snapshot": {}, "review_hash": None}


def _execute(action, args, data, review_hash):
    common = dict(args, business_date=timezone.localdate(), request_key=data["request_key"])
    reviewed = dict(common, review_hash=review_hash)
    if action == "proposal":
        return accounts.propose_revision(**args, request_key=data["request_key"], expected_revision=data["expected_revision"], reason=data["reason"], **_terms(data))
    if action == "deposit":
        return opening.record_deposit(**common, upload=data.get("upload"), **{k: data[k] for k in ("description", "metal", "quantity", "gross_weight", "net_weight", "purity", "storage_reference", "received_from")})
    if action == "photo":
        return opening.attach_photo(**common, item_id=data["item"].pk, upload=data["upload"])
    if action == "approve":
        return opening.approve_opening(**reviewed)
    if action in ("withdraw", "interest"):
        fn = opening.record_withdrawal if action == "withdraw" else servicing.record_interest_payment
        return fn(**reviewed, value=data["value"], payment_reference=data["payment_reference"])
    if action == "finalize":
        return servicing.finalize_interest(**reviewed)
    if action == "approve-change":
        return revisions.approve_revision(**reviewed, principal_repayment=data["principal_repayment"],
            outgoing_ids=[i.pk for i in data["outgoing"]], agreement_reference=data["agreement_reference"])
    if action == "activate-change":
        return revisions.activate_revision(**reviewed, approval_id=data["approval"].pk, payment_reference=data["payment_reference"])
    if action == "exchange":
        return collateral.record_exchange(**reviewed, outgoing_ids=[i.pk for i in data["outgoing"]], incoming_ids=[i.pk for i in data["incoming"]], reason=data["reason"])
    if action == "handover":
        return collateral.record_handover(**reviewed, item_id=data["item"].pk, parent_id=data["parent"].pk, recipient=data["recipient"], reference=data["reference"])
    if action == "return-unopened":
        return opening.return_unopened_item(**common, item_id=data["item"].pk, recipient=data["recipient"], reason=data["reason"])
    if action == "settle":
        return settlement.record_settlement(**reviewed, payment_reference=data["payment_reference"])
    if action == "correct":
        return corrections.record_correction(**reviewed, source_id=data["source"].pk, cash_resolution=data["cash_resolution"], reason=data["reason"], resolution_reference=data["resolution_reference"])
    if action == "cancel":
        return accounts.cancel_draft(**args, reason=data["reason"])
    raise Http404


def _receipt_context(request):
    source = request.POST if request.method == "POST" else request.GET
    return dict(return_exchange=source.get("return_to") == "exchange",
        exchange_outgoing=source.getlist("exchange_outgoing" if request.method == "POST" else "outgoing"),
        exchange_incoming=source.getlist("exchange_incoming" if request.method == "POST" else "incoming"))


def _exchange_data(request, account, form):
    selected = {}
    for role in ("outgoing", "incoming"):
        ids = [int(v) for v in (form[role].value() or []) if str(v).isdecimal() and len(str(v)) <= 18]
        selected[role] = item_rows(account, collateral_items(account, mode=role).filter(pk__in=ids))
    return dict(selected, endpoint=reverse("workspace_loans:khata_collateral", args=(account.workspace.slug, account.pk)),
        receive=reverse("workspace_loans:khata_action", args=(account.workspace.slug, account.pk, "deposit")),
        suggested=request.GET.get("suggest", ""))


def _servicing_data(account, form, action):
    role = "outgoing" if action == "approve-change" else "item"
    mode = {"approve-change": "outgoing", "photo": "held", "handover": "pending"}[action]
    values = form[role].value() or []
    if role == "item":
        values = [values] if values else []
    ids = [int(v) for v in values if str(v).isdecimal() and len(str(v)) <= 18]
    return dict(roles=[role], mode=mode, single=role == "item", handover=action == "handover",
        selected={role: item_rows(account, collateral_items(account, mode=mode).filter(pk__in=ids))},
        endpoint=reverse("workspace_loans:khata_collateral", args=(account.workspace.slug, account.pk)))


REVIEW_LABELS = {
    "principal": "Principal before operation (INR)", "unused": "Unused entitlement before operation (INR)",
    "interest": "All unpaid interest to closure (INR)", "total": "Total settlement to collect (INR)",
    "due_interest": "Interest due (INR)", "overdue_interest": "Interest overdue (INR)",
    "drawable": "Maximum drawable today (INR)", "amount": "Actual amount (INR)",
    "old_limit": "Current limit (INR)", "new_limit": "Proposed limit (INR)",
    "old_monthly_rate": "Current monthly rate (%)", "new_monthly_rate": "Proposed monthly rate (%)",
    "new_principal": "Principal after activation (INR)", "new_unused": "Unused entitlement after activation (INR)",
    "retained_value": "Retained collateral value (INR)", "backing": "Principal supported by retained collateral (INR)",
    "shortfall": "Exchange value shortfall (INR)", "ltv_breach": "Agreed LTV breached",
}


@loans_workspace_required
@never_cache
@require_http_methods(["GET", "POST"])
def operate(request, pk=None, action="new"):
    workspace = request.loans_workspace
    account = get_object_or_404(KhataAccount, workspace=workspace, pk=pk) if pk else None
    if action != "new" and action not in ACTIONS:
        raise Http404
    title, capabilities = ("New khata agreement draft", ("data.create",)) if action == "new" else ACTIONS[action]
    require_workspace_action(workspace, request.user, *capabilities)
    confirming = request.method == "POST" and "review_token" in request.POST
    source = request.POST if request.method == "POST" else None
    review = None
    error = None
    correction_blockers = []
    correction_blocker_count = 0
    if confirming:
        try:
            review = signing.loads(request.POST["review_token"], salt=SALT, max_age=1800)
            if (review["workspace"], review["actor"], review["account"], review["action"], review["date"]) != (
                workspace.pk, request.user.pk, pk, action, timezone.localdate().isoformat()):
                raise ValueError("This review belongs to another action, actor, workspace or business day.")
            source = QueryDict(mutable=True)
            for key, values in review["data"].items():
                source.setlist(key, values)
        except (signing.BadSignature, ValueError, KeyError):
            source = None
            error = "This review expired or changed. Please enter the instructions and review again."
    initial = _terms_initial(account) if action == "proposal" else dict(request_key=uuid.uuid4())
    if action == "exchange" and request.method == "GET":
        initial.update(outgoing=request.GET.getlist("outgoing"), incoming=request.GET.getlist("incoming"))
    if action in ("photo", "handover") and request.method == "GET":
        item_id = request.GET.get("item", "")
        if item_id.isdecimal() and len(item_id) <= 18:
            chosen_item = collateral_items(account, mode="pending" if action == "handover" else "held").filter(pk=item_id).first()
            if chosen_item is not None:
                initial["item"] = chosen_item.pk
                if action == "handover":
                    initial["parent"] = chosen_item.reservation_id
    if action == "correct" and request.method == "GET":
        source_id = request.GET.get("source", "")
        if source_id.isdecimal() and len(source_id) <= 18:
            chosen_source = account.operations.filter(pk=source_id, kind__in=("INTEREST", "EXCHANGE"), corrected_by__isnull=True).first()
            if chosen_source is not None:
                initial["source"] = chosen_source.pk
    if action in ("new", "proposal"):
        form = TermsForm(source, workspace=workspace, account=account, initial=initial,
            borrower_search=request.GET.get("borrower_q", "")[:120] if request.GET.get("native") == "1" else None)
    else:
        form = ActionForm(source, request.FILES or None, account=account, action=action, actor=request.user, replaying=confirming, initial=initial)
    if error:
        form.cleaned_data = {}
        form.add_error(None, error)
    args = dict(workspace=workspace, actor=request.user, account_id=pk)
    editing = confirming and request.POST.get("edit") == "1"
    if request.method == "POST" and source is not None and not editing and form.is_valid():
        try:
            if confirming or action in ("photo", "deposit"):
                if action == "new":
                    result = accounts.create_draft(workspace=workspace, actor=request.user,
                        series_id=form.cleaned_data["series"].pk, borrower_id=form.cleaned_data["borrower"].pk,
                        request_key=form.cleaned_data["request_key"], **_terms(form.cleaned_data))
                    pk = result.pk
                else:
                    result = _execute(action, args, form.cleaned_data, review["hash"] if review else None)
                if action == "deposit":
                    context = _receipt_context(request)
                    query = QueryDict(mutable=True)
                    if context["return_exchange"]:
                        query.setlist("outgoing", context["exchange_outgoing"])
                        query.setlist("incoming", context["exchange_incoming"])
                        query["suggest"] = str(result.pk)
                        return redirect(reverse("workspace_loans:khata_action", args=(workspace.slug, pk, "exchange")) + "?" + query.urlencode())
                    query["received"] = str(result.pk)
                    destination = reverse("workspace_loans:khata_action", args=(workspace.slug, pk, "deposit")) if request.POST.get("add_another") else reverse("workspace_loans:khata_collateral", args=(workspace.slug, pk))
                    return redirect(destination + "?" + query.urlencode())
                if action == "exchange":
                    return redirect(reverse("workspace_loans:khata_detail", args=(workspace.slug, pk)) + "?section=collateral&exchange=" + str(result.pk))
                if action in ("photo", "handover"):
                    return redirect(reverse("workspace_loans:khata_collateral", args=(workspace.slug, pk)) + ("?mode=pending" if action == "handover" else "?q=" + str(form.cleaned_data["item"].pk)))
                tab = _return_context(account, action)["account_return_tab"]
                query = QueryDict(mutable=True)
                query["tab"] = tab
                if action == "correct":
                    query["history-operation"] = str(result.pk)
                return redirect(reverse("workspace_loans:khata_detail", args=(workspace.slug, pk)) + "?" + query.urlencode())
            preview = _preview(action, args, form.cleaned_data)
            payload = dict(workspace=workspace.pk, actor=request.user.pk, account=pk, action=action,
                date=timezone.localdate().isoformat(), data={k: request.POST.getlist(k)
                    for k in request.POST if k != "csrfmiddlewaretoken"}, hash=preview["review_hash"])
            token = signing.dumps(payload, salt=SALT, compress=True)
            entries = [(field.label, field.value()) for field in form if not field.is_hidden]
            # Use validated objects for readable borrower/item/source choices.
            for index, field in enumerate([f for f in form if not f.is_hidden]):
                value = form.cleaned_data.get(field.name)
                if hasattr(value, "pk"):
                    entries[index] = (field.label, field.field.label_from_instance(value))
                elif hasattr(value, "model"):
                    entries[index] = (field.label, "; ".join(field.field.label_from_instance(i) for i in value))
            snapshot = preview["snapshot"]
            facts = [(label, snapshot[key]) for key, label in REVIEW_LABELS.items() if key in snapshot]
            facts.extend((f"{metal.title()} replacement shortfall (INR)", value) for metal, value in snapshot.get("shortfalls", {}).items())
            return _private(render(request, "loans/khata/review.html", dict(account=account, title=title, **_return_context(account, action),
                entries=entries, review_token=token, warnings=snapshot.get("warnings", []),
                facts=facts,
                periods=snapshot.get("periods", []), valuations=snapshot.get("valuations", []),
                exchange_groups=snapshot.get("groups", []),
                opening_estimate=opening_illustration(**{k: form.cleaned_data[k] for k in ("agreed_limit", "monthly_rate", "frequency")}) if action == "new" else None)))
        except (ValueError, ValidationError, ObjectDoesNotExist, OSError) as exc:
            form.add_error(None, str(exc))
            if isinstance(exc, corrections.KhataCorrectionBlocked):
                correction_blocker_count = len(exc.operation_ids)
                correction_blockers = account.operations.filter(pk__in=exc.operation_ids).order_by("sequence")[:10]
    context = dict(account=account, form=form, title=title, action=action, **_return_context(account, action),
        immediate=action == "photo", today=timezone.localdate(),
        correction_blockers=correction_blockers, correction_blocker_count=correction_blocker_count)
    if action == "new":
        context.update(native_borrower=request.GET.get("native") == "1", borrower_q=request.GET.get("borrower_q", "")[:120])
    if action == "deposit":
        context.update(_receipt_context(request), photo_required=collateral_photos_required(workspace.pk),
            received=account.collateral.filter(pk=request.GET.get("received")).first()
                if request.GET.get("received", "").isdecimal() and len(request.GET["received"]) <= 18 else None)
    if action == "exchange":
        context["exchange_data"] = _exchange_data(request, account, form)
    if action in ("approve-change", "photo", "handover"):
        context["servicing_data"] = _servicing_data(account, form, action)
    template = "exchange" if action == "exchange" else "receive" if action == "deposit" else "form"
    return _private(render(request, "loans/khata/" + template + ".html", context))


@loans_workspace_required
@never_cache
@require_http_methods(["GET", "POST"])
def setup(request):
    workspace = request.loans_workspace
    require_workspace_action(workspace, request.user, "workspace.settings.manage")
    policy = KhataPolicyRevision.objects.filter(workspace=workspace).order_by("-number").first()
    kind = request.POST.get("kind") if request.method == "POST" else None
    series_form = SeriesForm(request.POST if kind == "series" else None, workspace=workspace)
    policy_form = PolicyForm(request.POST if kind == "policy" else None,
        initial=dict(request_key=uuid.uuid4(), exchange=policy.exchange if policy else "WARN", overdue=policy.overdue if policy else "WARN"))
    form = series_form if kind == "series" else policy_form
    if kind in ("series", "policy") and form.is_valid():
        try:
            if kind == "series":
                data = dict(form.cleaned_data)
                license = data.pop("license")
                accounts.create_series(workspace=workspace, actor=request.user, license_id=license.pk if license else None, **data)
            else:
                opening.set_policies(workspace=workspace, actor=request.user, **form.cleaned_data)
            return redirect("workspace_loans:khata_setup", workspace_slug=workspace.slug)
        except (ValueError, ValidationError) as exc:
            form.add_error(None, str(exc))
    return _private(render(request, "loans/khata/setup.html", dict(series_form=series_form, policy_form=policy_form,
        can_policy=request.loans_workspace_access.can("workspace.transfer"),
        status_history=Paginator(KhataSeriesStatusChange.objects.filter(workspace=workspace).select_related("series", "created_by").order_by("-created_at", "-pk"), 25).get_page(request.GET.get("status-page")),
        series=KhataSeries.objects.filter(workspace=workspace).select_related("license").order_by("name"))))


@loans_workspace_required
@never_cache
@require_GET
def photo(request, pk, photo_pk):
    row = get_object_or_404(KhataCollateralPhoto, workspace=request.loans_workspace, item__account_id=pk, pk=photo_pk)
    try:
        with row.file.open("rb") as stream:
            content = stream.read(row.byte_size + 1)
        if len(content) != row.byte_size or hashlib.sha256(content).hexdigest() != row.sha256:
            raise ValueError("Photo bytes do not match retained evidence.")
    except (OSError, ValueError) as exc:
        return _private(HttpResponse(str(exc), status=409, content_type="text/plain"))
    mime = row.mime_type
    if request.GET.get("thumbnail") == "1":
        try:
            with Image.open(BytesIO(content)) as source:
                image = ImageOps.exif_transpose(source)
                image.thumbnail((160, 120))
                output = BytesIO()
                image.convert("RGB").save(output, format="JPEG", quality=75)
                content, mime = output.getvalue(), "image/jpeg"
        except (OSError, ValueError, Image.DecompressionBombError):
            return _private(HttpResponse("Photograph preview is unavailable.", status=409, content_type="text/plain"))
    response = HttpResponse(content, content_type=mime)
    response["Content-Disposition"] = 'inline; filename="collateral-photo"'
    return _private(response)


@loans_workspace_required
@never_cache
@require_GET
def export(request):
    from apps.tenant_apps.loans.services.khata_recovery import export_archive
    try:
        content = export_archive(workspace=request.loans_workspace, actor=request.user)
    except (ValueError, OSError) as exc:
        return _private(HttpResponse(str(exc), status=409, content_type="text/plain"))
    response = HttpResponse(content, content_type="application/zip")
    response["Content-Disposition"] = 'attachment; filename="khata-native-recovery.zip"'
    response["X-Archive-SHA256"] = hashlib.sha256(content).hexdigest()
    return _private(response)
