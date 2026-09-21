from urllib.parse import urlencode

from django.core import signing
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods

from .access import require_access
from .contracts import PROFILE, schema
from . import bundle_history, bundle_commit, bundle_import, bundles, child_contracts
from .forms import BundleUploadForm, MappingForm, UploadForm, PROFILE_CHOICES, RoleTypeMappingForm
from .models import ImportBatch, ImportBundle
from .presets import available_presets, save_preset, preset_for_batch
from .parsers import MAX_BYTES, PortabilityError
from .services import cancel_import, commit_import, export_children, export_parties, preview_import, stage_import, validate_import
from .name_reviews import review_distinct_names
from .address_reviews import review_distinct_addresses


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def upload(request):
    require_access(request.workspace.pk, request.user, "import")
    is_bundle = request.method == "POST" and request.POST.get("action") == "bundle"
    form = UploadForm((request.POST or None) if not is_bundle else None, (request.FILES or None) if not is_bundle else None)
    bundle_form = BundleUploadForm(request.POST if is_bundle else None, request.FILES if is_bundle else None)
    receipt_rows, receipt_error, history_id = None, None, None
    if request.GET.get("bundle_receipt"):
        try:
            receipt = signing.loads(request.GET["bundle_receipt"], salt="party-bundle-staging", max_age=86400)
            if receipt["workspace"] != request.workspace.pk:
                raise signing.BadSignature()
            history_id = receipt.get("history")
            ids = [key for profile, key in receipt["batches"] if key]
            found = {str(b.public_id): b for b in ImportBatch.objects.filter(workspace_id=request.workspace.pk, public_id__in=ids)}
            receipt_rows = [{"profile": profile, "batch": found.get(key), "empty": key is None} for profile, key in receipt["batches"]]
        except signing.BadSignature:
            receipt_error = "This bundle receipt is invalid or expired. Reopen it in Bundle history, or use Recent imports for individual batches."
    if is_bundle and bundle_form.is_valid():
        try:
            uploaded = bundle_form.cleaned_data["bundle_file"]
            if uploaded.size > bundle_import.MAX_BUNDLE_BYTES:
                raise PortabilityError("Upload a Party ZIP bundle of at most 31 MiB.")
            history = bundle_import.stage_bundle_history(workspace_id=request.workspace.pk, actor=request.user,
                content=uploaded.read(bundle_import.MAX_BUNDLE_BYTES + 1))
            receipt = bundle_history.review_receipt(history)
            response = redirect("workspace_portability:upload", workspace_slug=request.workspace.slug)
            response["Location"] += "?" + urlencode({"bundle_receipt": receipt})
            return response
        except PortabilityError as exc:
            bundle_form.add_error(None, str(exc))
    if request.method == "POST" and not is_bundle and form.is_valid():
        uploaded = form.cleaned_data["source_file"]
        try:
            if uploaded.size > MAX_BYTES:
                raise PortabilityError("The upload exceeds 5 MiB.")
            batch = stage_import(workspace_id=request.workspace.pk, actor=request.user,
                content=uploaded.read(MAX_BYTES + 1), filename=uploaded.name,
                source_system=form.cleaned_data["source_system"], profile=form.cleaned_data["profile"] or PROFILE)
            return redirect("workspace_portability:batch", workspace_slug=request.workspace.slug, batch_id=batch.public_id)
        except PortabilityError as exc:
            form.add_error(None, str(exc))
    batches = ImportBatch.objects.filter(workspace_id=request.workspace.pk).order_by("-created_at")[:20]
    histories = Paginator(ImportBundle.objects.filter(workspace_id=request.workspace.pk)
        .select_related(*ImportBundle.PROFILE_FIELDS).order_by("-created_at", "-pk"), 20).get_page(request.GET.get("history_page"))
    return render(request, "data_portability/upload.html", {"form": form, "batches": batches, "bundle_form": bundle_form, "receipt_rows": receipt_rows, "receipt_error": receipt_error, "history_id": history_id, "histories": histories})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def batch_detail(request, batch_id):
    args = {"workspace_id": request.workspace.pk, "actor": request.user, "batch_id": batch_id}
    batch, rows = preview_import(**args)
    form, error = None, None
    if batch.source_type in {"csv", "xlsx"} and batch.state not in {"COMPLETED", "CANCELLED"}:
        initial = None
        if batch.contract_version == child_contracts.ROLE:
            initial = {f"column_{i}": batch.mapping.get("columns", {}).get(h, "") for i, h in enumerate(batch.headers)}
        form = MappingForm(request.POST if request.POST.get("action") == "validate" else None, headers=batch.headers, profile=batch.contract_version, initial=initial)
    role_form = None
    if batch.contract_version == child_contracts.ROLE and batch.state not in {"COMPLETED", "CANCELLED"}:
        keys = [row.canonical.get("role_type_key", row.raw.get("role_type_key")) for row in rows]
        role_form = RoleTypeMappingForm(request.POST if request.POST.get("action") == "validate" else None,
            source_keys=[k for k in keys if isinstance(k, str) and k])
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "validate" and batch.state not in {"NEEDS_MAPPING", "READY"}:
                raise PortabilityError("Finished batches cannot be validated again.")
            if action == "validate" and (batch.source_type == "jsonl" or form.is_valid()) and (not role_form or role_form.is_valid()):
                mapping = {} if batch.source_type == "jsonl" else form.mapping()
                if role_form:
                    mapping["role_type_map"] = role_form.role_map()
                validate_import(**args, mapping=mapping)
            elif action == "apply_preset":
                validate_import(**args, preset_id=request.POST.get("preset_id", ""))
            elif action == "revalidate_mapping":
                if batch.mapping_preset_id:
                    validate_import(**args, preset_id=batch.mapping_preset.public_id)
                else:
                    validate_import(**args, mapping=batch.mapping)
            elif action == "save_preset":
                saved = save_preset(**args, name=request.POST.get("preset_name", ""), approval_digest=request.POST.get("approval_digest", ""))
                response = redirect("workspace_portability:batch", workspace_slug=request.workspace.slug, batch_id=batch.public_id)
                response["Location"] += "?saved_preset=" + str(saved.public_id)
                return response
            elif action == "review_distinct_names":
                review_distinct_names(**args,
                    external_ids=[s.strip() for s in request.POST.get("source_ids", "").splitlines() if s.strip()],
                    reason=request.POST.get("reason", ""), approval_digest=request.POST.get("approval_digest", ""))
            elif action == "review_distinct_addresses":
                review_distinct_addresses(**args,
                    external_ids=[s.strip() for s in request.POST.get("source_ids", "").splitlines() if s.strip()],
                    reason=request.POST.get("reason", ""), approval_digest=request.POST.get("approval_digest", ""))
            elif action == "commit":
                commit_import(**args, approval_digest=request.POST.get("approval_digest", ""),
                              acknowledge_warnings=request.POST.get("warnings") == "yes")
            elif action == "cancel":
                cancel_import(**args)
            elif action != "validate":
                raise PortabilityError("Unsupported action.")
            if (not form or not form.errors) and (not role_form or not role_form.errors):
                return redirect("workspace_portability:batch", workspace_slug=request.workspace.slug, batch_id=batch.public_id)
        except PortabilityError as exc:
            error = str(exc)
        batch, rows = preview_import(**args)
    page = Paginator(rows, 25).get_page(request.GET.get("page"))
    saved_preset = None
    if request.GET.get("saved_preset"):
        try:
            saved_preset = preset_for_batch(request.GET["saved_preset"], batch)
        except PortabilityError:
            pass
    summary_rows = [(key.replace("_", " ").capitalize(), value) for key, value in batch.summary.items() if key != "bundle_approval"]
    return render(request, "data_portability/batch.html", {"batch": batch, "rows": page, "form": form,
                                                         "error": error, "summary_rows": summary_rows, "role_form": role_form, "saved_preset": saved_preset,
                                                         "presets": available_presets(workspace_id=request.workspace.pk, actor=request.user, batch=batch) if batch.source_type in {"csv", "xlsx"} else []})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def export(request):
    require_access(request.workspace.pk, request.user, "export")
    profile = request.POST.get("profile", PROFILE) if request.method == "POST" else request.GET.get("profile", PROFILE)
    if profile not in (PROFILE, *child_contracts.PROFILES):
        return HttpResponse("Unsupported profile.", status=400)
    if request.GET.get("schema") == "1":
        return JsonResponse(schema() if profile == PROFILE else child_contracts.schema(profile))
    error = None
    if request.method == "POST":
        try:
            is_bundle = request.POST.get("action") == "bundle"
            args = {"workspace_id": request.workspace.pk, "actor": request.user}
            if is_bundle:
                result = bundles.export_bundle(**args)
                profile = bundles.PROFILE
            elif profile == PROFILE:
                result = export_parties(**args)
            else:
                result = export_children(**args, profile=profile)
            extension = "zip" if is_bundle else "jsonl"
            response = HttpResponse(result.content, content_type="application/zip" if is_bundle else "application/x-ndjson; charset=utf-8")
            response["Content-Disposition"] = f'attachment; filename="{profile.split("/")[0]}-{result.namespace}.{extension}"'
            response["X-Rokkad-Source-Namespace"] = result.namespace
            response["X-Rokkad-Profile"] = profile
            response["X-Rokkad-Record-Count"] = str(result.count)
            response["X-Rokkad-Coverage"] = "PARTIAL; " + profile + ("; metadata, files, Loans and Workspace configuration excluded" if is_bundle else "; other profiles, metadata and files excluded")
            response["X-Content-SHA256"] = result.sha256
            response["X-Content-Type-Options"] = "nosniff"
            return response
        except PortabilityError as exc:
            error = str(exc)
    return render(request, "data_portability/export.html", {"error": error, "profiles": PROFILE_CHOICES})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def bundle_review(request, bundle_id=None):
    history = None
    receipt = request.POST.get("receipt", "") if request.method == "POST" else request.GET.get("receipt", "")
    args = {"workspace_id": request.workspace.pk, "actor": request.user}
    if bundle_id is not None:
        history = bundle_history.get_history(**args, bundle_id=bundle_id)
        receipt = bundle_history.review_receipt(history)
    error, preview, batches, role_form = None, None, [], None
    try:
        batches = bundle_commit.receipt_batches(**args, receipt=receipt)
        keys = [row.raw.get("role_type_key") for batch in batches if batch.contract_version == child_contracts.ROLE
                for row in batch.rows.all() if isinstance(row.raw.get("role_type_key"), str)]
        role_form = RoleTypeMappingForm(request.POST if request.POST.get("action") == "preview" else None, source_keys=keys)
        if request.method == "POST":
            if request.POST.get("action") == "cancel_unfinished" and history is not None:
                bundle_history.cancel_unfinished(**args, bundle_id=bundle_id, confirmed=request.POST.get("confirm_cancel") == "yes")
                return redirect("workspace_portability:bundle_history", workspace_slug=request.workspace.slug, bundle_id=bundle_id)
            elif request.POST.get("action") == "preview" and role_form.is_valid():
                preview = bundle_commit.preview_bundle(**args, receipt=receipt, role_map=role_form.role_map())
                for profile in preview["profiles"]:
                    for row in profile["rows"]:
                        row["display_values"] = {k: v for k, v in row["canonical"].items() if not k.startswith("_")}
                        row["role_label"] = row["canonical"].get("_role_type", {}).get("label")
            elif request.POST.get("action") == "commit":
                bundle_commit.commit_bundle(**args, approval=request.POST.get("approval", ""),
                                            acknowledge_warnings=request.POST.get("warnings") == "yes", expected_bundle_id=bundle_id)
                if bundle_id is not None:
                    return redirect("workspace_portability:bundle_history", workspace_slug=request.workspace.slug, bundle_id=bundle_id)
                response = redirect("workspace_portability:bundle", workspace_slug=request.workspace.slug)
                response["Location"] += "?" + urlencode({"receipt": receipt})
                return response
    except PortabilityError as exc:
        error = str(exc)
    finished = bool(batches) and all(batch.state == "COMPLETED" for batch in batches)
    eligible = bool(batches) and all(batch.state in {"READY", "NEEDS_MAPPING"} for batch in batches)
    unfinished_count = sum(batch.state in {"READY", "NEEDS_MAPPING"} for batch in batches)
    return render(request, "data_portability/bundle.html", {"receipt": receipt, "batches": batches,
        "role_form": role_form, "preview": preview, "error": error, "finished": finished, "eligible": eligible, "history": history, "unfinished_count": unfinished_count})
