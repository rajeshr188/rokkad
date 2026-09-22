"""Bounded Party staging and identity; all rows are directly Workspace-owned."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenancy.models import WorkspaceOwnedModel


class WorkspaceNamespace(WorkspaceOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace"], name="port_namespace_workspace_uniq")]


class LegacyMediaReceipt(WorkspaceOwnedModel):
    """Immutable source admission receipt, retained after mutable Party media removal."""
    source_system = models.CharField(max_length=120)
    source_id = models.CharField(max_length=120)
    evidence_sha256 = models.CharField(max_length=64)
    source_evidence = models.JSONField()
    target = models.JSONField()
    imported_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    imported_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "source_system", "source_id"], name="port_legacy_media_source_uniq")]


class ImportBatch(WorkspaceOwnedModel):
    class State(models.TextChoices):
        NEEDS_MAPPING = "NEEDS_MAPPING", "Needs mapping"
        READY = "READY", "Ready"
        COMPLETED = "COMPLETED", "Completed"
        CANCELLED = "CANCELLED", "Cancelled"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source_name = models.CharField(max_length=255)
    source_type = models.CharField(max_length=8)
    source_system = models.CharField(max_length=120)
    source_sha256 = models.CharField(max_length=64)
    source_bytes = models.PositiveIntegerField()
    contract_version = models.CharField(max_length=32, default="party-master/1")
    headers = models.JSONField(default=list)
    mapping = models.JSONField(default=dict)
    mapping_preset = models.ForeignKey("MappingPresetVersion", null=True, on_delete=models.PROTECT, related_name="batches")
    summary = models.JSONField(default=dict)
    approval_digest = models.CharField(max_length=64, blank=True)
    revision = models.PositiveIntegerField(default=0)
    state = models.CharField(max_length=20, choices=State.choices, default=State.NEEDS_MAPPING)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    committed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True)


class PartyIdentity(WorkspaceOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    party = models.OneToOneField("party.Party", on_delete=models.PROTECT, related_name="exchange_identity")
    created_at = models.DateTimeField(auto_now_add=True)


class SourceIdentity(WorkspaceOwnedModel):
    source_system = models.CharField(max_length=120)
    external_id = models.CharField(max_length=255)
    identity = models.ForeignKey(PartyIdentity, on_delete=models.PROTECT, related_name="sources")
    accepted_digest = models.CharField(max_length=64)
    local_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "source_system", "external_id"], name="port_source_identity_uniq")]


class ImportRow(WorkspaceOwnedModel):
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="rows")
    source_row = models.PositiveIntegerField()
    raw = models.JSONField(default=dict)
    canonical = models.JSONField(default=dict)
    issues = models.JSONField(default=list)
    external_id = models.CharField(max_length=255, blank=True)
    disposition = models.CharField(max_length=16, default="UNVALIDATED")
    # Completed rows are permanent result/provenance records, guarded in PostgreSQL.
    identity = models.ForeignKey(PartyIdentity, null=True, on_delete=models.PROTECT, related_name="import_rows")
    child_identity = models.ForeignKey("ChildIdentity", null=True, on_delete=models.PROTECT, related_name="import_rows")
    committed_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "batch", "source_row"], name="port_batch_row_uniq")]


class ChildIdentity(WorkspaceOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    parent = models.ForeignKey(PartyIdentity, on_delete=models.PROTECT, related_name="children")
    profile = models.CharField(max_length=32)
    related_parent = models.ForeignKey(PartyIdentity, null=True, on_delete=models.PROTECT, related_name="incoming_children")
    relationship = models.OneToOneField("party.PartyRelationship", null=True, on_delete=models.SET_NULL, related_name="exchange_identity")
    role = models.OneToOneField("party.PartyRole", null=True, on_delete=models.SET_NULL, related_name="exchange_identity")
    identifier = models.OneToOneField("party.PartyIdentifier", null=True, on_delete=models.SET_NULL, related_name="exchange_identity")
    contact = models.OneToOneField("party.PartyContactMethod", null=True, on_delete=models.SET_NULL, related_name="exchange_identity")
    address = models.OneToOneField("party.PartyAddress", null=True, on_delete=models.SET_NULL, related_name="exchange_identity")
    created_at = models.DateTimeField(auto_now_add=True)


class ChildSourceIdentity(WorkspaceOwnedModel):
    profile = models.CharField(max_length=32)
    source_system = models.CharField(max_length=120)
    external_id = models.CharField(max_length=255)
    identity = models.ForeignKey(ChildIdentity, on_delete=models.PROTECT, related_name="sources")
    accepted_digest = models.CharField(max_length=64)
    local_digest = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace", "profile", "source_system", "external_id"], name="port_child_source_uniq")]


class MappingPresetVersion(WorkspaceOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    name = models.CharField(max_length=80)
    version = models.PositiveIntegerField()
    profile = models.CharField(max_length=32)
    source_system = models.CharField(max_length=120)
    headers = models.JSONField(default=list)
    mapping = models.JSONField(default=dict)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["workspace", "name", "version"], name="port_preset_version_uniq"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="port_preset_positive_version"),
        ]


class ImportBundle(WorkspaceOwnedModel):
    """Immutable source/group evidence; progress is derived from the six batches."""
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source_namespace = models.UUIDField()
    source_sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    master = models.OneToOneField(ImportBatch, null=True, on_delete=models.PROTECT, related_name="master_bundle")
    contact = models.OneToOneField(ImportBatch, null=True, on_delete=models.PROTECT, related_name="contact_bundle")
    address = models.OneToOneField(ImportBatch, null=True, on_delete=models.PROTECT, related_name="address_bundle")
    identifier = models.OneToOneField(ImportBatch, null=True, on_delete=models.PROTECT, related_name="identifier_bundle")
    role = models.OneToOneField(ImportBatch, null=True, on_delete=models.PROTECT, related_name="role_bundle")
    relationship = models.OneToOneField(ImportBatch, null=True, on_delete=models.PROTECT, related_name="relationship_bundle")

    PROFILE_FIELDS = ("master", "contact", "address", "identifier", "role", "relationship")

    def profile_batches(self):
        return [(f"party-{field}/1", getattr(self, field)) for field in self.PROFILE_FIELDS]

    def receipt_entries(self):
        return [(profile, str(batch.public_id) if batch else None) for profile, batch in self.profile_batches()]

    @property
    def progress(self):
        states = [batch.state for _, batch in self.profile_batches() if batch]
        if not states:
            return "Empty"
        if all(state == "COMPLETED" for state in states):
            return "Completed"
        if all(state == "CANCELLED" for state in states):
            return "Cancelled"
        if any(state in {"COMPLETED", "CANCELLED"} for state in states):
            return "Partly finished"
        return "Awaiting review"


class LoanHistoryBatch(WorkspaceOwnedModel):
    profile = models.CharField(max_length=32, default="loan-history/1",
        choices=[("loan-history/1", "Complete history"), ("legacy-opening/1", "Legacy opening")])
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source_sha256 = models.CharField(max_length=64)
    document = models.JSONField()
    mapping = models.JSONField(default=dict)
    preview = models.JSONField(default=dict)
    state = models.CharField(max_length=12, default="STAGED", choices=[(s, s) for s in ("STAGED", "READY", "COMPLETED", "CANCELLED")])
    approval_digest = models.CharField(max_length=64, blank=True)
    result = models.ForeignKey("loans.HistoricalLoanImport", null=True, on_delete=models.PROTECT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)


class LoanArchiveBatch(WorkspaceOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    source_sha256 = models.CharField(max_length=64)
    document = models.JSONField()
    state = models.CharField(max_length=12, default="STAGED",
        choices=[(s, s) for s in ("STAGED", "COMPLETED", "CANCELLED")])
    result = models.ForeignKey("loans.HistoricalLoanEvidence", null=True, on_delete=models.PROTECT, related_name="batches")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
