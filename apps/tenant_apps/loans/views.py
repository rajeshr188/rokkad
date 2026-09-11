"""Compatibility imports for Loans URLs and existing Python callers.

Feature handlers live in web/; keep their decorated functions and route names stable.
"""

from apps.tenant_apps.loans.web.communication_actions import pawn_communication_consent

from apps.tenant_apps.loans.web.communication_policy_actions import (
    pawn_communication_policy,
)

from apps.tenant_apps.loans.web.funding import (
    funding_loan_agreement_pdf,
    funding_loan_read_console,
    funding_loan_read_detail,
    funding_loan_repayment_receipt_pdf,
    funding_loan_return_receipt_pdf,
    funding_loan_statement_pdf,
)

from apps.tenant_apps.loans.web.operations import (
    pawn_loan_notice_list,
    pawn_operations_console,
    pawn_operations_runbook,
    pawn_risk_portfolio,
    pawn_risk_whatsapp_pilot,
)

from apps.tenant_apps.loans.web.reports import (
    pawn_loan_report_export,
    pawn_loan_reports,
    pawn_party_statement,
)

from apps.tenant_apps.loans.web.risk_actions import pawn_risk_borrower_notice_create

from apps.tenant_apps.loans.web.funding_actions import (
    funding_loan_begin_settlement,
    funding_loan_close,
    funding_loan_draft_activate,
    funding_loan_draft_cancel,
    funding_loan_draft_create,
    funding_loan_draft_inputs,
    funding_loan_repayment,
    funding_loan_return_collateral,
    funding_loan_reverse_event,
    funding_loan_reverse_pledge,
    funding_loan_reverse_return,
)

from apps.tenant_apps.loans.web.license_setup import (
    license_list,
    license_register_pdf,
    license_detail,
    license_expiry_notice_create,
    license_create,
    license_update,
    license_renew,
    license_revision_document,
    license_expire,
    license_activate,
    series_create,
    series_update,
    _license_for_workspace,
)

from apps.tenant_apps.loans.web.document_assets import _revision_assets

from apps.tenant_apps.loans.web.print_profile_setup import (
    document_print_profile_list,
    document_print_profile_create,
    document_print_profile_detail,
    document_print_profile_update,
    document_print_profile_clone,
    document_print_profile_publish,
    document_print_profile_assign,
    document_print_profile_retire,
    document_print_profile_preview,
)

from apps.tenant_apps.loans.web.economic_setup import pawn_economics_setup

from apps.tenant_apps.loans.web.product_setup import (
    loan_product_list,
    loan_product_seed_defaults,
    loan_product_version_activate,
    loan_product_version_create,
    loan_product_version_retire,
)

from apps.tenant_apps.loans.web.pawn_draft_actions import (
    get_pawn_draft_readiness,
    pawn_collateral_photo_add,
    pawn_loan_approve,
    pawn_loan_cancel,
    pawn_loan_create,
    pawn_loan_reopen,
    pawn_loan_split,
    pawn_loan_update,
)

from apps.tenant_apps.loans.web.pawn_financial_actions import (
    pawn_loan_accrue,
    pawn_loan_capitalize,
    pawn_loan_disburse,
    pawn_loan_repay,
    pawn_loan_reverse_event,
)

from apps.tenant_apps.loans.web.pawn_release_actions import (
    pawn_loan_release_full,
    pawn_loan_release_partial,
)

from apps.tenant_apps.loans.web.pawn_custody_actions import (
    pawn_collateral_storage_transfer,
    pawn_physical_verification_complete,
    pawn_physical_verification_discrepancy_notice,
    pawn_physical_verification_resolve,
    pawn_storage_location_create,
)

from apps.tenant_apps.loans.web.pawn_notice_actions import (
    pawn_loan_notice_create,
    pawn_loan_notice_retry,
)

from apps.tenant_apps.loans.web.pawn_auction_actions import (
    pawn_loan_auction_cancel,
    pawn_loan_auction_complete,
    pawn_loan_auction_initiate,
    pawn_loan_auction_reverse,
    pawn_loan_auction_start,
)

from apps.tenant_apps.loans.web.pawn_renewal_actions import (
    pawn_loan_renew,
    pawn_loan_renewal_reverse,
)

from apps.tenant_apps.loans.web.document_layout_setup import (
    _OVERLAY_PAGE_DIMENSIONS_MM,
    _document_revision,
    _fit_overlay_geometry,
    _preview_document_payload,
    document_layout_asset_add,
    document_layout_assign,
    document_layout_clone,
    document_layout_create,
    document_layout_designer,
    document_layout_detail,
    document_layout_diagnostics,
    document_layout_export,
    document_layout_guide,
    document_layout_import,
    document_layout_list,
    document_layout_overlay_background,
    document_layout_overlay_designer,
    document_layout_preview,
    document_layout_publish,
    document_layout_retire,
    document_layout_update,
)

from apps.tenant_apps.loans.web.document_issues import (
    _document_issue,
    document_issue_artifact,
    document_issue_detail,
    document_issue_list,
)

from apps.tenant_apps.loans.web.loan_documents import (
    _configurable_document_response,
    _issued_document_response,
    _pawn_auction_for_workspace,
    _pawn_renewal_for_workspace,
    pawn_loan_auction_notice_pdf,
    pawn_loan_auction_recovery_pdf,
    pawn_loan_kfs_schedule_pdf,
    pawn_loan_renewal_pdf,
    pawn_loan_ticket_pdf,
    pawn_release_memo_pdf,
    pawn_repayment_receipt_pdf,
)

from apps.tenant_apps.loans.web.pawn_reads import (
    _event_rows,
    _primary_action,
    pawn_loan_detail,
    pawn_loan_list,
)

from apps.tenant_apps.loans.web.pawn_custody_views import (
    _PENDING_STORAGE_ITEM_SESSION_KEY,
    pawn_collateral_label_pdf,
    pawn_collateral_photo_document,
    pawn_collateral_scan,
    pawn_physical_verification_detail,
    pawn_physical_verification_list,
    pawn_storage_location_label,
    pawn_storage_location_list,
    pawn_storage_location_scan,
)

from apps.tenant_apps.loans.web.risk_refresh import (
    _risk_portfolio_redirect,
    _risk_refresh_date,
    pawn_risk_refresh_batch,
    pawn_risk_refresh_one,
)

from apps.tenant_apps.loans.web.pawn_setup_actions import (
    pawn_loan_transfer_setup,
)

from apps.tenant_apps.loans.web.operational_notice_actions import (
    operational_notice_retry,
)

from apps.tenant_apps.loans.web.pawn_read_helpers import (
    _can_administer,
    _can_manage_storage,
    _pawn_loan_for_workspace,
)
