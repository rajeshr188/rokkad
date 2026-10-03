"""Explicit reference inventory. New FileFields fail coverage closed until classified."""
from collections import defaultdict

from django.apps import apps
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db.models import FileField

from apps.orgs.models import Company
from apps.tenancy.context import workspace_context


# No filename inference: ownership comes only from persisted Workspace records.
FILE_FIELDS = {
    ("loans.pledgebookbatch", "artifact"): "issued_documents",
    ("loans.statutoryauctionnotice", "artifact"): "issued_documents",
    ("loans.statutorynoticeevidence", "attachment"): "notification_artifacts",
    ("party.party", "profile_photo"): "customer_photos",
    ("party.partyphoto", "file"): "customer_photos",
    ("party.partydocument", "file"): "customer_documents",
    ("loans.pawncollateralphoto", "file"): "collateral_photos",
    ("loans.khatacollateralphoto", "file"): "collateral_photos",
    ("loans.historicalloanattachment", "file"): "historical_evidence",
    ("loans.loanlicenserevision", "supporting_document"): "licence_documents",
    ("loans.loandocumentasset", "file"): "template_assets",
    ("loans.loandocumentissue", "artifact"): "issued_documents",
    ("loans.khatadocumentissue", "artifact"): "issued_documents",
    ("notify_v2.notificationartifact", "file"): "notification_artifacts",
    ("orgs.company", "logo"): "workspace_logos",
    ("accounts.userprofile", "profile_picture"): "platform_avatars",
}


def validate_coverage():
    actual = {(model._meta.label_lower, field.name) for model in apps.get_models()
              for field in model._meta.concrete_fields if isinstance(field, FileField)}
    if actual != set(FILE_FIELDS):
        raise ValidationError("Media reference registry requires review before reconciliation.")
    if any(apps.get_model(label)._meta.get_field(name).storage is not default_storage for label, name in actual):
        raise ValidationError("A media field uses separate storage; its inventory scope requires review.")
    return sorted(f"{model}.{field}" for model, field in actual)


def collect_references(workspace_ids):
    references = defaultdict(set)

    def add(name, workspace_id, category):
        if name:
            # Preserve exact keys, including legacy names; never normalize two keys into one.
            if not isinstance(name, str) or len(name) > 1024 or name.startswith("/") or ".." in name.split("/"):
                raise ValidationError("A stored media reference requires operator review.")
            references[name].add((workspace_id, category))
            if len(references) > 500000:
                raise ValidationError("Reference inventory exceeded its reviewed bound.")

    for workspace_id in workspace_ids:
        with workspace_context(workspace_id):
            for (label, field), category in FILE_FIELDS.items():
                if label in {"orgs.company", "accounts.userprofile"}:
                    continue
                model = apps.get_model(label)
                for name in model._base_manager.filter(workspace_id=workspace_id).values_list(field, flat=True).iterator():
                    add(name, workspace_id, category)
            # Historical ticket photo references survive replacement of the current photo.
            issue = apps.get_model("loans.LoanDocumentIssue")
            for snapshot in issue.objects.filter(workspace_id=workspace_id).values_list("source_snapshot", flat=True).iterator():
                if snapshot:
                    for value in snapshot.get("media", {}).values():
                        add(value.get("file_name"), workspace_id, "historical_evidence")
            # Admission receipts remain even after mutable attachment rows are removed.
            receipt = apps.get_model("data_portability.LegacyMediaReceipt")
            for target in receipt.objects.filter(workspace_id=workspace_id).values_list("target", flat=True).iterator():
                for field in ("file_name", "document_name", "profile_name"):
                    add(target.get(field), workspace_id, "historical_evidence")
    for workspace_id, name in Company.all_objects.values_list("pk", "logo").iterator():
        add(name, workspace_id, "workspace_logos")
    for name in apps.get_model("accounts.UserProfile").objects.values_list("profile_picture", flat=True).iterator():
        # A user's selected workspace is a navigation preference, not file ownership.
        add(name, None, "platform_avatars")
    return references
