import logging
import os
import tempfile
import zipfile
from importlib import import_module

from django.apps import apps
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import render
from django.utils.text import slugify
from import_export import resources
from import_export.formats import base_formats
from tablib import Dataset

from ..forms import ExportForm, ImportForm

logger = logging.getLogger(__name__)


@login_required
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

    return render(request, "export.html", {"form": form})


@login_required
def export_data(request, model_name, export_format):
    model = None
    for app in settings.TENANT_APPS:
        try:
            model = apps.get_model(app.split(".")[-1], model_name)
            break
        except LookupError:
            continue

    if not model:
        return HttpResponseBadRequest(f"Model '{model_name}' does not exist.")

    valid_formats = [
        fmt().get_title()
        for fmt in [
            base_formats.CSV,
            base_formats.JSON,
            base_formats.XLS,
            base_formats.HTML,
        ]
    ]
    if export_format not in valid_formats:
        return HttpResponseBadRequest(f"Invalid export format '{export_format}'.")

    try:
        admin_module = import_module(f"{app}.admin")
        ModelResource = getattr(admin_module, f"{model_name}Resource")
        logger.warning(f"ModelResource {ModelResource} for '{model_name}' found.")
    except (ImportError, AttributeError):
        logger.warning(
            f"ModelResource for '{model_name}' does not exist. Falling back to modelresource_factory."
        )
        ModelResource = resources.modelresource_factory(model=model)

    dataset = ModelResource().export()
    export_data = dataset.export(format=export_format)

    response = HttpResponse(export_data, content_type="application/octet-stream")
    response[
        "Content-Disposition"
    ] = f'attachment; filename="{request.user.workspace}_{model_name}.{export_format}"'
    return response


@login_required
def export_multiple_models(request, model_names, export_format):
    valid_formats = [
        fmt().get_title()
        for fmt in [
            base_formats.CSV,
            base_formats.JSON,
            base_formats.XLS,
            base_formats.HTML,
        ]
    ]
    if export_format not in valid_formats:
        return HttpResponseBadRequest(f"Invalid export format '{export_format}'.")

    with tempfile.TemporaryDirectory() as temp_dir:
        for model_name in model_names:
            model = None
            for app in settings.TENANT_APPS:
                try:
                    model = apps.get_model(app.split(".")[-1], model_name)
                    break
                except LookupError:
                    continue

            if not model:
                return HttpResponseBadRequest(f"Model '{model_name}' does not exist.")

            try:
                admin_module = import_module(f"{app}.admin")
                ModelResource = getattr(admin_module, f"{model_name}Resource")
                logger.warning(
                    f"ModelResource {ModelResource} for '{model_name}' found."
                )
            except (ImportError, AttributeError):
                logger.warning(
                    f"ModelResource for '{model_name}' does not exist. Falling back to modelresource_factory."
                )
                ModelResource = resources.modelresource_factory(model=model)

            dataset = ModelResource().export()
            export_data = dataset.export(format=export_format)

            file_path = os.path.join(temp_dir, f"{slugify(model_name)}.{export_format}")
            with open(file_path, "wb") as file:
                file.write(export_data.encode("utf-8"))

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


@login_required
def import_data(request):
    form = ImportForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        model_name = form.cleaned_data["model_name"]
        import_file = form.cleaned_data["import_file"]

        model = None
        for app in settings.TENANT_APPS:
            try:
                model = apps.get_model(app.split(".")[-1], model_name)
                break
            except LookupError:
                continue

        if model is None:
            raise ValueError(f"No model named '{model_name}' found in TENANT_APPS")

        model_resource = None
        try:
            app_label = model._meta.app_label
            module_path = f"apps.tenant_apps.{app_label}.resources"
            print(f"Attempting to import module: {module_path}")

            resource_module = import_module(module_path)
            print(f"Successfully imported module: {resource_module}")

            for attr_name in dir(resource_module):
                attr = getattr(resource_module, attr_name)
                if isinstance(attr, type) and issubclass(attr, resources.ModelResource):
                    if attr._meta.model == model:
                        print(f"Found matching ModelResource: {attr}")
                        model_resource = attr()
                        break
        except ImportError as e:
            print(f"ImportError: {e}")

        if model_resource is None:
            logger.warning(
                "No ModelResource found. Falling back to modelresource_factory."
            )
            model_resource = resources.modelresource_factory(model=model)()

        dataset = Dataset().load(import_file.read().decode())
        with transaction.atomic():
            result = model_resource.import_data(dataset, raise_errors=True)

        if not result.has_errors():
            rows_imported = [row for row in result.rows if row.diff]
            return render(
                request, "import_success.html", {"rows_imported": rows_imported}
            )
        else:
            errors = result.get_errors()
            return render(request, "import_error.html", {"errors": errors})

    return render(request, "import.html", {"form": form})


@login_required
def get_model_fields(request):
    model_name = request.GET.get("model_name")
    model = None
    for app in settings.TENANT_APPS:
        try:
            model = apps.get_model(app.split(".")[-1], model_name)
            break
        except LookupError:
            continue

    if model is None:
        return JsonResponse({"error": "Model not found"}, status=404)

    fields = [field.name for field in model._meta.fields]
    return render(request, "model_fields.html", {"fields": fields})
