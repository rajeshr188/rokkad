from django.db import models
from django.conf import settings
from decimal import Decimal
from dateutil.relativedelta import relativedelta
from datetime import datetime, timedelta
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# Import Company model (workspace/tenant)
from apps.orgs.models import Company


class Plan(models.Model):
    """
    Subscription plans for India SaaS market.
    Tier: Starter (₹999), Professional (₹3,999), Enterprise (Custom)
    """

    class PlanTierChoices(models.TextChoices):
        STARTER = "starter", "Starter - ₹999/month"
        PROFESSIONAL = "professional", "Professional - ₹3,999/month"
        ENTERPRISE = "enterprise", "Enterprise - Custom"

    class BillingCycleChoices(models.TextChoices):
        MONTHLY = "monthly", "Monthly"
        YEARLY = "yearly", "Yearly (20% discount)"

    name = models.CharField(max_length=255)
    tier = models.CharField(max_length=20, choices=PlanTierChoices.choices)
    price = models.DecimalField(max_digits=8, decimal_places=2)  # In INR
    yearly_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Annual price with 20% discount applied",
    )
    description = models.TextField()
    billing_cycle = models.CharField(
        max_length=10,
        choices=BillingCycleChoices.choices,
        default=BillingCycleChoices.MONTHLY,
    )

    # Feature limits for this plan
    max_users = models.IntegerField(default=5)
    max_products = models.IntegerField(default=100)
    max_warehouses = models.IntegerField(default=1)
    max_transactions_per_month = models.IntegerField(default=500)
    max_invoices_per_month = models.IntegerField(default=500)

    # Feature flags
    has_advanced_reporting = models.BooleanField(default=False)
    has_multi_warehouse = models.BooleanField(default=False)
    has_approvals_workflow = models.BooleanField(default=False)
    has_api_access = models.BooleanField(default=False)
    has_custom_fields = models.BooleanField(default=False)

    # Trial support
    trial_days = models.IntegerField(default=14)

    # Pricing for additional users
    extra_user_price = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("99.00")
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_tier_display()})"

    def save(self, *args, **kwargs):
        # Auto-calculate yearly price with 20% discount
        if not self.yearly_price:
            self.yearly_price = self.price * Decimal("9.6")  # 20% off
        super().save(*args, **kwargs)


class Subscription(models.Model):
    """
    Company-level subscription with usage tracking and automatic billing.
    The company (workspace/tenant) is the paying entity, not individual users.
    Company owner/admin manages billing and subscription.
    """

    class StatusChoices(models.TextChoices):
        TRIAL = "trial", "Trial (14 days free)"
        ACTIVE = "active", "Active & Paid"
        PAST_DUE = "past_due", "Payment Overdue"
        CANCELLED = "cancelled", "Cancelled"
        EXPIRED = "expired", "Expired"

    # Company (workspace) is the billing entity
    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="subscription",
        verbose_name=_("Company/Workspace"),
        help_text="The company/workspace being billed",
    )
    plan = models.ForeignKey(
        Plan, on_delete=models.CASCADE, related_name="subscriptions"
    )
    status = models.CharField(
        max_length=20, choices=StatusChoices.choices, default=StatusChoices.TRIAL
    )

    # Billing dates
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField()
    trial_end_date = models.DateTimeField(null=True, blank=True)

    # Billing
    auto_renew = models.BooleanField(default=True)

    # Razorpay subscription ID (for recurring payments)
    razorpay_subscription_id = models.CharField(max_length=255, null=True, blank=True)

    # Cancellation info
    cancellation_reason = models.TextField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")

    def __str__(self):
        return f"{self.company.name} - {self.plan.name} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.id:
            # First time creation - set dates
            self.start_date = timezone.now()
            self.trial_end_date = self.start_date + timedelta(days=self.plan.trial_days)
            self.status = self.StatusChoices.TRIAL

            # Set end date based on billing cycle
            if self.plan.billing_cycle == Plan.BillingCycleChoices.MONTHLY:
                self.end_date = self.start_date + relativedelta(months=1)
            else:  # YEARLY
                self.end_date = self.start_date + relativedelta(years=1)

        super().save(*args, **kwargs)

    def is_trial_active(self):
        """Check if company is still in trial period"""
        return (
            self.status == self.StatusChoices.TRIAL
            and timezone.now() < self.trial_end_date
        )

    def days_until_renewal(self):
        """Days left before next billing cycle"""
        if self.status == self.StatusChoices.TRIAL:
            return (self.trial_end_date - timezone.now()).days
        return (self.end_date - timezone.now()).days

    def get_current_user_count(self):
        """Get actual member count from Membership table"""
        from apps.orgs.models import Membership

        return Membership.objects.filter(company=self.company).count()

    def get_overage_users(self):
        """Calculate how many users exceed the plan's limit"""
        current_users = self.get_current_user_count()
        return max(0, current_users - self.plan.max_users)

    def get_overage_charge(self):
        """Calculate overage charges for extra users"""
        overage_users = self.get_overage_users()
        return Decimal(str(overage_users)) * self.plan.extra_user_price

    def get_total_charges(self):
        """Calculate total charges including overage"""
        base_price = (
            self.plan.yearly_price
            if self.plan.billing_cycle == Plan.BillingCycleChoices.YEARLY
            else self.plan.price
        )
        overage_charge = self.get_overage_charge()
        total = base_price + overage_charge
        return total

    def can_add_member(self):
        """Compatibility wrapper around the canonical member entitlement."""
        from apps.subscriptions.entitlements import limit

        current_users = self.get_current_user_count()
        member_limit = limit(self.company, "workspace.max_members")
        return member_limit is not None and current_users < member_limit

    def can_access_feature(self, feature_name):
        """Compatibility wrapper around the canonical entitlement service."""
        from apps.subscriptions.entitlements import enabled

        return enabled(self.company, feature_name)

    def is_billing_manager(self, user):
        """Check if user can manage billing (company owner or billing admin)"""
        from apps.orgs.models import Membership

        # Owner can always manage billing
        if self.company.owner == user:
            return True

        # Check if user has billing admin role in company
        membership = Membership.objects.filter(company=self.company, user=user).first()
        if membership and membership.role:
            # Check if role has billing permissions
            return membership.role.permissions.filter(
                codename="manage_company_billing"
            ).exists()

        return False


class BillingAccount(models.Model):
    """Workspace-level billing account used by the subscription service."""

    company = models.OneToOneField(
        Company,
        on_delete=models.CASCADE,
        related_name="billing_account",
        verbose_name=_("Company/Workspace"),
    )
    provider = models.CharField(max_length=50, default="razorpay")
    provider_customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        db_index=True,
        verbose_name=_("Provider Customer ID"),
    )
    billing_email = models.EmailField(null=True, blank=True)
    billing_phone = models.CharField(max_length=32, blank=True)
    contact_name = models.CharField(max_length=255, blank=True)
    gstin = models.CharField(max_length=20, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Billing Account")
        verbose_name_plural = _("Billing Accounts")

    def __str__(self):
        return f"{self.company.name} billing"


class SubscriptionEntitlement(models.Model):
    """Feature and limit entitlements for a workspace subscription."""

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="entitlements",
        verbose_name=_("Subscription"),
    )
    feature_code = models.CharField(max_length=100, verbose_name=_("Feature Code"))
    enabled = models.BooleanField(default=True)
    value = models.CharField(max_length=255, blank=True)
    source = models.CharField(
        max_length=20,
        choices=[("plan", "Plan projection"), ("override", "Explicit override")],
        default="plan",
    )
    override_reason = models.TextField(blank=True)
    override_actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subscription_entitlement_overrides",
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("subscription", "feature_code")
        verbose_name = _("Subscription Entitlement")
        verbose_name_plural = _("Subscription Entitlements")
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(source="plan")
                    | (
                        models.Q(source="override")
                        & models.Q(override_actor__isnull=False)
                        & ~models.Q(override_reason="")
                    )
                ),
                name="subscription_override_requires_provenance",
            )
        ]

    def __str__(self):
        return f"{self.subscription.company.name} / {self.feature_code}"


class ProviderWebhookEvent(models.Model):
    """Persisted provider webhook events for safe replay and audit."""

    class StatusChoices(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        FAILED = "failed", "Failed"

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="webhook_events",
        null=True,
        blank=True,
        verbose_name=_("Subscription"),
    )
    provider = models.CharField(max_length=50, default="razorpay")
    provider_event_id = models.CharField(max_length=255, null=True, blank=True)
    event_type = models.CharField(max_length=100, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=20,
        choices=StatusChoices.choices,
        default=StatusChoices.RECEIVED,
    )
    error_message = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Provider Webhook Event")
        verbose_name_plural = _("Provider Webhook Events")
        constraints = [
            models.UniqueConstraint(
                fields=("provider", "provider_event_id"),
                name="subscription_provider_event_unique",
            )
        ]


class SubscriptionEvent(models.Model):
    """Lifecycle and billing events for a workspace subscription."""

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("Subscription"),
    )
    event_type = models.CharField(max_length=100, verbose_name=_("Event Type"))
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("Subscription Event")
        verbose_name_plural = _("Subscription Events")


class Invoice(models.Model):
    """
    Monthly billing invoice with GST calculation for Indian market.
    Includes base plan + overage charges.
    Tied to company subscription (workspace-level billing).
    """

    class StatusChoices(models.TextChoices):
        DRAFT = "draft", "Draft"
        ISSUED = "issued", "Issued"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        CANCELLED = "cancelled", "Cancelled"

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="invoices",
        verbose_name=_("Subscription"),
    )

    # Invoice details
    invoice_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name=_("Invoice Number"),
        help_text="e.g., INV-2025-01-0001",
    )
    status = models.CharField(
        max_length=20, choices=StatusChoices.choices, default=StatusChoices.ISSUED
    )

    # Pricing breakdown
    base_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name=_("Base Amount"),
        help_text="Plan price",
    )
    overage_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        verbose_name=_("Overage Amount"),
        help_text="Extra users, additional features",
    )
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)

    # GST (18% for India - adjustable)
    gst_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("18.00"),
        verbose_name=_("GST Rate (%)"),
    )
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Final amount
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    # Razorpay payment ID
    razorpay_payment_id = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Razorpay Payment ID")
    )
    razorpay_order_id = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Razorpay Order ID")
    )

    # Dates
    invoice_date = models.DateField(verbose_name=_("Invoice Date"))
    due_date = models.DateField(
        verbose_name=_("Due Date"), help_text="7 days from invoice date"
    )
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name=_("Paid On"))

    # Notes
    notes = models.TextField(blank=True, verbose_name=_("Notes"))

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-invoice_date"]
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")

    def __str__(self):
        return f"{self.invoice_number} - {self.subscription.company.name} - ₹{self.total_amount}"

    def save(self, *args, **kwargs):
        # Calculate amounts
        self.subtotal = self.base_amount + self.overage_amount
        self.gst_amount = self.subtotal * (self.gst_rate / Decimal("100"))
        self.total_amount = self.subtotal + self.gst_amount

        # Auto-generate invoice number if not set
        if not self.invoice_number:
            year = datetime.now().year
            month = datetime.now().month
            count = (
                Invoice.objects.filter(
                    invoice_date__year=year, invoice_date__month=month
                ).count()
                + 1
            )
            self.invoice_number = f"INV-{year}-{month:02d}-{count:04d}"

        super().save(*args, **kwargs)

    def mark_as_paid(self, razorpay_id):
        """Mark an invoice paid and activate through the billing transition service."""
        self.status = self.StatusChoices.PAID
        self.paid_at = timezone.now()
        self.razorpay_payment_id = razorpay_id
        self.save()

        from apps.subscriptions.billing import transition_subscription

        transition_subscription(
            subscription=self.subscription,
            target_status=Subscription.StatusChoices.ACTIVE,
            event_type="invoice.paid",
            payload={"invoice_id": self.pk, "provider_payment_id": razorpay_id},
        )


class Payment(models.Model):
    """
    Payment records for Razorpay integration.
    Tracks actual payment processing for company invoices.
    """

    class PaymentStatusChoices(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTHORIZED = "authorized", "Authorized"
        CAPTURED = "captured", "Captured"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    invoice = models.OneToOneField(
        Invoice,
        on_delete=models.CASCADE,
        related_name="payment",
        verbose_name=_("Invoice"),
    )

    # Razorpay details
    razorpay_payment_id = models.CharField(
        max_length=255, unique=True, verbose_name=_("Razorpay Payment ID")
    )
    razorpay_order_id = models.CharField(
        max_length=255, null=True, blank=True, verbose_name=_("Razorpay Order ID")
    )

    # Amount & status
    amount = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Amount")
    )
    status = models.CharField(
        max_length=20,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.PENDING,
        verbose_name=_("Status"),
    )

    # Payment method
    payment_method = models.CharField(
        max_length=50,
        choices=[
            ("card", "Credit/Debit Card"),
            ("netbanking", "Net Banking"),
            ("upi", "UPI"),
            ("wallet", "Wallet"),
            ("emandate", "E-Mandate (Auto-pay)"),
        ],
        default="card",
        verbose_name=_("Payment Method"),
    )

    # Refund info
    refund_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        null=True,
        blank=True,
        verbose_name=_("Refund Amount"),
    )
    refund_reason = models.TextField(
        null=True, blank=True, verbose_name=_("Refund Reason")
    )

    # Timestamps
    payment_date = models.DateTimeField(verbose_name=_("Payment Date"))
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-payment_date"]
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")

    def __str__(self):
        return f"Payment {self.razorpay_payment_id} - ₹{self.amount} ({self.get_status_display()})"


class UsageMetrics(models.Model):
    """
    Track daily/monthly usage for metering and analytics.
    Monitors company-level resource usage against plan limits.
    """

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="usage_metrics",
        verbose_name=_("Subscription"),
    )

    # Count metrics
    users_count = models.IntegerField(default=0, verbose_name=_("Active Users"))
    transactions_count = models.IntegerField(
        default=0, verbose_name=_("Transactions Count")
    )
    invoices_count = models.IntegerField(default=0, verbose_name=_("Invoices Count"))
    products_count = models.IntegerField(default=0, verbose_name=_("Products Count"))

    # Dates
    date = models.DateField(
        db_index=True, verbose_name=_("Date"), help_text="Daily snapshot"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("subscription", "date")
        ordering = ["-date"]
        verbose_name = _("Usage Metric")
        verbose_name_plural = _("Usage Metrics")
        indexes = [
            models.Index(fields=["subscription", "date"]),
            models.Index(fields=["-date"]),
        ]

    def __str__(self):
        return f"{self.subscription.company.name} - {self.date}"

    def is_near_user_limit(self):
        """Check if company is near max users limit (>80%)"""
        from apps.subscriptions.entitlements import limit

        max_users = limit(self.subscription.company, "workspace.max_members")
        if max_users is None:
            return False
        return self.users_count > (max_users * 0.8)

    def is_near_transaction_limit(self):
        """Check if company is near transaction limit (>80%)"""
        max_transactions = self.subscription.plan.max_transactions_per_month
        return self.transactions_count > (max_transactions * 0.8)

    def is_near_invoice_limit(self):
        """Check if company is near invoice limit (>80%)"""
        max_invoices = self.subscription.plan.max_invoices_per_month
        return self.invoices_count > (max_invoices * 0.8)


class PriceOverride(models.Model):
    """
    Custom pricing for Enterprise clients (negotiated discounts, custom plans).
    Applied at company level for special deals.
    """

    subscription = models.OneToOneField(
        Subscription,
        on_delete=models.CASCADE,
        related_name="price_override",
        verbose_name=_("Subscription"),
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.CASCADE,
        related_name="price_overrides",
        verbose_name=_("Base Plan"),
    )

    # Custom pricing
    custom_monthly_price = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name=_("Custom Monthly Price")
    )
    custom_annual_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Custom Annual Price"),
    )

    # Justification
    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name=_("Discount %"),
        help_text="Percentage discount applied",
    )
    reason = models.CharField(
        max_length=255,
        choices=[
            ("annual_commitment", "Annual Commitment"),
            ("volume_discount", "Volume Discount"),
            ("competitor_match", "Competitor Matching"),
            ("early_adopter", "Early Adopter"),
            ("non_profit", "Non-Profit Organization"),
            ("partner", "Strategic Partner"),
            ("other", "Other"),
        ],
        verbose_name=_("Discount Reason"),
    )
    notes = models.TextField(blank=True, verbose_name=_("Internal Notes"))

    # Validity
    valid_from = models.DateField(verbose_name=_("Valid From"))
    valid_until = models.DateField(
        null=True,
        blank=True,
        verbose_name=_("Valid Until"),
        help_text="Leave blank for indefinite",
    )

    approved_by = models.CharField(
        max_length=255,
        verbose_name=_("Approved By"),
        help_text="Admin email who approved",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Price Override")
        verbose_name_plural = _("Price Overrides")

    def __str__(self):
        return f"Custom pricing for {self.subscription.company.name} - {self.discount_percentage}% off"

    def is_active(self):
        """Check if override is currently valid"""
        today = timezone.now().date()
        return self.valid_from <= today and (
            self.valid_until is None or today <= self.valid_until
        )
