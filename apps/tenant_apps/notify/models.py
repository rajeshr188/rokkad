import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import models
from django.shortcuts import reverse
from django.template import Context, Template
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

from apps.tenant_apps.utils.loan_pdf import get_notice_pdf

logger = logging.getLogger(__name__)


# Create your models here.
class NoticeTypeConfig(models.Model):
    """
    Configure notification types per company/tenant.
    Allows different businesses to define their own notice types.

    Replaces hardcoded NoticeType choices with flexible, database-backed configuration.
    Enables the notification system to support any business module (loans, sales, purchase, etc.)
    """

    code = models.CharField(
        max_length=50,
        unique=True,
        help_text="Unique identifier for this notice type (e.g., LOAN_FIRST_REMINDER, INVOICE_REMINDER)",
    )
    name = models.CharField(
        max_length=100, help_text="Display name for this notice type"
    )

    class CategoryChoices(models.TextChoices):
        LOAN = "LOAN", "Loan/Girvi"
        SALES = "SALES", "Sales"
        PURCHASE = "PURCHASE", "Purchase"
        INVENTORY = "INVENTORY", "Inventory"
        ACCOUNTING = "ACCOUNTING", "Accounting"
        HR = "HR", "Human Resources"
        GENERAL = "GENERAL", "General"

    category = models.CharField(
        max_length=50,
        choices=CategoryChoices.choices,
        help_text="Business module category for grouping notice types",
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of when and how this notice type should be used",
    )

    # Default templates per medium
    sms_template = models.TextField(
        blank=True, help_text="Default SMS template with {{variable}} placeholders"
    )
    whatsapp_template = models.TextField(
        blank=True, help_text="Default WhatsApp template with {{variable}} placeholders"
    )
    email_subject_template = models.CharField(
        max_length=200, blank=True, help_text="Email subject line template"
    )
    email_template = models.TextField(
        blank=True,
        help_text="Default email body template with {{variable}} placeholders",
    )
    postal_template = models.TextField(
        blank=True,
        help_text="Default postal letter template with {{variable}} placeholders",
    )

    # Metadata
    is_active = models.BooleanField(
        default=True,
        help_text="Inactive notice types won't appear in selection dropdowns",
    )
    sort_order = models.PositiveIntegerField(
        default=0, help_text="Display order in dropdowns (lower numbers first)"
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ["category", "sort_order", "name"]
        verbose_name = "Notice Type Configuration"
        verbose_name_plural = "Notice Type Configurations"
        indexes = [
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class NoticeGroup(models.Model):
    """
    Container for batch notifications. Groups related notifications together
    for easier management and bulk operations.

    TODO: Add date_range field for filtering loans by date
    TODO: Add created_by field to track who created the group
    """

    name = models.CharField(max_length=30, unique=True)
    description = models.TextField(blank=True, null=True)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Notice Group"
        verbose_name_plural = "Notice Groups"

    def __str__(self):
        return f"{self.name}"

    def get_absolute_url(self):
        return reverse("notify_noticegroup_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("notify_noticegroup_update", args=(self.pk,))

    def items_count(self):
        return self.notifications.count()

    def print_notice(self):
        """Generate a batch PDF for all printable notifications in this group."""
        selection = []
        template_key = None
        seen_objects = set()

        notifications = self.notifications.select_related(
            "notice_type_config"
        ).prefetch_related(
            "items",
        )
        for notification in notifications:
            if notification.get_renderer_type() != NotificationTemplate.RendererType.PDF:
                continue

            printable_items = notification.get_printable_items()
            if not printable_items:
                continue

            if template_key is None:
                selected_template = notification.get_selected_template()
                template_key = getattr(selected_template, "pdf_template_key", None)

            for obj in printable_items:
                obj_key = (
                    getattr(getattr(obj, "_meta", None), "label_lower", obj.__class__.__name__),
                    getattr(obj, "pk", None),
                )
                if obj_key in seen_objects:
                    continue
                seen_objects.add(obj_key)
                selection.append(obj)

        if not selection:
            return None

        selection.sort(
            key=lambda obj: getattr(
                getattr(obj, "borrower", None) or getattr(obj, "customer", None),
                "pk",
                0,
            )
        )
        return get_notice_pdf(selection=selection, template_key=template_key)


class NotificationItem(models.Model):
    """
    Through model to link notifications with multiple business objects.

    Uses Django's ContentTypes framework to create generic relationships.
    Allows one notification to reference many loans, or many invoices, or any model.

    This enables the notification system to be reusable across all business modules
    without hardcoding specific model relationships.
    """

    notification = models.ForeignKey(
        "Notification",
        on_delete=models.CASCADE,
        related_name="items",
        help_text="The notification this item belongs to",
    )

    # Generic relation to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        help_text="The type of object this item references (e.g., GivenLoan, Invoice, PurchaseOrder)",
    )
    object_id = models.PositiveIntegerField(help_text="The ID of the referenced object")
    content_object = GenericForeignKey("content_type", "object_id")

    # Optional item-specific data (useful for calculations without hitting DB)
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Amount related to this item (loan amount, invoice total, etc.)",
    )
    due_date = models.DateField(
        null=True,
        blank=True,
        help_text="Due date for this item (loan maturity, invoice due date, etc.)",
    )
    reference_number = models.CharField(
        max_length=100,
        blank=True,
        help_text="Reference number from the related object (loan_id, invoice_number, etc.)",
    )
    notes = models.TextField(
        blank=True, help_text="Additional notes specific to this item"
    )

    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        unique_together = [["notification", "content_type", "object_id"]]
        verbose_name = "Notification Item"
        verbose_name_plural = "Notification Items"
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
            models.Index(fields=["notification"]),
        ]

    def __str__(self):
        return f"{self.content_type.model} #{self.object_id} for {self.notification}"


class Notification(models.Model):
    """
    Individual customer notification with related business objects.

    Tracks the lifecycle of a notification from creation to delivery.
    Supports multiple channels (Email, SMS, WhatsApp, Post, Letter).

    Business objects are linked through generic NotificationItem records.

    TODO: Add sent_at, delivered_at, read_at timestamps
    TODO: Add scheduled_for field for delayed sending
    TODO: Add failed_reason for error tracking
    TODO: Add retry_count for failed delivery attempts
    TODO: Add external_id for tracking with third-party delivery services.
    TODO: Add created_by field to track who created the notification
    """

    # Relationships
    group = models.ForeignKey(
        "notify.NoticeGroup",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    customer = models.ForeignKey(
        "contact.Customer", on_delete=models.CASCADE, related_name="notifications"
    )
    party = models.ForeignKey(
        "party.Party",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Shadow Party link for the notification recipient during Customer migration.",
    )

    # Notification Configuration
    class MediumType(models.TextChoices):
        Email = "E", "Email"
        Post = "P", "Post"
        Whatsapp = "W", "Whatsapp"
        SMS = "S", "SMS"
        Letter = "L", "Letter"

    medium_type = models.CharField(
        max_length=1,
        choices=MediumType.choices,
        default=MediumType.Email,
        help_text="Channel to use for sending this notification",
    )

    # OLD FIELD - Keep for backward compatibility during migration
    class NoticeType(models.TextChoices):
        First_Reminder = "FR", "First Reminder"
        Second_Reminder = "SR", "Second Reminder"
        Final_Notice = "FN", "Final Notice"
        Loan_created = "LN", "Loan Created"

    notice_type = models.CharField(
        max_length=2,
        choices=NoticeType.choices,
        blank=True,
        null=True,
        help_text="DEPRECATED: Use notice_type_config instead for flexible notice types",
    )

    # NEW FIELD - Use this for new notifications
    notice_type_config = models.ForeignKey(
        NoticeTypeConfig,
        on_delete=models.PROTECT,
        related_name="notifications",
        null=True,
        blank=True,
        help_text="Configurable notice type that supports all business modules",
    )

    class StatusType(models.TextChoices):
        Draft = "D", "Draft"
        Sent = "S", "Sent"
        Delivered = "Z", "Delivered"
        Acknowledged = "A", "Acknowledged"
        Responded = "R", "Responded"

    status = models.CharField(
        max_length=1,
        choices=StatusType.choices,
        default=StatusType.Draft,
        help_text="Current status in the notification lifecycle",
    )

    # Content
    message = models.TextField(
        blank=True,
        help_text="Notification message. Auto-generated from template if empty.",
    )

    # Tracking
    is_printed = models.BooleanField(
        default=False, help_text="Set to True when notification is printed"
    )
    last_updated = models.DateTimeField(auto_now=True, editable=False)
    created = models.DateTimeField(auto_now_add=True, editable=False)

    class Meta:
        ordering = ["-created"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        indexes = [
            models.Index(fields=["status", "created"]),
            models.Index(fields=["customer", "notice_type"]),
            models.Index(fields=["party", "status"]),
        ]

    def __str__(self):
        # Use new notice_type_config if available, otherwise fall back to old field
        if self.notice_type_config:
            notice_display = self.notice_type_config.name
        elif self.notice_type:
            notice_display = self.get_notice_type_display()
        else:
            notice_display = "Unknown"
        return f"{notice_display} to {self.customer} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.party_id:
            party = getattr(getattr(self, "customer", None), "party", None)
            if party:
                self.party = party
                update_fields = kwargs.get("update_fields")
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {"party"}
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("notify_notification_detail", args=(self.pk,))

    def get_update_url(self):
        return reverse("notify_Notification_update", args=(self.pk,))

    # ============ NEW GENERIC METHODS ============

    def add_item(self, obj, **kwargs):
        """
        Add any business object to this notification.

        Args:
            obj: Any Django model instance (GivenLoan, Invoice, PurchaseOrder, etc.)
            **kwargs: Optional fields (amount, due_date, reference_number, notes)

        Returns:
            NotificationItem instance

        Example:
            notification.add_item(loan, amount=loan.loanamount, due_date=loan.maturity_date)
            notification.add_item(invoice, amount=invoice.total, reference_number=invoice.number)
        """
        item = NotificationItem.objects.create(
            notification=self, content_object=obj, **kwargs
        )
        return item

    def get_items_by_type(self, model_class):
        """
        Get all notification items of a specific model type.

        Args:
            model_class: Django model class (e.g., GivenLoan, Invoice)

        Returns:
            QuerySet of NotificationItem instances

        Example:
            loan_items = notification.get_items_by_type(GivenLoan)
        """
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(model_class)
        return self.items.filter(content_type=ct)

    def get_related_objects(self):
        """
        Get all business objects linked to this notification.

        Returns:
            List of actual model instances (not NotificationItem wrappers)

        Example:
            objects = notification.get_related_objects()  # [loan1, loan2, invoice1]
        """
        if not self.pk:
            return []
        return [item.content_object for item in self.items.all()]

    def calculate_total_amount(self):
        """
        Sum the amount field of all notification items.

        Returns:
            Decimal: Total amount across all items
        """
        from django.db.models import Sum

        if not self.pk:
            return 0

        result = self.items.aggregate(total=Sum("amount"))
        return result["total"] or 0

    # ============ END NEW METHODS ============

    def update_status(self, new_status, reason=None):
        """
        Update notification status with audit trail.

        TODO: Create NotificationStatusLog model for audit trail
        TODO: Add timestamp fields (sent_at, delivered_at) based on status
        """
        self.status = new_status
        if new_status == self.StatusType.Sent:
            # self.sent_at = timezone.now()  # TODO: Add field
            pass
        self.save()

    def print_letter(self):
        """Generate and return PDF bytes for a printable notification."""
        if self.get_renderer_type() != NotificationTemplate.RendererType.PDF:
            return None

        selection = self.get_printable_items()
        if not selection:
            return None

        selected_template = self.get_selected_template()
        template_key = getattr(selected_template, "pdf_template_key", None)
        pdf = get_notice_pdf(selection=selection, template_key=template_key)
        if pdf:
            self.is_printed = True
            if self.pk:
                self.save(update_fields=["is_printed", "last_updated"])
            else:
                self.save()
        return pdf

    def get_selected_template(self):
        if not getattr(self, "notice_type_config", None):
            return None
        return NotificationTemplate.resolve_for(self)

    def get_renderer_type(self):
        selected_template = self.get_selected_template()
        if selected_template:
            return selected_template.renderer
        if self.medium_type in (self.MediumType.Post, self.MediumType.Letter):
            return NotificationTemplate.RendererType.PDF
        return NotificationTemplate.RendererType.DJANGO

    def get_printable_items(self):
        return [
            obj for obj in self.get_related_objects() if hasattr(obj, "loan_id")
        ]

    def get_subject_text(self):
        default_subject = self.effective_notice_type or "Notification"
        selected_template = self.get_selected_template()
        if selected_template and selected_template.subject_template:
            subject = selected_template.render_subject(self)
            if subject:
                return subject

        if self.notice_type_config and self.notice_type_config.email_subject_template:
            return (
                Template(self.notice_type_config.email_subject_template)
                .render(Context(self._build_template_context()))
                .strip()
                or default_subject
            )
        return default_subject

    def _build_template_context(self):
        item_rows = self.items.all() if self.pk else []
        return {
            "customer": self.customer,
            "party": self.party,
            "notification": self,
            "items": [
                {
                    "object": item.content_object,
                    "amount": item.amount,
                    "due_date": item.due_date,
                    "reference": item.reference_number,
                }
                for item in item_rows
            ],
            "total_amount": self.calculate_total_amount(),
            "notice_type": self.notice_type_config.name
            if self.notice_type_config
            else self.get_notice_type_display(),
        }

    def send_email(self):
        """Send notification to the customer's configured email address."""
        recipient = (getattr(self.customer, "email", None) or "").strip()
        if not recipient:
            return False

        if not self.message:
            self.generate_message()

        subject = self.get_subject_text()

        try:
            send_mail(
                subject,
                self.message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient],
                fail_silently=False,
            )
        except Exception:
            logger.exception("Failed to send notification email for notification %s", self.pk or "unsaved")
            return False

        self.update_status(self.StatusType.Sent)
        return True

    def send_sms(self):
        """
        Send notification via a configured SMS gateway.

        TODO: Implement SMS sending logic
        TODO: Update status to Sent on success
        TODO: Handle errors and update failed_reason
        """
        # Example implementation:
        # client = Client(account_sid, auth_token)
        # for contact in self.customer.contactno.filter(is_mobile=True):
        #     message = client.messages.create(
        #         body=self.message,
        #         from_=from_number,
        #         to=contact.number
        #     )
        #     self.update_status(self.StatusType.Sent)
        pass

    def send_whatsapp(self):
        """
        Send notification via WhatsApp Business API.

        TODO: Implement WhatsApp sending logic
        TODO: Use approved message templates
        """
        pass

    def send_notification(self):
        """
        Dispatch notification via the configured medium type.
        Route to appropriate sending method based on medium_type.
        """
        if self.medium_type == self.MediumType.Email:
            self.send_email()
        elif (
            self.medium_type == self.MediumType.Letter
            or self.medium_type == self.MediumType.Post
        ):
            self.print_letter()
        elif self.medium_type == self.MediumType.SMS:
            self.send_sms()
        elif self.medium_type == self.MediumType.Whatsapp:
            self.send_whatsapp()

    def generate_message(self):
        """
        Auto-generate message content based on notice_type and related items.

        Supports both old (loans field) and new (NotificationItem) patterns.
        Uses templates from NoticeTypeConfig if available.
        """
        selected_template = self.get_selected_template()
        if selected_template:
            rendered_message = selected_template.render(self)
            if rendered_message:
                self.message = rendered_message
                return

        # Determine which template to use
        template_text = None
        if self.notice_type_config:
            # Use notice-type defaults when no NotificationTemplate override exists
            if self.medium_type == self.MediumType.SMS:
                template_text = self.notice_type_config.sms_template
            elif self.medium_type == self.MediumType.Email:
                template_text = self.notice_type_config.email_template
            elif self.medium_type == self.MediumType.Whatsapp:
                template_text = self.notice_type_config.whatsapp_template
            elif self.medium_type in (self.MediumType.Post, self.MediumType.Letter):
                template_text = self.notice_type_config.postal_template

        if not template_text:
            # Fallback to basic message
            item_rows = self.items.all() if self.pk else []

            if item_rows:
                # New pattern: use NotificationItem
                items_list = [
                    f"{item.reference_number or item.object_id}"
                    for item in item_rows
                ]
                items_str = ", ".join(items_list)
                self.message = (
                    f"Dear {self.customer.name}, this is regarding items: {items_str}."
                )
            elif loan_rows:
                # Old pattern: use loans M2M
                loan_ids = ", ".join([loan.loan_id for loan in loan_rows])
                self.message = f"Dear {self.customer.name}, your loans {loan_ids} require attention."
            else:
                self.message = (
                    f"Dear {self.customer.name}, this is a notification from us."
                )
            return

        # Render template with context
        template = Template(template_text)
        self.message = template.render(Context(self._build_template_context()))

    @property
    def effective_notice_type(self):
        """
        Get the effective notice type for display, preferring new over old.

        Returns:
            str: Notice type display name
        """
        if self.notice_type_config:
            return self.notice_type_config.name
        elif self.notice_type:
            return self.get_notice_type_display()
        return "Unknown"


class NotificationTemplate(models.Model):
    """Per-medium template override with explicit renderer selection."""

    class RendererType(models.TextChoices):
        DJANGO = "DJANGO", "Django/Jinja Template"
        PDF = "PDF", "PDF / Predefined Print Format"

    notice_type_config = models.ForeignKey(
        NoticeTypeConfig,
        on_delete=models.CASCADE,
        related_name="notification_templates",
        help_text="Notice type this template belongs to.",
    )
    name = models.CharField(
        max_length=100,
        help_text="Internal label for this template entry.",
    )
    medium_type = models.CharField(
        max_length=1,
        choices=Notification.MediumType.choices,
        help_text="Channel this template should be used for.",
    )
    renderer = models.CharField(
        max_length=10,
        choices=RendererType.choices,
        default=RendererType.DJANGO,
        help_text="Use PDF for fixed printable formats and Django/Jinja for flexible digital messages.",
    )
    subject_template = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional subject override for media such as email.",
    )
    body_template = models.TextField(
        blank=True,
        help_text="Use Django template syntax such as {{ customer.name }} and {% for item in items %}.",
    )
    pdf_template_key = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional key for selecting the printable PDF layout implementation.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Only active templates are considered during renderer selection.",
    )
    sort_order = models.PositiveIntegerField(
        default=0,
        help_text="Lower values are preferred first when multiple templates exist.",
    )
    created = models.DateTimeField(auto_now_add=True, editable=False)
    modified = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        ordering = ["notice_type_config__category", "sort_order", "name"]
        verbose_name = "Notification Template"
        verbose_name_plural = "Notification Templates"
        constraints = [
            models.UniqueConstraint(
                fields=["notice_type_config", "medium_type", "name"],
                name="notify_unique_template_name_per_notice_medium",
            )
        ]
        indexes = [
            models.Index(fields=["notice_type_config", "medium_type", "is_active"]),
        ]

    def __str__(self):
        return (
            f"{self.notice_type_config.name} - {self.get_medium_type_display()} "
            f"({self.get_renderer_display()})"
        )

    @classmethod
    def resolve_for(cls, notification):
        notice_type_config = getattr(notification, "notice_type_config", None)
        if not notice_type_config or not getattr(notice_type_config, "pk", None):
            return None
        return (
            cls.objects.filter(
                notice_type_config=notice_type_config,
                medium_type=notification.medium_type,
                is_active=True,
            )
            .order_by("sort_order", "id")
            .first()
        )

    def render_subject(self, notification):
        if not self.subject_template:
            return ""
        return Template(self.subject_template).render(
            Context(notification._build_template_context())
        ).strip()

    def render(self, notification):
        if not self.body_template:
            return ""
        return Template(self.body_template).render(
            Context(notification._build_template_context())
        )
