from django.urls import path

from . import views

app_name = "data_import"

urlpatterns = [
    path("export/", views.export_form, name="export_form"),
    path(
        "export/<str:model_name>/<str:export_format>/",
        views.export_data,
        name="export_data",
    ),
    path("import/", views.import_data, name="import_data"),
    path("model-fields/", views.get_model_fields, name="get_model_fields"),
]
