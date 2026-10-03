from __future__ import annotations

from django.apps import apps


WORKSPACE_APP_LABELS = frozenset({"party", "loans", "notify_v2", "rates"})
# Infrastructure is RLS-owned without exposing it through legacy generic data tools.
RLS_PROTECTED_APP_LABELS = WORKSPACE_APP_LABELS | {"data_portability"}
CONTROL_PLANE_OWNED_MODELS = frozenset({"orgs.workspacerole", "orgs.workspacerolegrant", "orgs.workspacestorageusage"})
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
    "loans.paperbacklogcheckpoint": "0047_paper_backlog_checkpoint",
    "loans.loantransactionreview": "0043_loan_transaction_review",
    "loans.khatadocumentissue": "0042_khata_label_batches",
    "loans.khatacollateralselection": "0037_khata_custody_settlement",
    "loans.khatainterestperiod": "0035_khata_interest_collection",
    "loans.khatainterestsegment": "0035_khata_interest_collection",
    "loans.khatainterestallocation": "0035_khata_interest_collection",
    "loans.khatapolicyrevision": "0034_khata_opening",
    "loans.khataoperation": "0034_khata_opening",
    "loans.khatacollateralitem": "0034_khata_opening",
    "loans.khatacollateralvaluation": "0034_khata_opening",
    "loans.khatacollateralphoto": "0034_khata_opening",
    "loans.khataseries": "0033_khata_foundation",
    "loans.khataseriesstatuschange": "0041_khata_series_status",
    "loans.khataaccount": "0033_khata_foundation",
    "loans.khataagreementrevision": "0033_khata_foundation",
    "data_portability.guidedopeningbatch": "0016_guidedopeningbatch",
    "loans.auctioneerhandover": "0031_auctioneer_handovers",
    "loans.auctioneerhandoverrevision": "0031_auctioneer_handovers",
    "loans.pledgebook": "0030_pledge_book",
    "loans.pledgebookreview": "0030_pledge_book",
    "loans.pledgebookbatch": "0030_pledge_book",
    "loans.pledgebookentry": "0030_pledge_book",
    "loans.statutoryauctionnotice": "0029_statutory_notices",
    "loans.statutorynoticeevidence": "0029_statutory_notices",
    "orgs.workspacestorageusage": "0010_storage_inventory",
    "loans.loanoriginationsettings": "0028_origination_photo_settings",
    "loans.paperclosuretransition": "0022_paper_closure_transition",
    "party.partyphoto": "0003_party_photo_gallery",
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
