from django.urls import path
from apps.orgs.route_adapters import workspace_view
from . import views, loan_setup, loan_history_views, legacy_opening_views, loan_archive_views

app_name = "workspace_portability"
urlpatterns = [
    path("history-archive/", workspace_view(loan_archive_views.listing), name="archive_list"),
    path("history-archive/upload/", workspace_view(loan_archive_views.upload), name="archive_upload"),
    path("history-archive/schema/", workspace_view(loan_archive_views.schema), name="archive_schema"),
    path("history-archive/staged/<uuid:batch_id>/", workspace_view(loan_archive_views.review), name="archive_batch"),
    path("history-archive/<uuid:evidence_id>/", workspace_view(loan_archive_views.detail), name="archive_detail"),
    path("history-archive/<uuid:evidence_id>/export/", workspace_view(loan_archive_views.export), name="archive_export"),
    path("openings/", workspace_view(legacy_opening_views.listing), name="opening_list"),
    path("openings/<uuid:batch_id>/", workspace_view(legacy_opening_views.review), name="opening_batch"),
    path("loans/", workspace_view(loan_history_views.upload), name="loan_upload"),
    path("loans/schema/", workspace_view(loan_history_views.schema), name="loan_schema"),
    path("loans/<uuid:batch_id>/", workspace_view(loan_history_views.review), name="loan_batch"),
    path("export/loans/<int:loan_id>/", workspace_view(loan_history_views.export), name="loan_export"),
    path("loans/prepare/", workspace_view(loan_setup.prepare), name="loan_setup"),
    path("party/bundles/<uuid:bundle_id>/", workspace_view(views.bundle_review), name="bundle_history"),
    path("party/bundle/", workspace_view(views.bundle_review), name="bundle"),
    path("party/", workspace_view(views.upload), name="upload"),
    path("party/<uuid:batch_id>/", workspace_view(views.batch_detail), name="batch"),
    path("export/party-master/", workspace_view(views.export), name="export"),
]
