from django import forms
from django.apps import apps
from django.conf import settings
from import_export.formats import base_formats


def tenant_app_configs():
    """Resolve TENANT_APPS entries whether they name a module or AppConfig class."""
    configured = set(settings.TENANT_APPS)
    return tuple(
        config
        for config in apps.get_app_configs()
        if config.name in configured
        or f"{config.__class__.__module__}.{config.__class__.__name__}" in configured
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
