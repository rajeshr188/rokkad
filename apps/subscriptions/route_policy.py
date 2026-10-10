"""Reviewed read routes. GET alone is not evidence that an action is read-only."""

READ_ROUTES = {
    "workspace_slug_dashboard",
    "workspace_slug_parties", "workspace_slug_party_detail", "workspace_slug_loans",
    "workspace_slug_loan_list", "workspace_slug_loan_table", "workspace_slug_loan_detail",
    "workspace_slug_loan_detail_items", "workspace_slug_loan_detail_payments",
    "workspace_slug_loan_detail_transactions", "workspace_slug_rates",
    "workspace_loans:pawn_loan_list", "workspace_loans:pawn_loan_detail",
    "workspace_loans:pawn_collateral_list", "workspace_loans:pawn_release_list",
    "workspace_loans:pawn_release_detail", "workspace_loans:release_batch_list",
    "workspace_loans:paper_closure_guide", "workspace_loans:paper_closure_csv",
    "workspace_loans:release_batch_detail", "workspace_loans:pawn_loan_reports",
    "workspace_loans:pawn_loan_report_export", "workspace_loans:pawn_party_statement",
    "workspace_loans:pawn_party_statement_export", "workspace_loans:pawn_collateral_photo_document",
    "workspace_loans:pawn_collateral_label_pdf", "workspace_loans:pawn_collateral_scan",
    "workspace_loans:pawn_storage_location_scan",
    "workspace_loans:pawn_loan_ticket_pdf", "workspace_loans:pawn_loan_kfs_schedule_pdf",
    "workspace_loans:pawn_repayment_receipt_pdf", "workspace_loans:pawn_release_memo_pdf",
    "workspace_loans:pawn_loan_auction_notice_pdf", "workspace_loans:pawn_loan_auction_recovery_pdf",
    "workspace_loans:pawn_loan_renewal_pdf", "workspace_loans:document_issue_list",
    "workspace_loans:document_issue_detail", "workspace_loans:document_issue_artifact",
    "workspace_party:party_list", "workspace_party:party_detail",
    "workspace_rates:rate_list", "workspace_rates:rate_detail",
    "workspace_rates:ratesource_list", "workspace_rates:ratesource_detail",
    "workspace_rates:historical_rate",
    "workspace_portability:archive_list", "workspace_portability:archive_detail",
    "workspace_portability:archive_attachment", "workspace_portability:archive_export",
    "workspace_portability:loan_export", "workspace_portability:export",
}


def read_route_allowed(view_name, method):
    # These exports intentionally require POST + CSRF, but do not mutate business data.
    if method == "POST" and view_name in {
        "workspace_portability:loan_export", "workspace_portability:archive_export",
        "workspace_portability:export",
    }:
        return True
    return method in {"GET", "HEAD"} and view_name in READ_ROUTES


# Only configuration is available to the canonical owner before subscription
# activation. Do not use a setup-path prefix: that namespace also hosts lending,
# funding, notices and imports.
INITIAL_SETUP_ROUTES = {
    "workspace_slug_settings_setup", "workspace_settings_setup",
    "workspace_slug_settings_setup_state", "workspace_settings_setup_state",
    "workspace_update", "workspace_settings_preferences",
    "workspace_slug_settings_preferences", "workspace_slug_settings_profile",
    "workspace_slug_settings_numbering",
    "workspace_loans:license_list", "workspace_loans:license_create",
    "workspace_loans:license_detail", "workspace_loans:license_update",
    "workspace_loans:license_renew", "workspace_loans:license_verify",
    "workspace_loans:license_revision_document", "workspace_loans:license_register_pdf",
    "workspace_loans:license_expire", "workspace_loans:license_activate",
    "workspace_loans:series_create", "workspace_loans:series_update",
    "workspace_loans:pawn_economics_setup", "workspace_loans:interest_policy_help",
    "workspace_loans:origination_settings", "workspace_loans:loan_workflow_settings",
    "workspace_loans:loan_product_list", "workspace_loans:loan_product_seed_defaults",
    "workspace_loans:loan_product_version_create", "workspace_loans:loan_product_version_activate",
    "workspace_loans:loan_product_version_retire",
    "workspace_rates:rate_list", "workspace_rates:rate_detail",
    "workspace_rates:rate_create", "workspace_rates:rate_update",
    "workspace_rates:ratesource_list", "workspace_rates:ratesource_detail",
    "workspace_rates:ratesource_create", "workspace_rates:ratesource_update",
    "workspace_slug_rates", "workspace_slug_rate_detail",
    "workspace_slug_rate_sources", "workspace_slug_rate_source_detail",
    "workspace_loans:document_layout_list", "workspace_loans:document_layout_guide",
    "workspace_loans:document_layout_create", "workspace_loans:document_layout_import",
    "workspace_loans:document_layout_detail", "workspace_loans:document_layout_designer",
    "workspace_loans:document_layout_overlay_designer", "workspace_loans:document_layout_overlay_background",
    "workspace_loans:document_layout_update", "workspace_loans:document_layout_asset_add",
    "workspace_loans:document_layout_clone", "workspace_loans:document_layout_publish",
    "workspace_loans:document_layout_assign", "workspace_loans:document_layout_retire",
    "workspace_loans:document_layout_preview", "workspace_loans:document_layout_export",
    "workspace_loans:ticket_template_use",
    "workspace_loans:document_print_profile_list", "workspace_loans:document_print_profile_create",
    "workspace_loans:document_print_profile_detail", "workspace_loans:document_print_profile_update",
    "workspace_loans:document_print_profile_clone", "workspace_loans:document_print_profile_publish",
    "workspace_loans:document_print_profile_assign", "workspace_loans:document_print_profile_retire",
    "workspace_loans:document_print_profile_preview",
}


def initial_setup_route_allowed(view_name, method):
    return method in {"GET", "HEAD", "POST"} and view_name in INITIAL_SETUP_ROUTES
