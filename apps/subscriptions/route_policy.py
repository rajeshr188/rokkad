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
