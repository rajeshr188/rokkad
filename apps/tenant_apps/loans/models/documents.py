"""Tenant-owned, versioned configurable document persistence."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from .core import LoanLicense, LoanSeries, current_tenant_workspace_id


DOCUMENT_KIND_CHOICES = (
    ("loan_ticket", "Loan ticket"),
    ("repayment_receipt", "Repayment receipt"),
    ("release_memo", "Release memo"),
    ("auction_notice", "Auction notice"),
    ("auction_recovery", "Auction recovery memo"),
    ("renewal", "Renewal agreement"),
)


def document_asset_upload(instance, filename):
    return f"loans/documents/workspace-{instance.workspace_id}/layout-{instance.revision.layout_id}/revision-{instance.revision_id}/assets/{filename}"


def document_issue_upload(instance, filename):
    return f"loans/documents/workspace-{instance.workspace_id}/issues/{instance.document_type}/{instance.source_type}-{instance.source_id}/{filename}"


class LoanDocumentLayout(models.Model):
    workspace = models.ForeignKey("orgs.Company", on_delete=models.PROTECT, related_name="loan_document_layouts")
    document_type = models.CharField(max_length=32, choices=DOCUMENT_KIND_CHOICES)
    name = models.CharField(max_length=100)
    is_retired = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="loan_document_layouts_created")

    class Meta:
        ordering = ("document_type", "name", "pk")
        constraints = [models.UniqueConstraint(fields=("workspace", "document_type", "name"), name="loans_doc_layout_name_uniq")]

    def clean(self):
        active = current_tenant_workspace_id()
        if active and self.workspace_id != active:
            raise ValidationError({"workspace": "Document layout workspace must match the active tenant."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LoanDocumentLayoutRevision(models.Model):
    class State(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        PUBLISHED = "PUBLISHED", "Published"
        RETIRED = "RETIRED", "Retired"

    layout = models.ForeignKey(LoanDocumentLayout, on_delete=models.PROTECT, related_name="revisions")
    version = models.PositiveIntegerField()
    state = models.CharField(max_length=12, choices=State.choices, default=State.DRAFT, db_index=True)
    definition = models.JSONField(default=dict)
    content_hash = models.CharField(max_length=64, blank=True)
    validation_result = models.JSONField(default=dict, blank=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="loan_document_revisions_created")

    class Meta:
        ordering = ("layout_id", "version")
        constraints = [
            models.UniqueConstraint(fields=("layout", "version"), name="loans_doc_revision_version_uniq"),
            models.CheckConstraint(condition=Q(version__gt=0), name="loans_doc_revision_version_positive"),
        ]

    @property
    def workspace_id(self):
        return self.layout.workspace_id

    def clean(self):
        active = current_tenant_workspace_id()
        if active and self.layout_id and self.layout.workspace_id != active:
            raise ValidationError("Document revision must belong to the active tenant.")
        if self.definition and self.layout_id and self.definition.get("document_type") != self.layout.document_type:
            raise ValidationError({"definition": "Layout definition document type does not match its layout."})
        if self.pk:
            previous = type(self).objects.filter(pk=self.pk).values("state", "definition", "content_hash").first()
            if previous and previous["state"] != self.State.DRAFT:
                if self.definition != previous["definition"] or self.content_hash != previous["content_hash"]:
                    raise ValidationError("Published document revisions are immutable.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LoanDocumentAsset(models.Model):
    revision = models.ForeignKey(LoanDocumentLayoutRevision, on_delete=models.PROTECT, related_name="assets")
    workspace = models.ForeignKey("orgs.Company", on_delete=models.PROTECT, related_name="loan_document_assets")
    key = models.CharField(max_length=64)
    kind = models.CharField(max_length=16, choices=(("IMAGE", "Image"), ("BACKGROUND", "Background")))
    mime_type = models.CharField(max_length=64)
    file = models.FileField(upload_to=document_asset_upload)
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveIntegerField()
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    page_count = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="loan_document_assets_created")

    class Meta:
        constraints = [models.UniqueConstraint(fields=("revision", "key"), name="loans_doc_asset_key_uniq")]

    def clean(self):
        errors = {}
        if self.revision_id and self.workspace_id != self.revision.layout.workspace_id:
            errors["workspace"] = "Asset workspace must match its layout revision."
        if self.revision_id and self.revision.state != LoanDocumentLayoutRevision.State.DRAFT and not self.pk:
            errors["revision"] = "Assets can be added only to draft revisions."
        if self.pk and self.revision_id and self.revision.state != LoanDocumentLayoutRevision.State.DRAFT:
            errors["revision"] = "Assets on published revisions are immutable."
        active = current_tenant_workspace_id()
        if active and self.workspace_id != active:
            errors["workspace"] = "Asset workspace must match the active tenant."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LoanDocumentLayoutAssignment(models.Model):
    workspace = models.ForeignKey("orgs.Company", on_delete=models.PROTECT, related_name="loan_document_assignments")
    document_type = models.CharField(max_length=32, choices=DOCUMENT_KIND_CHOICES)
    revision = models.ForeignKey(LoanDocumentLayoutRevision, on_delete=models.PROTECT, related_name="assignments")
    license = models.ForeignKey(LoanLicense, null=True, blank=True, on_delete=models.PROTECT, related_name="document_layout_assignments")
    series = models.ForeignKey(LoanSeries, null=True, blank=True, on_delete=models.PROTECT, related_name="document_layout_assignments")
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="loan_document_assignments_created")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("workspace", "document_type"), condition=Q(is_active=True, license__isnull=True, series__isnull=True), name="loans_doc_assign_workspace_uniq"),
            models.UniqueConstraint(fields=("workspace", "document_type", "license"), condition=Q(is_active=True, license__isnull=False, series__isnull=True), name="loans_doc_assign_license_uniq"),
            models.UniqueConstraint(fields=("workspace", "document_type", "series"), condition=Q(is_active=True, series__isnull=False), name="loans_doc_assign_series_uniq"),
        ]

    def clean(self):
        errors = {}
        active = current_tenant_workspace_id()
        if active and self.workspace_id != active:
            errors["workspace"] = "Assignment workspace must match the active tenant."
        if self.revision_id:
            if self.revision.state != LoanDocumentLayoutRevision.State.PUBLISHED:
                errors["revision"] = "Only published revisions can be assigned."
            elif self.revision.layout.workspace_id != self.workspace_id or self.revision.layout.document_type != self.document_type:
                errors["revision"] = "Assigned revision scope does not match the assignment."
        if self.license_id and self.license.workspace_id != self.workspace_id:
            errors["license"] = "Assigned license belongs to another workspace."
        if self.series_id:
            if self.series.license.workspace_id != self.workspace_id:
                errors["series"] = "Assigned series belongs to another workspace."
            if self.license_id and self.series.license_id != self.license_id:
                errors["series"] = "Assigned series does not belong to the selected license."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class LoanDocumentIssue(models.Model):
    class Kind(models.TextChoices):
        OFFICIAL = "OFFICIAL", "Official"
        REGENERATED = "REGENERATED", "Regenerated"

    workspace = models.ForeignKey("orgs.Company", on_delete=models.PROTECT, related_name="loan_document_issues")
    document_type = models.CharField(max_length=32, choices=DOCUMENT_KIND_CHOICES)
    issue_kind = models.CharField(max_length=12, choices=Kind.choices, default=Kind.OFFICIAL)
    source_type = models.CharField(max_length=64)
    source_id = models.CharField(max_length=64)
    source_fingerprint = models.CharField(max_length=128)
    revision = models.ForeignKey(LoanDocumentLayoutRevision, null=True, blank=True, on_delete=models.PROTECT, related_name="issues")
    fixed_renderer_version = models.CharField(max_length=64, blank=True)
    payload_schema_version = models.PositiveIntegerField()
    payload_hash = models.CharField(max_length=64)
    layout_hash = models.CharField(max_length=64, blank=True)
    asset_hashes = models.JSONField(default=dict, blank=True)
    pdf_hash = models.CharField(max_length=64)
    artifact = models.FileField(upload_to=document_issue_upload)
    prior_issue = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="regenerated_issues")
    issued_at = models.DateTimeField(auto_now_add=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="loan_document_issues_created")

    class Meta:
        ordering = ("-issued_at", "-pk")
        indexes = [models.Index(fields=("workspace", "document_type", "source_type", "source_id"), name="loans_doc_issue_source_idx")]
        constraints = [
            models.UniqueConstraint(
                fields=("workspace", "document_type", "source_type", "source_id", "source_fingerprint"),
                condition=Q(issue_kind="OFFICIAL"),
                name="loans_doc_official_issue_uniq",
            )
        ]

    def clean(self):
        errors = {}
        active = current_tenant_workspace_id()
        if active and self.workspace_id != active:
            errors["workspace"] = "Document issue workspace must match the active tenant."
        if self.revision_id and (self.revision.layout.workspace_id != self.workspace_id or self.revision.layout.document_type != self.document_type):
            errors["revision"] = "Issue revision scope does not match the source document."
        if self.issue_kind == self.Kind.REGENERATED and not self.prior_issue_id:
            errors["prior_issue"] = "Regenerated issues require a prior issue."
        if self.prior_issue_id and self.prior_issue.workspace_id != self.workspace_id:
            errors["prior_issue"] = "Prior issue belongs to another workspace."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Issued document evidence is immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)
