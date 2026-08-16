from __future__ import annotations

from django.apps import apps


WORKSPACE_APP_LABELS = frozenset({"party", "loans", "notify_v2", "rates"})
RLS_PROTECTED_APP_LABELS = WORKSPACE_APP_LABELS
RLS_MIGRATION_BY_APP = {
    "loans": "0067_enable_workspace_rls",
    "notify_v2": "0011_enable_workspace_rls",
    "party": "0009_enable_workspace_rls",
    "rates": "0006_enable_workspace_rls",
}


def workspace_owned_models(app_registry=apps):
    """Return the authoritative concrete shared-schema business-model registry."""

    return tuple(
        sorted(
            (
                model
                for model in app_registry.get_models()
                if not model._meta.abstract
                and not model._meta.proxy
                and model._meta.app_label in WORKSPACE_APP_LABELS
            ),
            key=lambda model: model._meta.label_lower,
        )
    )


def rls_protected_models(app_registry=apps):
    return tuple(
        model
        for model in workspace_owned_models(app_registry)
        if model._meta.app_label in RLS_PROTECTED_APP_LABELS
    )
