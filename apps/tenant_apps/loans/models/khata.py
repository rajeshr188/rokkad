"""Khata identities and immutable opening, custody and interest evidence."""
import uuid

from django.conf import settings
from django.core.validators import MaxLengthValidator, RegexValidator
from django.db import models
from django.db.models import F, Q
from django_cleanup import cleanup

from apps.tenancy.models import WorkspaceOwnedModel


def khata_document_path(instance, filename):
    return f"loans/khata/{instance.workspace_id}/documents/{instance.account_id}/{instance.request_key}.pdf"


@cleanup.ignore
class KhataDocumentIssue(WorkspaceOwnedModel):
    """Immutable source snapshot and exact private PDF; never a financial event."""
    account = models.ForeignKey("KhataAccount", on_delete=models.PROTECT, related_name="document_issues")
    source_operation = models.ForeignKey("KhataOperation", null=True, blank=True, on_delete=models.PROTECT, related_name="document_issues")
    kind = models.CharField(max_length=9, choices=(("OPERATION", "Source document"), ("STATEMENT", "Dated statement"), ("LABEL", "Collateral label")))
    as_of = models.DateField()
    source_sequence = models.PositiveIntegerField()
    request_key = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    payload = models.JSONField()
    payload_sha256 = models.CharField(max_length=64)
    renderer_version = models.CharField(max_length=24)
    artifact = models.FileField(upload_to=khata_document_path, max_length=255)
    artifact_sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.UniqueConstraint(fields=("workspace", "request_key"), name="khata_document_request_uniq"),
            models.CheckConstraint(condition=Q(byte_size__gt=0), name="khata_document_bytes_positive"),
            models.CheckConstraint(condition=Q(kind="OPERATION", source_operation__isnull=False)
                | Q(kind__in=("STATEMENT", "LABEL"), source_operation__isnull=True), name="khata_document_source_valid"),
        ]


class KhataSeries(WorkspaceOwnedModel):
    license = models.ForeignKey("loans.LoanLicense", null=True, blank=True, on_delete=models.PROTECT, related_name="khata_series")
    code = models.CharField(max_length=32)
    name = models.CharField(max_length=120)
    prefix = models.CharField(max_length=16, validators=[RegexValidator(r"^[A-Z][A-Z-]{0,15}$")])
    width = models.PositiveSmallIntegerField(default=5)
    next_number = models.PositiveBigIntegerField(default=1, editable=False)
    maximum_number = models.PositiveBigIntegerField(default=99999)
    has_issued_number = models.BooleanField(default=False, editable=False)
    is_active = models.BooleanField(default=True)
    retired_at = models.DateTimeField(null=True, blank=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("workspace", "code"), name="khata_series_code_uniq"),
            models.UniqueConstraint(fields=("workspace", "prefix"), name="khata_series_prefix_uniq"),
            models.CheckConstraint(condition=Q(width__gte=1, width__lte=12), name="khata_series_width_valid"),
            models.CheckConstraint(condition=Q(next_number__gte=1, maximum_number__gte=1, maximum_number__lte=999999999999)
                                   & Q(next_number__lte=F("maximum_number") + 1), name="khata_series_counter_valid"),
            models.CheckConstraint(condition=Q(prefix__regex=r"^[A-Z][A-Z-]{0,15}$"), name="khata_series_prefix_valid"),
            models.CheckConstraint(condition=Q(retired_at__isnull=True) | Q(is_active=False), name="khata_series_retired_inactive"),
        ]

    def __str__(self):
        return f"{self.name} ({self.prefix})"

    @property
    def lending_status(self):
        return "RETIRED" if self.retired_at else "ACTIVE" if self.is_active else "PAUSED"


class KhataSeriesStatusChange(WorkspaceOwnedModel):
    """Append-only setup evidence, separate from account cash/custody operations."""
    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        PAUSED = "PAUSED", "Paused"
        RETIRED = "RETIRED", "Retired"

    series = models.ForeignKey(KhataSeries, on_delete=models.PROTECT, related_name="status_changes")
    number = models.PositiveIntegerField()
    from_status = models.CharField(max_length=7, choices=Status.choices)
    to_status = models.CharField(max_length=7, choices=Status.choices)
    reason = models.TextField(validators=[MaxLengthValidator(2000)])
    request_key = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ("-number",)
        constraints = [
            models.UniqueConstraint(fields=("workspace", "request_key"), name="khata_series_change_request_uniq"),
            models.UniqueConstraint(fields=("series", "number"), name="khata_series_change_number_uniq"),
            models.CheckConstraint(condition=Q(number__gte=1), name="khata_series_change_number_positive"),
            models.CheckConstraint(condition=Q(from_status="ACTIVE", to_status__in=("PAUSED", "RETIRED"))
                | Q(from_status="PAUSED", to_status__in=("ACTIVE", "RETIRED")), name="khata_series_transition_valid"),
        ]


class KhataAccount(WorkspaceOwnedModel):
    """Identity with a lifecycle projection guarded by source operations."""
    class State(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        APPROVED = "APPROVED", "Approved"
        ACTIVE = "ACTIVE", "Active"
        SETTLED_RETURN_PENDING = "SETTLED_RETURN_PENDING", "Settled, return pending"
        CLOSED = "CLOSED", "Closed"
        CANCELLED = "CANCELLED", "Cancelled"

    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    series = models.ForeignKey(KhataSeries, on_delete=models.PROTECT, related_name="accounts")
    borrower = models.ForeignKey("party.Party", on_delete=models.PROTECT, related_name="khata_accounts")
    account_number = models.CharField(max_length=28, editable=False)
    state = models.CharField(max_length=24, choices=State.choices, default=State.DRAFT)
    opened_on = models.DateField(null=True, blank=True, editable=False)
    settled_on = models.DateField(null=True, blank=True, editable=False)
    request_key = models.UUIDField(editable=False)
    request_sha256 = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    cancelled_at = models.DateTimeField(null=True, blank=True, editable=False)
    cancelled_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    cancellation_reason = models.TextField(blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("workspace", "account_number"), name="khata_account_number_uniq"),
            models.UniqueConstraint(fields=("workspace", "request_key"), name="khata_account_request_uniq"),
            models.CheckConstraint(condition=(Q(state__in=("DRAFT", "APPROVED"), opened_on__isnull=True,
                settled_on__isnull=True, cancelled_at__isnull=True, cancelled_by__isnull=True, cancellation_reason="")
                | Q(state="ACTIVE", opened_on__isnull=False, settled_on__isnull=True, cancelled_at__isnull=True, cancelled_by__isnull=True, cancellation_reason="")
                | Q(state__in=("SETTLED_RETURN_PENDING", "CLOSED"), opened_on__isnull=False, settled_on__gte=F("opened_on"),
                    cancelled_at__isnull=True, cancelled_by__isnull=True, cancellation_reason="") & Q(settled_on__isnull=False)
                | (Q(state="CANCELLED", opened_on__isnull=True, settled_on__isnull=True, cancelled_at__isnull=False, cancelled_by__isnull=False)
                   & ~Q(cancellation_reason=""))), name="khata_account_state_valid"),
        ]


class KhataAgreementRevision(WorkspaceOwnedModel):
    """Append-only proposed terms; saving a proposal is not approval/activation."""
    class Frequency(models.TextChoices):
        MONTHLY = "MONTHLY", "Monthly"
        ANNUAL = "ANNUAL", "Annually"

    account = models.ForeignKey(KhataAccount, on_delete=models.PROTECT, related_name="agreement_revisions")
    number = models.PositiveIntegerField()
    intended_on = models.DateField()
    agreed_limit = models.DecimalField(max_digits=18, decimal_places=2)
    monthly_rate = models.DecimalField(max_digits=10, decimal_places=6)
    ltv = models.DecimalField(max_digits=7, decimal_places=6)
    frequency = models.CharField(max_length=7, choices=Frequency.choices)
    contract_version = models.CharField(max_length=16, default="KHATA-1", editable=False)
    lender_name = models.CharField(max_length=255)
    lender_address = models.TextField(max_length=1000, validators=[MaxLengthValidator(1000)])
    reason = models.TextField()
    request_key = models.UUIDField(editable=False)
    request_sha256 = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ("number",)
        constraints = [
            models.UniqueConstraint(fields=("account", "number"), name="khata_revision_number_uniq"),
            models.UniqueConstraint(fields=("workspace", "request_key"), name="khata_revision_request_uniq"),
            models.CheckConstraint(condition=Q(number__gte=1, agreed_limit__gt=0, monthly_rate__gte=0, ltv__gt=0, ltv__lte=1), name="khata_revision_terms_valid"),
            models.CheckConstraint(condition=Q(frequency__in=("MONTHLY", "ANNUAL"), contract_version="KHATA-1"), name="khata_revision_contract_valid"),
        ]


class KhataPolicyRevision(WorkspaceOwnedModel):
    number = models.PositiveIntegerField()
    exchange = models.CharField(max_length=5, choices=(("WARN", "Warn"), ("BLOCK", "Block")))
    overdue = models.CharField(max_length=5, choices=(("WARN", "Warn"), ("BLOCK", "Block")))
    reason = models.TextField()
    request_key = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("workspace", "number"), name="khata_policy_number_uniq"),
            models.UniqueConstraint(fields=("workspace", "request_key"), name="khata_policy_request_uniq"),
            models.CheckConstraint(condition=Q(number__gte=1, exchange__in=("WARN", "BLOCK"), overdue__in=("WARN", "BLOCK")), name="khata_policy_values_valid"),
        ]


class KhataOperation(WorkspaceOwnedModel):
    class Kind(models.TextChoices):
        APPROVE = "APPROVE", "Approve opening"
        WITHDRAW = "WITHDRAW", "Withdrawal"
        DEPOSIT = "DEPOSIT", "Collateral received"
        RETURN = "RETURN", "Unopened collateral returned"
        PHOTO = "PHOTO", "Collateral photograph"
        ACCRUE = "ACCRUE", "Finalize completed interest periods"
        INTEREST = "INTEREST", "Interest received"
        TERMS_OK = "TERMS_OK", "Approve agreement change"
        REVISE = "REVISE", "Activate agreement change"
        EXCHANGE = "EXCHANGE", "Collateral exchange"
        HANDOVER = "HANDOVER", "Reserved collateral handed over"
        SETTLE = "SETTLE", "Financial settlement"
        CORRECT = "CORRECT", "Compensating correction"

    account = models.ForeignKey(KhataAccount, on_delete=models.PROTECT, related_name="operations")
    sequence = models.PositiveIntegerField()
    kind = models.CharField(max_length=8, choices=Kind.choices)
    business_date = models.DateField()
    amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    interest_amount = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="handovers")
    correction_of = models.OneToOneField("self", null=True, blank=True, on_delete=models.PROTECT, related_name="corrected_by")
    agreement = models.ForeignKey(KhataAgreementRevision, null=True, blank=True, on_delete=models.PROTECT, related_name="operations")
    approval = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="withdrawals")
    item = models.ForeignKey("KhataCollateralItem", null=True, blank=True, on_delete=models.PROTECT, related_name="operations")
    policy = models.ForeignKey(KhataPolicyRevision, null=True, blank=True, on_delete=models.PROTECT, related_name="operations")
    request_key = models.UUIDField()
    request_sha256 = models.CharField(max_length=64)
    evidence = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(fields=("account", "sequence"), name="khata_op_sequence_uniq"),
            models.UniqueConstraint(fields=("workspace", "request_key"), name="khata_op_request_uniq"),
            models.UniqueConstraint(fields=("item",), condition=Q(kind__in=("RETURN", "HANDOVER")), name="khata_item_return_once"),
            models.UniqueConstraint(fields=("agreement",), condition=Q(kind="REVISE"), name="khata_revision_activate_once"),
            models.CheckConstraint(condition=Q(sequence__gte=1) & (
                Q(kind="WITHDRAW", amount__gt=0, agreement__isnull=False, approval__isnull=False, item__isnull=True)
                | Q(kind="APPROVE", amount=0, agreement__isnull=False, approval__isnull=True, item__isnull=True)
                | Q(kind="DEPOSIT", amount=0, agreement__isnull=True, approval__isnull=True, item__isnull=True)
                | Q(kind="ACCRUE", amount=0, agreement__isnull=True, approval__isnull=True, item__isnull=True, policy__isnull=True)
                | Q(kind="INTEREST", amount__gt=0, agreement__isnull=True, approval__isnull=True, item__isnull=True, policy__isnull=True)
                | Q(kind="TERMS_OK", amount=0, agreement__isnull=False, approval__isnull=True, item__isnull=True, policy__isnull=True)
                | Q(kind="REVISE", amount__gte=0, agreement__isnull=False, approval__isnull=False, item__isnull=True, policy__isnull=True)
                | Q(kind="EXCHANGE", amount=0, agreement__isnull=False, approval__isnull=True, item__isnull=True)
                | Q(kind="HANDOVER", amount=0, agreement__isnull=True, approval__isnull=True, item__isnull=False, policy__isnull=True)
                | Q(kind="SETTLE", amount__gte=0, agreement__isnull=False, approval__isnull=True, item__isnull=True, policy__isnull=True)
                | Q(kind="CORRECT", amount__gte=0, approval__isnull=True, item__isnull=True, policy__isnull=True)
                | Q(kind__in=("RETURN", "PHOTO"), amount=0, agreement__isnull=True, approval__isnull=True, item__isnull=False)),
                name="khata_op_shape_valid"),
            models.CheckConstraint(condition=(Q(kind="SETTLE", interest_amount__gte=0) | ~Q(kind="SETTLE") & Q(interest_amount=0))
                & (Q(kind="HANDOVER", parent__isnull=False) | ~Q(kind="HANDOVER") & Q(parent__isnull=True)), name="khata_op_money_parent_valid"),
            models.CheckConstraint(condition=Q(kind="CORRECT", correction_of__isnull=False)
                | ~Q(kind="CORRECT") & Q(correction_of__isnull=True), name="khata_correction_source_valid"),
        ]


class KhataCollateralItem(WorkspaceOwnedModel):
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    account = models.ForeignKey(KhataAccount, on_delete=models.PROTECT, related_name="collateral")
    received_operation = models.OneToOneField(KhataOperation, on_delete=models.PROTECT, related_name="received_item")
    description = models.CharField(max_length=500)
    metal = models.CharField(max_length=6, choices=(("GOLD", "Gold"), ("SILVER", "Silver")))
    quantity = models.PositiveIntegerField()
    gross_weight = models.DecimalField(max_digits=12, decimal_places=3)
    net_weight = models.DecimalField(max_digits=12, decimal_places=3)
    purity = models.DecimalField(max_digits=7, decimal_places=4)
    storage_reference = models.CharField(max_length=160)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(metal__in=("GOLD", "SILVER"), quantity__gte=1,
            net_weight__gt=0, gross_weight__gte=F("net_weight"), purity__gt=0, purity__lte=100), name="khata_item_values_valid")]


class KhataCollateralValuation(WorkspaceOwnedModel):
    item = models.ForeignKey(KhataCollateralItem, on_delete=models.PROTECT, related_name="valuations")
    operation = models.ForeignKey(KhataOperation, on_delete=models.PROTECT, related_name="valuations")
    rate = models.ForeignKey("rates.Rate", on_delete=models.PROTECT, related_name="+")
    value = models.DecimalField(max_digits=18, decimal_places=2)
    rate_evidence = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("operation", "item"), name="khata_valuation_item_uniq"),
            models.CheckConstraint(condition=Q(value__gte=0), name="khata_valuation_nonnegative"),
        ]


class KhataCollateralSelection(WorkspaceOwnedModel):
    """Immutable exchange membership and outgoing reservation; handover is separate."""
    operation = models.ForeignKey(KhataOperation, on_delete=models.PROTECT, related_name="collateral_selections")
    item = models.ForeignKey(KhataCollateralItem, on_delete=models.PROTECT, related_name="selections")
    role = models.CharField(max_length=3, choices=(("IN", "Replacement"), ("OUT", "Reserved for return")))

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("operation", "item"), name="khata_selection_item_uniq"),
            models.CheckConstraint(condition=Q(role__in=("IN", "OUT")), name="khata_selection_role_valid"),
        ]


class KhataInterestPeriod(WorkspaceOwnedModel):
    """Frozen monthly charge; annual collection groups these by due date."""
    account = models.ForeignKey(KhataAccount, on_delete=models.PROTECT, related_name="interest_periods")
    operation = models.ForeignKey(KhataOperation, on_delete=models.PROTECT, related_name="interest_periods")
    index = models.PositiveIntegerField()
    start_on = models.DateField()
    end_on = models.DateField()
    charged_through = models.DateField(null=True, blank=True)
    due_on = models.DateField()
    actual_charge = models.DecimalField(max_digits=18, decimal_places=2)
    minimum_adjustment = models.DecimalField(max_digits=18, decimal_places=2)
    charge = models.DecimalField(max_digits=18, decimal_places=2)
    contract_version = models.CharField(max_length=16, default="KHATA-1", editable=False)

    class Meta:
        ordering = ("index",)
        constraints = [
            models.UniqueConstraint(fields=("account", "index"), name="khata_interest_period_uniq"),
            models.CheckConstraint(condition=Q(end_on__gt=F("start_on"), due_on__gte=F("end_on"),
                actual_charge__gte=0, minimum_adjustment__gte=0, contract_version="KHATA-1")
                & Q(charge=F("actual_charge") + F("minimum_adjustment")), name="khata_interest_period_valid"),
            models.CheckConstraint(condition=Q(charged_through__isnull=True) | Q(charged_through__gte=F("start_on"),
                charged_through__lte=F("end_on")), name="khata_interest_through_valid"),
        ]


class KhataInterestSegment(WorkspaceOwnedModel):
    period = models.ForeignKey(KhataInterestPeriod, on_delete=models.PROTECT, related_name="segments")
    agreement = models.ForeignKey(KhataAgreementRevision, on_delete=models.PROTECT, related_name="interest_segments")
    sequence = models.PositiveIntegerField()
    start_on = models.DateField()
    end_on = models.DateField()
    period_days = models.PositiveSmallIntegerField()
    exact_numerator = models.DecimalField(max_digits=60, decimal_places=0)
    exact_denominator = models.DecimalField(max_digits=60, decimal_places=0)

    class Meta:
        ordering = ("sequence",)
        constraints = [
            models.UniqueConstraint(fields=("period", "sequence"), name="khata_interest_segment_uniq"),
            models.CheckConstraint(condition=Q(sequence__gte=1, end_on__gt=F("start_on"),
                period_days__gte=28, period_days__lte=31, exact_numerator__gte=0,
                exact_denominator__gt=0), name="khata_interest_segment_valid"),
        ]


class KhataInterestAllocation(WorkspaceOwnedModel):
    operation = models.ForeignKey(KhataOperation, on_delete=models.PROTECT, related_name="interest_allocations")
    period = models.ForeignKey(KhataInterestPeriod, on_delete=models.PROTECT, related_name="allocations")
    amount = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("operation", "period"), name="khata_interest_allocation_uniq"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="khata_interest_allocation_positive"),
        ]


def khata_photo_upload_to(instance, filename):
    suffix = "png" if instance.mime_type == "image/png" else "jpg"
    return f"loans/khata/{instance.workspace_id}/{instance.item.public_id}/{uuid.uuid4().hex}.{suffix}"


@cleanup.ignore
class KhataCollateralPhoto(WorkspaceOwnedModel):
    item = models.ForeignKey(KhataCollateralItem, on_delete=models.PROTECT, related_name="photos")
    operation = models.OneToOneField(KhataOperation, on_delete=models.PROTECT, related_name="photo")
    file = models.FileField(upload_to=khata_photo_upload_to, max_length=500)
    sha256 = models.CharField(max_length=64)
    byte_size = models.PositiveIntegerField()
    mime_type = models.CharField(max_length=10)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(byte_size__gte=1, byte_size__lte=10485760,
            mime_type__in=("image/jpeg", "image/png")), name="khata_photo_values_valid")]
