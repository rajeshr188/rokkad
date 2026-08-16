from django import forms
from django.apps import apps
from import_export.formats import base_formats

from apps.tenancy.registry import WORKSPACE_APP_LABELS


def tenant_app_configs():
    """Return the surviving shared-schema business application configs."""
    return tuple(
        config
        for config in apps.get_app_configs()
        if config.label in WORKSPACE_APP_LABELS
    )


def _tenant_model_choices():
    choices = []
    for app_config in tenant_app_configs():
        for model in app_config.models.values():
            choices.append((model.__name__, model.__name__))
    return sorted(choices, key=lambda choice: choice[1].lower())


class ExportForm(forms.Form):
    model_names = forms.MultipleChoiceField(
        choices=_tenant_model_choices,
        widget=forms.CheckboxSelectMultiple,
        label="Select Models to Export",
    )
    export_format = forms.ChoiceField(
        choices=[
            (fmt().get_title(), fmt().get_title())
            for fmt in [
                base_formats.CSV,
                base_formats.JSON,
                base_formats.XLS,
                base_formats.HTML,
            ]
        ]
    )


class ImportForm(forms.Form):
    model_name = forms.ChoiceField(choices=_tenant_model_choices)
    import_file = forms.FileField()
