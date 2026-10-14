"""Account enrollment and directly Workspace-owned communication preferences."""
import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.tenancy.models import WorkspaceOwnedModel


class Contact(models.Model):
    class State(models.TextChoices):
        PENDING = "pending", "Pairing pending"
        VERIFIED = "verified", "Account paired"
        PAUSED = "paused", "Paused"
        DISCONNECTED = "disconnected", "Disconnected"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    phone = models.CharField(max_length=16, blank=True)
    state = models.CharField(max_length=16, choices=State.choices, default=State.PENDING)
    revision = models.PositiveIntegerField(default=1)
    challenge_hash = models.CharField(max_length=64, blank=True)
    challenge_expires_at = models.DateTimeField(null=True, blank=True)
    challenge_issued_at = models.DateTimeField(null=True, blank=True)
    match_failures = models.PositiveSmallIntegerField(default=0)
    issue_window_at = models.DateTimeField(default=timezone.now)
    issue_count = models.PositiveSmallIntegerField(default=0)
    verified_at = models.DateTimeField(null=True, blank=True)
    sender_fingerprint = models.CharField(max_length=64, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def masked_phone(self):
        return ("•••• " + self.phone[-4:]) if self.phone else "No number connected"

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("phone",), condition=~models.Q(phone=""),
                                    name="platform_wa_phone_unique"),
            models.CheckConstraint(condition=models.Q(revision__gte=1),
                                   name="platform_wa_contact_revision_positive"),
            models.CheckConstraint(condition=~models.Q(state="verified") | (
                ~models.Q(phone="") & models.Q(verified_at__isnull=False) &
                ~models.Q(sender_fingerprint="") & models.Q(challenge_hash="")),
                name="platform_wa_verified_evidence"),
        ]


class Preference(WorkspaceOwnedModel):
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT)
    contact_revision = models.PositiveIntegerField()
    setup = models.BooleanField(default=False)
    subscription = models.BooleanField(default=False)
    service = models.BooleanField(default=False)
    language = models.CharField(max_length=5, default="en")
    consent_version = models.CharField(max_length=64)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("workspace",), name="platform_wa_workspace_preference_unique"),
            models.CheckConstraint(condition=models.Q(language="en"), name="platform_wa_language_supported"),
            models.CheckConstraint(condition=models.Q(contact_revision__gte=1),
                                   name="platform_wa_preference_revision_positive"),
        ]


class ConsentEvent(WorkspaceOwnedModel):
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    contact_revision = models.PositiveIntegerField()
    setup = models.BooleanField()
    subscription = models.BooleanField()
    service = models.BooleanField()
    consent_version = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=("id", "workspace"), name="platform_wa_consent_scope")]


class ContactEvent(models.Model):
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT)
    kind = models.CharField(max_length=24)
    revision = models.PositiveIntegerField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()


class Suppression(models.Model):
    phone_hash = models.CharField(max_length=64, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()


class InboundReceipt(models.Model):
    message_id = models.CharField(max_length=255, unique=True)
    outcome = models.CharField(max_length=24, default="ignored")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()


class SetupRequest(WorkspaceOwnedModel):
    """Explicit, reviewed owner request; never an onboarding-completion flag."""
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT)
    contact_revision = models.PositiveIntegerField()
    consent = models.ForeignKey(ConsentEvent, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [
            models.UniqueConstraint(fields=("workspace", "contact", "contact_revision"),
                                    name="platform_wa_setup_once"),
            models.UniqueConstraint(fields=("id", "workspace"), name="platform_wa_setup_scope"),
        ]


class Delivery(WorkspaceOwnedModel):
    """Immutable source intent; capture-only history is never promoted to sending."""
    class Purpose(models.TextChoices):
        SETUP = "setup", "Requested setup assistance"
        TRIAL = "trial", "Trial confirmation"
        PAID = "paid", "Subscription payment confirmation"
        ENDING = "ending", "Trial ending reminder"
        SERVICE = "service", "Reviewed service announcement"

    contact = models.ForeignKey(Contact, on_delete=models.PROTECT)
    contact_revision = models.PositiveIntegerField()
    consent = models.ForeignKey(ConsentEvent, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    recipient_phone = models.CharField(max_length=16)
    workspace_name = models.CharField(max_length=255)
    purpose = models.CharField(max_length=10, choices=Purpose.choices)
    setup_request = models.OneToOneField(SetupRequest, null=True, blank=True, on_delete=models.PROTECT)
    trial_event = models.OneToOneField("subscriptions.SubscriptionEvent", null=True, blank=True,
                                      on_delete=models.PROTECT)
    invoice = models.OneToOneField("subscriptions.Invoice", null=True, blank=True, on_delete=models.PROTECT)
    reminder = models.OneToOneField("TrialReminder", null=True, blank=True, on_delete=models.PROTECT)
    announcement_target = models.OneToOneField("AnnouncementTarget", null=True, blank=True, on_delete=models.PROTECT)
    template_revision = models.CharField(max_length=64)
    sender_fingerprint = models.CharField(max_length=64)
    source_fingerprint = models.CharField(max_length=64)
    provider_mode = models.CharField(max_length=4, blank=True)
    capture_only = models.BooleanField(default=True, editable=False)
    source_recorded_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()

    @property
    def masked_phone(self):
        return "•••• " + self.recipient_phone[-4:]

    class Meta:
        default_permissions = ()
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(condition=(
                models.Q(purpose="setup", setup_request__isnull=False, trial_event__isnull=True,
                         invoice__isnull=True, reminder__isnull=True, announcement_target__isnull=True, provider_mode="") |
                models.Q(purpose="trial", setup_request__isnull=True, trial_event__isnull=False,
                         invoice__isnull=True, provider_mode="") |
                models.Q(purpose="paid", setup_request__isnull=True, trial_event__isnull=True,
                         invoice__isnull=False, reminder__isnull=True, announcement_target__isnull=True, provider_mode__in=("test", "live"))
                | models.Q(purpose="ending", setup_request__isnull=True, trial_event__isnull=True,
                    invoice__isnull=True, reminder__isnull=False, announcement_target__isnull=True, provider_mode="")
                | models.Q(purpose="service", setup_request__isnull=True, trial_event__isnull=True,
                    invoice__isnull=True, reminder__isnull=True, announcement_target__isnull=False, provider_mode="")
            ), name="platform_wa_delivery_one_source"),
            models.UniqueConstraint(fields=("id", "workspace"), name="platform_wa_delivery_scope"),
            models.CheckConstraint(condition=models.Q(contact_revision__gte=1),
                                   name="platform_wa_delivery_revision"),
            models.CheckConstraint(condition=models.Q(expires_at__gt=models.F("created_at")),
                                   name="platform_wa_delivery_expiry"),
        ]


class Attempt(WorkspaceOwnedModel):
    class Outcome(models.TextChoices):
        CLAIMED = "claimed", "Claimed"
        ACCEPTED = "accepted", "Accepted by Meta"
        REJECTED = "rejected", "Rejected by Meta"
        UNKNOWN = "unknown", "Acceptance unknown"
        CANCELLED = "cancelled", "Cancelled before request"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    delivery = models.ForeignKey(Delivery, on_delete=models.PROTECT, related_name="attempts")
    number = models.PositiveSmallIntegerField()
    claimed_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True, blank=True)
    phone_id = models.CharField(max_length=64)
    waba_id = models.CharField(max_length=64)
    sender_fingerprint = models.CharField(max_length=64)
    transport_fingerprint = models.CharField(max_length=64)
    content_fingerprint = models.CharField(max_length=64)
    template_name = models.CharField(max_length=128)
    language = models.CharField(max_length=10)
    outcome = models.CharField(max_length=12, choices=Outcome.choices, default=Outcome.CLAIMED)
    provider_message_id = models.CharField(max_length=255, blank=True)
    retryable = models.BooleanField(default=False)
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    diagnostic = models.CharField(max_length=64, blank=True)

    class Meta:
        default_permissions = ()
        ordering = ("number",)
        constraints = [
            models.UniqueConstraint(fields=("delivery", "number"), name="platform_wa_attempt_number"),
            models.UniqueConstraint(fields=("id", "workspace"), name="platform_wa_attempt_scope"),
            models.UniqueConstraint(fields=("phone_id", "provider_message_id"),
                condition=~models.Q(provider_message_id=""), name="platform_wa_attempt_provider_id"),
            models.CheckConstraint(condition=models.Q(number__gte=1, number__lte=3), name="platform_wa_attempt_bound"),
            models.CheckConstraint(condition=(
                models.Q(outcome="claimed", finished_at__isnull=True, provider_message_id="", retryable=False) |
                models.Q(outcome="accepted", finished_at__isnull=False,
                         provider_message_id__startswith="wamid.", retryable=False) |
                models.Q(outcome="rejected", finished_at__isnull=False, provider_message_id="") |
                models.Q(outcome__in=("unknown", "cancelled"), finished_at__isnull=False,
                         provider_message_id="", retryable=False)
            ), name="platform_wa_attempt_outcome"),
            models.CheckConstraint(condition=models.Q(finished_at__isnull=True) |
                models.Q(finished_at__gte=models.F("claimed_at")), name="platform_wa_attempt_time"),
        ]


class ProviderReceipt(models.Model):
    """Global authenticated, minimal evidence; unmatched IDs do not imply scope."""
    class Status(models.TextChoices):
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        READ = "read", "Read"
        FAILED = "failed", "Failed"
        DELETED = "deleted", "Deleted"

    event_digest = models.CharField(max_length=64, unique=True)
    phone_id = models.CharField(max_length=64)
    waba_id = models.CharField(max_length=64)
    provider_message_id = models.CharField(max_length=255)
    recipient_hash = models.CharField(max_length=64)
    status = models.CharField(max_length=10, choices=Status.choices)
    provider_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    error_codes = models.JSONField(default=list)
    pricing_category = models.CharField(max_length=32, blank=True)
    pricing_model = models.CharField(max_length=24, blank=True)
    billable = models.BooleanField(null=True, blank=True)

    class Meta:
        default_permissions = ()
        indexes = [models.Index(fields=("phone_id", "provider_message_id"), name="platform_wa_receipt_lookup")]
        constraints = [models.CheckConstraint(condition=models.Q(status__in=("sent", "delivered", "read", "failed", "deleted")),
                                              name="platform_wa_receipt_status")]


class ReceiptLink(WorkspaceOwnedModel):
    attempt = models.ForeignKey(Attempt, on_delete=models.PROTECT, related_name="receipt_links")
    receipt = models.OneToOneField(ProviderReceipt, on_delete=models.PROTECT, related_name="match")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()


class TrialReminder(WorkspaceOwnedModel):
    trial_event = models.OneToOneField("subscriptions.SubscriptionEvent", on_delete=models.PROTECT)
    trial_end = models.DateTimeField()
    stage = models.CharField(max_length=16, default="final_three")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=("id", "workspace"), name="platform_wa_reminder_scope"),
            models.CheckConstraint(condition=models.Q(stage="final_three"), name="platform_wa_reminder_stage")]


class Announcement(models.Model):
    """Immutable global platform publication; scoped target evidence below."""
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    purpose = models.CharField(max_length=16)  # maintenance or incident
    text = models.CharField(max_length=700)
    revision = models.CharField(max_length=64)
    impact_start = models.DateTimeField()
    impact_end = models.DateTimeField()
    expires_at = models.DateTimeField()
    urgent = models.BooleanField(default=False)
    affected_workspaces = models.JSONField()
    review_digest = models.CharField(max_length=64, unique=True)
    configuration_fingerprint = models.CharField(max_length=64)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(purpose__in=("maintenance", "incident")), name="platform_wa_announcement_purpose"),
            models.CheckConstraint(condition=models.Q(impact_end__gt=models.F("impact_start"), expires_at__gt=models.F("created_at")), name="platform_wa_announcement_dates")]


class AnnouncementTarget(WorkspaceOwnedModel):
    announcement = models.ForeignKey(Announcement, on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    contact = models.ForeignKey(Contact, on_delete=models.PROTECT)
    contact_revision = models.PositiveIntegerField()
    consent = models.ForeignKey(ConsentEvent, on_delete=models.PROTECT)
    representative = models.BooleanField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=("announcement", "workspace"), name="platform_wa_announcement_target"),
            models.UniqueConstraint(fields=("announcement", "owner"), condition=models.Q(representative=True), name="platform_wa_announcement_owner_once"),
            models.UniqueConstraint(fields=("id", "workspace"), name="platform_wa_announcement_scope")]


class BudgetDay(models.Model):
    """Global platform aggregate. No Workspace business data or recipient number."""
    day = models.DateField(unique=True)
    policy_fingerprint = models.CharField(max_length=64)
    platform_limit = models.PositiveSmallIntegerField()
    contact_limit = models.PositiveSmallIntegerField()
    spend_limit = models.DecimalField(max_digits=14, decimal_places=6)
    reserved_count = models.PositiveSmallIntegerField(default=0)
    reserved_amount = models.DecimalField(max_digits=14, decimal_places=6, default=0)
    pricing_hold = models.BooleanField(default=False)

    class Meta:
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=models.Q(platform_limit__gte=1, platform_limit__lte=100,
            contact_limit__gte=1, contact_limit__lte=5, spend_limit__gt=0, reserved_count__lte=models.F("platform_limit"),
            reserved_amount__gte=0, reserved_amount__lte=models.F("spend_limit")), name="platform_wa_budget_limits")]


class ContactDay(models.Model):
    budget = models.ForeignKey(BudgetDay, on_delete=models.PROTECT)
    phone_hash = models.CharField(max_length=64)
    reserved_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=("budget", "phone_hash"), name="platform_wa_contact_day"),
            models.CheckConstraint(condition=models.Q(reserved_count__lte=5), name="platform_wa_contact_day_bound")]


class Reservation(WorkspaceOwnedModel):
    """One conservative count/spend reservation per HTTP attempt, never released."""
    attempt = models.OneToOneField(Attempt, on_delete=models.PROTECT, related_name="reservation")
    delivery = models.ForeignKey(Delivery, on_delete=models.PROTECT)
    budget = models.ForeignKey(BudgetDay, on_delete=models.PROTECT)
    phone_hash = models.CharField(max_length=64)
    amount = models.DecimalField(max_digits=14, decimal_places=6)
    tariff = models.JSONField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [models.UniqueConstraint(fields=("id", "workspace"), name="platform_wa_reservation_scope"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="platform_wa_reservation_positive")]


class CostEvidence(WorkspaceOwnedModel):
    """Callback-based tariff estimate, never a provider invoice or loan posting."""
    reservation = models.ForeignKey(Reservation, on_delete=models.PROTECT, related_name="cost_evidence")
    receipt = models.OneToOneField(ProviderReceipt, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=14, decimal_places=6, null=True)
    known = models.BooleanField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()
        constraints = [models.CheckConstraint(condition=(models.Q(known=True, amount__gte=0) | models.Q(known=False, amount__isnull=True)), name="platform_wa_cost_known")]
