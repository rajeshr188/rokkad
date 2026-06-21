import logging
import os
import tempfile
import zipfile
from functools import wraps
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.utils.text import slugify
from import_export import resources
from import_export.formats import base_formats
from tablib import Dataset

from apps.orgs.models import Membership
from apps.orgs.permissions import is_platform_admin
from apps.orgs.tenant_context import resolve_request_workspace

from .forms import ExportForm, ImportForm

logger = logging.getLogger(__name__)

ADMIN_ROLE_NAMES = {"Owner", "Admin", "Administrator"}


def owner_or_admin_required(view_func):
    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        workspace = resolve_request_workspace(request)
        if workspace is None:
            raise PermissionDenied("Workspace required")

        if is_platform_admin(request.user):
            return view_func(request, *args, **kwargs)

        try:
            membership = Membership.objects.select_related("role").get(
                user=request.user,
                company=workspace,
            )
        except Membership.DoesNotExist as exc:
            raise PermissionDenied("Not a workspace member") from exc

        role_name = membership.role.name if membership.role else ""
        if role_name not in ADMIN_ROLE_NAMES:
            raise PermissionDenied("Owner or admin access is required")

        return view_func(request, *args, **kwargs)

    return _wrapped


def _valid_export_formats():
    return [
        fmt().get_title()
        for fmt in [
            base_formats.CSV,
            base_formats.JSON,
            base_formats.XLS,
            base_formats.HTML,
        ]
    ]


def _find_tenant_model(model_name):
    for app_path in settings.TENANT_APPS:
        app_label = app_path.split(".")[-1]
        try:
            return apps.get_model(app_label, model_name), app_path
        except LookupError:
            continue
    return None, None


def _resource_from_admin(model, app_path):
    if not app_path:
        return None

    try:
        admin_module = import_module(f"{app_path}.admin")
        return getattr(admin_module, f"{model.__name__}Resource")
    except (ImportError, AttributeError):
        logger.info(
            "No admin ModelResource for %s.%s.",
            model._meta.app_label,
            model.__name__,
        )
        return None


def _resource_from_module(model):
    try:
        resource_module = import_module(
            f"apps.tenant_apps.{model._meta.app_label}.resources"
        )
    except ImportError:
        logger.info(
            "No resource module for %s.%s.",
            model._meta.app_label,
            model.__name__,
        )
        return None

    for attr_name in dir(resource_module):
        attr = getattr(resource_module, attr_name)
        if (
            isinstance(attr, type)
            and issubclass(attr, resources.ModelResource)
            and getattr(attr._meta, "model", None) == model
        ):
            return attr
    return None


def _export_resource_for_model(model, app_path=None):
    return (
        _resource_from_admin(model, app_path)
        or _resource_from_module(model)
        or resources.modelresource_factory(model=model)
    )


def _import_resource_for_model(model):
    return _resource_from_module(model) or resources.modelresource_factory(model=model)


@owner_or_admin_required
def export_form(request):
    if request.method == "POST":
        form = ExportForm(request.POST)
        if form.is_valid():
            return export_multiple_models(
                request,
                form.cleaned_data["model_names"],
                form.cleaned_data["export_format"],
            )
    else:
        form = ExportForm()

    return render(request, "data_import/export.html", {"form": form})


@owner_or_admin_required
def export_data(request, model_name, export_format):
    model, app_path = _find_tenant_model(model_name)
    if not model:
        return HttpResponseBadRequest(f"Model '{model_name}' does not exist.")

    if export_format not in _valid_export_formats():
        return HttpResponseBadRequest(f"Invalid export format '{export_format}'.")

    model_resource = _export_resource_for_model(model, app_path)()
    dataset = model_resource.export()
    export_bytes = dataset.export(format=export_format)

    response = HttpResponse(export_bytes, content_type="application/octet-stream")
    workspace_name = getattr(
        getattr(request, "tenant", None),
        "schema_name",
        "workspace",
    )
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{workspace_name}_{model_name}.{export_format}"'
    return response


@owner_or_admin_required
def export_multiple_models(request, model_names, export_format):
    if export_format not in _valid_export_formats():
        return HttpResponseBadRequest(f"Invalid export format '{export_format}'.")

    with tempfile.TemporaryDirectory() as temp_dir:
        for model_name in model_names:
            model, app_path = _find_tenant_model(model_name)
            if not model:
                return HttpResponseBadRequest(f"Model '{model_name}' does not exist.")

            model_resource = _export_resource_for_model(model, app_path)()
            dataset = model_resource.export()
            export_bytes = dataset.export(format=export_format)

            file_path = os.path.join(temp_dir, f"{slugify(model_name)}.{export_format}")
            with open(file_path, "wb") as file:
                if isinstance(export_bytes, str):
                    export_bytes = export_bytes.encode("utf-8")
                file.write(export_bytes)

        zip_file_path = os.path.join(temp_dir, "exported_models.zip")
        with zipfile.ZipFile(zip_file_path, "w") as zip_file:
            for file_name in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file_name)
                if file_name != "exported_models.zip":
                    zip_file.write(file_path, os.path.basename(file_path))

        with open(zip_file_path, "rb") as zip_file:
            response = HttpResponse(zip_file.read(), content_type="application/zip")
            response[
                "Content-Disposition"
            ] = 'attachment; filename="exported_models.zip"'
            return response


@owner_or_admin_required
def import_data(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        model_name = form.cleaned_data["model_name"]
        import_file = form.cleaned_data["import_file"]

        model, _app_path = _find_tenant_model(model_name)
        if model is None:
            return HttpResponseBadRequest(
                f"No model named '{model_name}' found in TENANT_APPS"
            )

        model_resource = _import_resource_for_model(model)()
        dataset = Dataset().load(import_file.read().decode())

        with transaction.atomic():
            result = model_resource.import_data(dataset, raise_errors=True)

        if not result.has_errors():
            rows_imported = [row for row in result.rows if row.diff]
            return render(
                request,
                "data_import/import_success.html",
                {"rows_imported": rows_imported},
            )

        return render(
            request,
            "data_import/import_error.html",
            {"errors": result.get_errors()},
        )

    return render(request, "data_import/import.html", {"form": form})


@owner_or_admin_required
def get_model_fields(request):
    model_name = request.GET.get("model_name")
    model, _app_path = _find_tenant_model(model_name)
    if model is None:
        return JsonResponse({"error": "Model not found"}, status=404)

    fields = [field.name for field in model._meta.fields]
    return render(request, "data_import/model_fields.html", {"fields": fields})
