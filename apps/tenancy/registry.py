from __future__ import annotations

from django.apps import apps


WORKSPACE_APP_LABELS = frozenset({"party", "loans", "notify_v2", "rates"})
# Infrastructure is RLS-owned without exposing it through legacy generic data tools.
RLS_PROTECTED_APP_LABELS = WORKSPACE_APP_LABELS | {"data_portability"}
CONTROL_PLANE_OWNED_MODELS = frozenset({"orgs.workspacerole", "orgs.workspacerolegrant"})
RLS_MIGRATION_BY_APP = {
    "data_portability": "0002_workspace_guards",
    "orgs": "0008_companyinvitation_role_fingerprint_workspacerole_and_more",
    "loans": "0003_enable_workspace_rls",
    "notify_v2": "0003_enable_workspace_rls",
    "party": "0002_enable_workspace_rls",
    "rates": "0002_enable_workspace_rls",
}
# Models introduced after their app's original RLS rollout have their own gate.
RLS_MIGRATION_BY_MODEL = {
    "loans.historicalloanattachment": "0014_legacy_media",
    "data_portability.legacymediareceipt": "0015_legacy_media",
    "loans.historicalloanevidence": "0013_historicalloanevidence",
    "data_portability.loanarchivebatch": "0014_loanarchivebatch",
    "loans.historicalloanimport": "0009_historicalloanimport",
    "data_portability.loanhistorybatch": "0012_loanhistorybatch_result_loanhistorybatch_workspace",
    "data_portability.importbundle": "0010_importbundle",
    "data_portability.mappingpresetversion": "0008_mappingpresetversion_importbatch_mapping_preset_and_more",
    "data_portability.childidentity": "0004_child_guards",
    "data_portability.childsourceidentity": "0004_child_guards",
    "loans.pawnreleasebatch": "0005_pawnreleasebatch_pawnreleasebatchline_and_more",
    "loans.pawnreleasebatchline": "0005_pawnreleasebatch_pawnreleasebatchline_and_more",
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
                and (model._meta.app_label in RLS_PROTECTED_APP_LABELS or model._meta.label_lower in CONTROL_PLANE_OWNED_MODELS)
            ),
            key=lambda model: model._meta.label_lower,
        )
    )


def rls_protected_models(app_registry=apps):
    return tuple(
        model
        for model in workspace_owned_models(app_registry)
        if model._meta.app_label in RLS_PROTECTED_APP_LABELS or model._meta.label_lower in CONTROL_PLANE_OWNED_MODELS
    )
