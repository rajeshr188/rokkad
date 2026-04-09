from django.urls import path
from django.views.generic.dates import ArchiveIndexView

from . import views
from .models import GivenLoan
from .views import custody_views

app_name = "girvi"

CORE_URLPATTERNS = [
    # Notifications and utility endpoints
    path(
        "girvi/loan/<int:pk>/notify/",
        views.create_loan_notification,
        name="girvi_loan_notice",
    ),
    path("deletemultiple/", views.deleteLoan, name="girvi_loan_deletemultiple"),
    path(
        "girvi/loan/get-interestrate/",
        views.get_interestrate,
        name="girvi_get_interestrate",
    ),
    path("girvi/notice/", views.notice, name="notice"),
    path("girvi/outdatedloans/notify/", views.notify_print, name="girvi_create_notice"),
    path("girvi/outdatedloans/notify-v2/", views.notify_print_v2, name="girvi_create_notice_v2"),
    path(
        "loans/today/",
        views.loans_created_on_day_excluding_current_month,
        name="loans_created_on_day_excluding_current_month",
    ),
]

ARCHIVE_URLPATTERNS = [
    path(
        "loan_archive/",
        ArchiveIndexView.as_view(
            model=GivenLoan,
            date_field="loan_date",
            template_name="girvi/loan_archive.html",
            allow_empty=True,
            paginate_by=10,
            allow_future=True,
        ),
        name="loan_archive",
    ),
    path("<int:year>/", views.LoanYearArchiveView.as_view(), name="loan_year_archive"),
    path(
        "<int:year>/<int:month>/",
        views.LoanMonthArchiveView.as_view(month_format="%m"),
        name="archive_month_numeric",
    ),
    path(
        "<int:year>/<str:month>/",
        views.LoanMonthArchiveView.as_view(),
        name="archive_month",
    ),
    path(
        "<int:year>/<str:month>/<int:day>/",
        views.LoanDayArchiveView.as_view(),
        name="archive_day",
    ),
    path(
        "<int:year>/week/<int:week>/",
        views.LoanWeekArchiveView.as_view(),
        name="archive_week",
    ),
    path("today/", views.LoanTodayArchiveView.as_view(), name="archive_today"),
]

LICENSE_URLPATTERNS = [
    path("girvi/license/", views.license_list, name="girvi_license_list"),
    path(
        "girvi/license/create/",
        views.LicenseCreateView.as_view(),
        name="girvi_license_create",
    ),
    path(
        "girvi/license/detail/<int:pk>/",
        views.LicenseDetailView.as_view(),
        name="girvi_license_detail",
    ),
    path(
        "girvi/license/update/<int:pk>/",
        views.LicenseUpdateView.as_view(),
        name="girvi_license_update",
    ),
    path(
        "girvi/license/<int:pk>/delete/",
        views.LicenseDeleteView.as_view(),
        name="girvi_license_delete",
    ),
    path(
        "girvi/license/expiry-report/",
        views.LicenseExpiryReportView.as_view(),
        name="girvi_license_expiry_report",
    ),
    path(
        "girvi/license/<int:license_id>/document/upload/",
        views.LicenseDocumentUploadView.as_view(),
        name="girvi_license_document_upload",
    ),
    path(
        "girvi/license/document/<int:pk>/delete/",
        views.LicenseDocumentDeleteView.as_view(),
        name="girvi_license_document_delete",
    ),
    path(
        "girvi/license/<int:pk>/renew/",
        views.LicenseRenewalView.as_view(),
        name="girvi_license_renewal",
    ),
]

LOAN_URLPATTERNS = [
    path("", views.girvi_dashboard, name="girvi_dashboard"),
    path("girvi/loan/<int:pk>/split/", views.split_loan_items, name="split_loan_items"),
    path("girvi/loan/merge/", views.merge_loans, name="merge_loans"),
    path("girvi/loan/", views.loan_list, name="girvi_loan_list"),
    # Loan detail tab endpoints (HTMX lazy-loaded)
    path(
        "girvi/loan/detail/<int:pk>/items/",
        views.loan_detail_items_tab,
        name="loan_detail_items_tab",
    ),
    path(
        "girvi/loan/detail/<int:pk>/payments/",
        views.loan_detail_payments_tab,
        name="loan_detail_payments_tab",
    ),
    path(
        "girvi/loan/detail/<int:pk>/transactions/",
        views.loan_detail_transactions_tab,
        name="loan_detail_transactions_tab",
    ),
    path(
        "girvi/loan/detail/<int:pk>/statement/",
        views.loan_detail_statement_tab,
        name="loan_detail_statement_tab",
    ),
    path(
        "girvi/loan/detail/<int:pk>/notices/",
        views.loan_detail_notices_tab,
        name="loan_detail_notices_tab",
    ),
    path(
        "girvi/loan/detail/<int:pk>/release/",
        views.loan_detail_release_tab,
        name="loan_detail_release_tab",
    ),
    path("girvi/loan/table/", views.loan_table_partial, name="loan_table_partial"),
    path("girvi/loan/renew/<int:pk>/", views.loan_renew, name="girvi_loan_renew"),
    path(
        "girvi/loan/create/preview/",
        views.loan_create_preview,
        name="girvi_loan_create_preview",
    ),
    path("girvi/loan/create/", views.loan_create, name="girvi_loan_create"),
    path(
        "girvi/loan/create/customer/<int:customer_pk>/",
        views.loan_create_for_customer,
        name="girvi_loan_create_for_customer",
    ),
    path("girvi/loan/detail/<int:pk>/", views.loan_detail, name="girvi_loan_detail"),
    path("girvi/loan/detail/<int:pk>/pdf", views.print_loan, name="loan_pdf"),
    path(
        "girvi/loan/update/<int:pk>/",
        views.loan_update,
        name="girvi_loan_update",
    ),
    path(
        "girvi/loan/<int:pk>/delete/",
        views.loan_delete,
        name="girvi_loan_delete",
    ),
    path("girvi/loan/print_labels/", views.print_labels, name="print_labels"),
    path("girvi/loan/print_label/", views.print_label, name="print_label"),
    path(
        "girvi/loan-report/", views.LoanTimeSeriesReport.as_view(), name="loan_report"
    ),
    path(
        "girvi/loanbycustomer/",
        views.LoanByCustomerReport.as_view(),
        name="loan_by_customer",
    ),
    path(
        "girvi/loancrosstab/", views.LoanCrosstabReport.as_view(), name="loan_crosstab"
    ),
    path(
        "girvi/series-report/",
        views.SeriesReport.as_view(),
        name="series_report",
    ),
    path(
        "girvi/license-report/",
        views.LicenseReport.as_view(),
        name="license_report",
    ),
    path(
        "girvi/loan-crosstab/",
        views.LoanCrosstabReport.as_view(),
        name="loan_crosstab_legacy",
    ),
    path(
        "girvi/loan-listreport/", views.LoanListReport.as_view(), name="Loan_list_repot"
    ),
    path(
        "girvi/loan-listreport/",
        views.LoanListReport.as_view(),
        name="girvi_loan_list_report",
    ),
    path("girvi/ledger/", views.export_loans_to_excel, name="girvi_ledger"),
    path("girvi/unreleased/", views.generate_unreleased_pdf, name="girvi_unreleased"),
    path("girvi/grid-template/", views.print_grid_template, name="girvi_grid_template"),
    path(
        "loan/<int:pk>/transition/", views.loan_transition_view, name="loan_transition"
    ),
    path(
        "loan/<int:pk>/transition/",
        views.loan_transition_view,
        name="girvi_loan_transition",
    ),
]

LOAN_ITEM_URLPATTERNS = [
    path(
        "loan/item/<int:pk>/detail", views.loanitem_detail, name="girvi_loanitem_detail"
    ),
    path(
        "loan/repledged_item/<int:pk>/",
        views.repledgedloanitem_detail,
        name="repledgedloanitem_detail",
    ),
    path(
        "loan/<int:parent_id>/item/<int:id>/delete/",
        views.loanitem_delete,
        name="girvi_loanitem_delete",
    ),
    path(
        "loan/<int:parent_id>/repledgedloanitem/<int:id>/delete/",
        views.repledged_loanitem_delete,
        name="repledgedloanitem_delete",
    ),
    path("loanitems/", views.loanitem_list, name="loanitem_list"),
    path(
        "loanitem/<int:parent_id>/create/",
        views.loanitem_create_update,
        name="loanitem_create_update",
    ),
    path(
        "loanitem/<int:parent_id>/update/<int:id>/",
        views.loanitem_create_update,
        name="loanitem_create_update",
    ),
    path(
        "loanitem/<int:item_id>/pictures/",
        views.loanitem_picture_modal,
        name="loanitem_picture_modal",
    ),
    path(
        "loanitem/<int:item_id>/picture/add/",
        views.loanitem_picture_add,
        name="loanitem_picture_add",
    ),
    path(
        "loanitem/<int:item_id>/picture/<int:pic_id>/delete/",
        views.loanitem_picture_delete,
        name="loanitem_picture_delete",
    ),
]

PAYMENT_URLPATTERNS = [
    path(
        "girvi/loanpayment/<int:pk>/create/",
        views.loan_payment_create_view,
        name="girvi_loanpayment_create",
    ),
    path(
        "girvi/takenloan/<int:pk>/payment/create/",
        views.taken_loan_payment_create_view,
        name="takenloan_payment_create",
    ),
]

SERIES_URLPATTERNS = [
    path("girvi/series/", views.series_list, name="girvi_series_list"),
    path(
        "girvi/series/create/",
        views.series_new,
        name="girvi_series_create",
    ),
    path(
        "girvi/series/detail/<int:pk>/",
        views.series_detail,
        name="girvi_series_detail",
    ),
    path(
        "girvi/series/update/<int:pk>/",
        views.series_edit,
        name="girvi_series_update",
    ),
    path(
        "girvi/series/<int:pk>/delete/",
        views.series_delete,
        name="girvi_series_delete",
    ),
    path(
        "girvi/series/<int:pk>/activate",
        views.activate_series,
        name="girvi_activate_series",
    ),
    path(
        "girvi/series/next-loanid/", views.next_loanid, name="girvi_series_next_loanid"
    ),
]

TEMPLATE_URLPATTERNS = [
    path(
        "girvi/templates/",
        views.LoanTemplateListView.as_view(),
        name="girvi_template_list",
    ),
    path(
        "girvi/templates/download-pack/",
        views.download_template_pack,
        name="girvi_template_download_pack",
    ),
    path(
        "girvi/templates/create/",
        views.LoanTemplateCreateView.as_view(),
        name="girvi_template_create",
    ),
    path(
        "girvi/templates/<int:pk>/",
        views.LoanTemplateDetailView.as_view(),
        name="girvi_template_detail",
    ),
    path(
        "girvi/templates/<int:pk>/edit/",
        views.LoanTemplateUpdateView.as_view(),
        name="girvi_template_update",
    ),
    path(
        "girvi/templates/<int:pk>/delete/",
        views.LoanTemplateDeleteView.as_view(),
        name="girvi_template_delete",
    ),
    path(
        "girvi/templates/<int:pk>/preview/",
        views.LoanTemplatePreviewView.as_view(),
        name="girvi_template_preview",
    ),
    path(
        "girvi/templates/<int:pk>/preview-pdf/",
        views.template_preview_pdf,
        name="girvi_template_preview_pdf",
    ),
    path(
        "girvi/templates/<int:pk>/test-print/",
        views.template_test_print,
        name="girvi_template_test_print",
    ),
    path(
        "girvi/templates/<int:pk>/set-default/",
        views.template_set_default,
        name="girvi_template_set_default",
    ),
    path(
        "girvi/templates/<int:pk>/clone/",
        views.template_clone,
        name="girvi_template_clone",
    ),
    path(
        "girvi/templates/<int:pk>/toggle-active/",
        views.template_toggle_active,
        name="girvi_template_toggle_active",
    ),
    path(
        "girvi/templates/<int:pk>/create-starter-frames/",
        views.template_create_starter_frames,
        name="girvi_template_create_starter_frames",
    ),
    path(
        "girvi/templates/<int:template_pk>/frames/create/",
        views.template_frame_create,
        name="girvi_template_frame_create",
    ),
    path(
        "girvi/templates/<int:template_pk>/frames/<int:pk>/edit/",
        views.template_frame_update,
        name="girvi_template_frame_update",
    ),
    path(
        "girvi/templates/<int:template_pk>/frames/<int:pk>/delete/",
        views.template_frame_delete,
        name="girvi_template_frame_delete",
    ),
]

RELEASE_URLPATTERNS = [
    path("girvi/release/", views.release_list, name="girvi_release_list"),
    path(
        "girvi/release/create/",
        views.release_create,
        name="girvi_release_create",
    ),
    path(
        "girvi/release/<int:pk>/create/",
        views.release_create,
        name="girvi_release_create",
    ),
    path(
        "girvi/release/detail/<int:pk>/",
        views.release_detail,
        name="girvi_release_detail",
    ),
    path(
        "girvi/release/update/<int:pk>/",
        views.release_update_view,
        name="girvi_release_update",
    ),
    path(
        "girvi/release/<int:pk>/delete",
        views.ReleaseDeleteView.as_view(),
        name="girvi_release_delete",
    ),
    path("girvi/bulk_release/", views.bulk_release, name="bulk_release"),
    path(
        "girvi/bulk_release/details/",
        views.get_release_details,
        name="bulk_release_details",
    ),
    path(
        "submit_release_formset/",
        views.submit_release_formset,
        name="submit_release_formset",
    ),
    path("girvi/release/<int:pk>/form_h/", views.form_h, name="release_form_h"),
]

CUSTODY_URLPATTERNS = [
    path(
        "girvi/custody/items/<int:item_id>/custody/",
        custody_views.item_custody_status,
        name="item_custody_status",
    ),
    path(
        "girvi/custody/loans/<int:loan_id>/custody/",
        custody_views.loan_custody_summary,
        name="loan_custody_summary",
    ),
    path(
        "girvi/custody/items/<int:item_id>/return-from-lender/",
        custody_views.return_item_from_lender,
        name="return_item_from_lender",
    ),
    path(
        "girvi/custody/loans/<int:loan_id>/return-from/<int:taken_loan_id>/",
        custody_views.return_all_items_from_lender,
        name="return_all_items_from_lender",
    ),
    path(
        "girvi/custody/loans/<int:loan_id>/release/check/",
        custody_views.release_loan_check_custody,
        name="release_loan_check_custody",
    ),
    path(
        "girvi/custody/loans/<int:loan_id>/release/with-return/",
        custody_views.release_loan_with_return,
        name="release_loan_with_return",
    ),
    path(
        "girvi/custody/repledge/create/",
        custody_views.create_repledge_select_items,
        name="create_repledge_select_items",
    ),
    path(
        "girvi/custody/repledge/create/with-items/",
        custody_views.create_repledge_with_items,
        name="create_repledge_with_items",
    ),
    path(
        "girvi/custody/taken-loans/<int:loan_id>/collateral/",
        custody_views.taken_loan_collateral_detail,
        name="taken_loan_collateral_detail",
    ),
    path(
        "girvi/custody/taken-loans/<int:loan_id>/return-collateral/",
        custody_views.return_taken_loan_collateral,
        name="return_taken_loan_collateral",
    ),
    path(
        "girvi/custody/reports/repledge-history/",
        custody_views.repledge_history_report,
        name="repledge_history_report",
    ),
    path(
        "girvi/custody/api/loans/<int:loan_id>/check-custody/",
        custody_views.api_check_release_custody,
        name="api_check_release_custody",
    ),
    path(
        "girvi/custody/api/items/<int:item_id>/custody/",
        custody_views.api_item_custody_status,
        name="api_item_custody_status",
    ),
]

STATEMENT_URLPATTERNS = [
    path("statements/", views.verification_session_list, name="statement_list"),
    path("statements/", views.verification_session_list, name="girvi_statement_list"),
    path(
        "statement/create/",
        views.verification_session_create,
        name="statement_create",
    ),
    path(
        "statement/create/",
        views.verification_session_create,
        name="girvi_statement_create",
    ),
    path(
        "statement/<int:pk>/toggle_complete",
        views.verification_session_toggle,
        name="statement_update",
    ),
    path(
        "statement/<int:pk>/toggle_complete",
        views.verification_session_toggle,
        name="girvi_statement_update",
    ),
    path(
        "statement/<int:pk>/detail/",
        views.verification_session_detail,
        name="statement_detail",
    ),
    path(
        "statement/<int:pk>/delete/",
        views.statement_delete,
        name="statement_delete",
    ),
    path(
        "statement/<int:pk>/statement_item/create/",
        views.statement_item_add,
        name="statement_item_create",
    ),
    path(
        "statement_item/<int:pk>/delete/",
        views.statement_item_delete,
        name="statement_item_delete",
    ),
]

STORAGE_BOX_URLPATTERNS = [
    path("storage_boxes/", views.list_storage_boxes, name="storage_boxes"),
    path("storage_boxes/", views.list_storage_boxes, name="girvi_storage_boxes"),
    path("storage_boxes/add/", views.add_storage_box, name="add_storage_box"),
    path("storage_boxes/add/", views.add_storage_box, name="girvi_add_storage_box"),
    path(
        "storage_boxes/update/<int:pk>/",
        views.update_storage_box,
        name="update_storage_box",
    ),
    path(
        "storage_boxes/update/<int:pk>/",
        views.update_storage_box,
        name="girvi_update_storage_box",
    ),
    path(
        "storage_boxes/delete/<int:pk>/",
        views.delete_storage_box,
        name="delete_storage_box",
    ),
    path(
        "storage_boxes/delete/<int:pk>/",
        views.delete_storage_box,
        name="girvi_delete_storage_box",
    ),
]

urlpatterns = [
    *CORE_URLPATTERNS,
    *ARCHIVE_URLPATTERNS,
    *LICENSE_URLPATTERNS,
    *LOAN_URLPATTERNS,
    *LOAN_ITEM_URLPATTERNS,
    *PAYMENT_URLPATTERNS,
    *SERIES_URLPATTERNS,
    *TEMPLATE_URLPATTERNS,
    *RELEASE_URLPATTERNS,
    *CUSTODY_URLPATTERNS,
    *STATEMENT_URLPATTERNS,
    *STORAGE_BOX_URLPATTERNS,
]
