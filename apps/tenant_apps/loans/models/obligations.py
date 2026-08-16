from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Q

from apps.tenant_apps.loans.domain import ObligationComponent
from apps.tenant_apps.loans.models.core import current_tenant_workspace_id, enum_choices


class ImmutableObligationEvidence(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if self.pk and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(f"{type(self).__name__} is immutable.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(f"{type(self).__name__} is immutable and cannot be deleted.")


class RepaymentScheduleVersion(ImmutableObligationEvidence):
    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="repayment_schedule_versions"
    )
    loan = models.ForeignKey(
        "loans.PawnLoan", on_delete=models.PROTECT, related_name="repayment_schedules"
    )
    source_event = models.OneToOneField(
        "loans.PawnLoanEvent",
        on_delete=models.PROTECT,
        related_name="repayment_schedule",
    )
    version = models.PositiveIntegerField(default=1)
    contract_version = models.CharField(max_length=40)
    fingerprint = models.CharField(max_length=64)
    disbursed_on = models.DateField()
    maturity_date = models.DateField()
    principal = models.DecimalField(max_digits=18, decimal_places=4)
    contractual_interest = models.DecimalField(max_digits=18, decimal_places=4)
    rounding_adjustment = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    supersedes = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="superseded_by"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="repayment_schedule_versions_created",
    )

    class Meta:
        ordering = ("loan_id", "version")
        constraints = [
            models.UniqueConstraint(fields=("loan", "version"), name="loans_schedule_loan_version_uniq"),
            models.UniqueConstraint(fields=("loan", "fingerprint"), name="loans_schedule_loan_fingerprint_uniq"),
            models.CheckConstraint(condition=Q(principal__gt=0), name="loans_schedule_principal_positive"),
            models.CheckConstraint(condition=Q(contractual_interest__gte=0), name="loans_schedule_interest_nonnegative"),
            models.CheckConstraint(condition=Q(maturity_date__gte=F("disbursed_on")), name="loans_schedule_dates_valid"),
        ]
        indexes = [models.Index(fields=("workspace", "loan", "version"), name="loans_schedule_workspace_idx")]

    def clean(self):
        super().clean()
        errors = {}
        workspace_id = current_tenant_workspace_id()
        if workspace_id and self.workspace_id != workspace_id:
            errors["workspace"] = "Schedule must belong to the active workspace."
        if self.loan_id and self.workspace_id and self.loan.workspace_id != self.workspace_id:
            errors["loan"] = "Schedule loan must belong to its workspace."
        if self.source_event_id and self.loan_id and self.source_event.loan_id != self.loan_id:
            errors["source_event"] = "Schedule source event must belong to its loan."
        if self.supersedes_id and self.supersedes.loan_id != self.loan_id:
            errors["supersedes"] = "Superseded schedule must belong to the same loan."
        if errors:
            raise ValidationError(errors)


class RepaymentObligation(ImmutableObligationEvidence):
    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="repayment_obligations"
    )
    loan = models.ForeignKey(
        "loans.PawnLoan", on_delete=models.PROTECT, related_name="repayment_obligations"
    )
    schedule_version = models.ForeignKey(
        RepaymentScheduleVersion, on_delete=models.PROTECT, related_name="obligations"
    )
    sequence = models.PositiveIntegerField()
    due_date = models.DateField(db_index=True)
    principal_due = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    interest_due = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    opening_principal = models.DecimalField(max_digits=18, decimal_places=4)
    closing_principal = models.DecimalField(max_digits=18, decimal_places=4)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("due_date", "sequence")
        constraints = [
            models.UniqueConstraint(fields=("schedule_version", "sequence"), name="loans_obligation_schedule_sequence_uniq"),
            models.CheckConstraint(condition=Q(principal_due__gte=0), name="loans_obligation_principal_nonnegative"),
            models.CheckConstraint(condition=Q(interest_due__gte=0), name="loans_obligation_interest_nonnegative"),
            models.CheckConstraint(condition=Q(opening_principal__gte=0), name="loans_obligation_opening_nonnegative"),
            models.CheckConstraint(condition=Q(closing_principal__gte=0), name="loans_obligation_closing_nonnegative"),
            models.CheckConstraint(condition=Q(principal_due__gt=0) | Q(interest_due__gt=0), name="loans_obligation_amount_positive"),
        ]
        indexes = [models.Index(fields=("workspace", "loan", "due_date"), name="loans_obligation_due_idx")]

    def clean(self):
        super().clean()
        errors = {}
        workspace_id = current_tenant_workspace_id()
        if workspace_id and self.workspace_id != workspace_id:
            errors["workspace"] = "Obligation must belong to the active workspace."
        if self.schedule_version_id:
            if self.schedule_version.loan_id != self.loan_id:
                errors["loan"] = "Obligation loan must match its schedule."
            if self.schedule_version.workspace_id != self.workspace_id:
                errors["workspace"] = "Obligation workspace must match its schedule."
        if errors:
            raise ValidationError(errors)


class RepaymentScheduleChangeKind(models.TextChoices):
    TERMINATE = "TERMINATE", "Terminate"
    REACTIVATE = "REACTIVATE", "Reactivate"


class RepaymentScheduleChange(ImmutableObligationEvidence):
    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="repayment_schedule_changes"
    )
    loan = models.ForeignKey(
        "loans.PawnLoan", on_delete=models.PROTECT, related_name="repayment_schedule_changes"
    )
    schedule_version = models.ForeignKey(
        RepaymentScheduleVersion, on_delete=models.PROTECT, related_name="changes"
    )
    source_event = models.OneToOneField(
        "loans.PawnLoanEvent",
        on_delete=models.PROTECT,
        related_name="repayment_schedule_change",
    )
    kind = models.CharField(max_length=12, choices=RepaymentScheduleChangeKind.choices)
    effective_date = models.DateField()
    reason = models.CharField(max_length=120)
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="repayment_schedule_changes_created",
    )

    class Meta:
        ordering = ("effective_date", "pk")
        indexes = [
            models.Index(
                fields=("workspace", "loan", "effective_date"),
                name="loans_schedule_change_idx",
            )
        ]

    def clean(self):
        super().clean()
        errors = {}
        if self.schedule_version_id:
            if self.schedule_version.loan_id != self.loan_id:
                errors["loan"] = "Schedule change loan must match its schedule."
            if self.schedule_version.workspace_id != self.workspace_id:
                errors["workspace"] = "Schedule change workspace must match its schedule."
        if self.source_event_id and self.source_event.loan_id != self.loan_id:
            errors["source_event"] = "Schedule change event must belong to its loan."
        if self.reversal_of_id:
            if self.kind != RepaymentScheduleChangeKind.REACTIVATE:
                errors["kind"] = "A schedule-change reversal must reactivate the schedule."
            if self.reversal_of.kind != RepaymentScheduleChangeKind.TERMINATE:
                errors["reversal_of"] = "Only a termination may be reactivated."
            if self.reversal_of.schedule_version_id != self.schedule_version_id:
                errors["reversal_of"] = "Reactivation must reference the same schedule."
        elif self.kind == RepaymentScheduleChangeKind.REACTIVATE:
            errors["reversal_of"] = "Reactivation requires its termination evidence."
        if errors:
            raise ValidationError(errors)


class ObligationAllocation(ImmutableObligationEvidence):
    workspace = models.ForeignKey(
        "orgs.Company", on_delete=models.PROTECT, related_name="obligation_allocations"
    )
    loan = models.ForeignKey(
        "loans.PawnLoan", on_delete=models.PROTECT, related_name="obligation_allocations"
    )
    source_event = models.ForeignKey(
        "loans.PawnLoanEvent", on_delete=models.PROTECT, related_name="obligation_allocations"
    )
    obligation = models.ForeignKey(
        RepaymentObligation, on_delete=models.PROTECT, related_name="allocations"
    )
    component = models.CharField(max_length=16, choices=enum_choices(ObligationComponent))
    amount = models.DecimalField(max_digits=18, decimal_places=4)
    allocation_order = models.PositiveIntegerField()
    reversal_of = models.OneToOneField(
        "self", null=True, blank=True, on_delete=models.PROTECT, related_name="reversal"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="obligation_allocations_created",
    )

    class Meta:
        ordering = ("source_event_id", "allocation_order")
        constraints = [
            models.UniqueConstraint(fields=("source_event", "allocation_order"), name="loans_allocation_event_order_uniq"),
            models.CheckConstraint(condition=~Q(amount=0), name="loans_allocation_amount_nonzero"),
        ]
        indexes = [models.Index(fields=("workspace", "loan", "component"), name="loans_allocation_component_idx")]

    def clean(self):
        super().clean()
        errors = {}
        workspace_id = current_tenant_workspace_id()
        if workspace_id and self.workspace_id != workspace_id:
            errors["workspace"] = "Allocation must belong to the active workspace."
        if self.obligation_id and self.obligation.loan_id != self.loan_id:
            errors["obligation"] = "Allocation obligation must belong to its loan."
        if self.source_event_id and self.source_event.loan_id != self.loan_id:
            errors["source_event"] = "Allocation source event must belong to its loan."
        if self.reversal_of_id:
            if self.reversal_of.loan_id != self.loan_id:
                errors["reversal_of"] = "Reversed allocation must belong to its loan."
            if self.amount != -self.reversal_of.amount:
                errors["amount"] = "Reversal allocation must be the exact inverse."
        elif self.amount < 0:
            errors["amount"] = "Only reversal allocations may be negative."
        if errors:
            raise ValidationError(errors)
