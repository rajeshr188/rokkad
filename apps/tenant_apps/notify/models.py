from django.db import models
from django.shortcuts import reverse
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


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
        """Generate PDF for all notifications in this group"""
        # TODO: Implement batch PDF generation
        pass


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

    MIGRATION PATH: This model is being refactored to support generic relationships.
    - Old fields (loans, notice_type) are kept temporarily for backward compatibility
    - New fields (notice_type_config) should be used in new code
    - Future migration will remove old fields after data migration

    TODO: Add sent_at, delivered_at, read_at timestamps
    TODO: Add scheduled_for field for delayed sending
    TODO: Add failed_reason for error tracking
    TODO: Add retry_count for failed delivery attempts
    TODO: Add external_id for tracking with third-party services (Twilio, etc.)
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

    # OLD FIELD - Keep for backward compatibility during migration
    loans = models.ManyToManyField(
        "girvi.GivenLoan",
        blank=True,
        related_name="notifications",
        help_text="DEPRECATED: Use NotificationItem model instead for generic relationships",
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
        return [item.content_object for item in self.items.all()]

    def calculate_total_amount(self):
        """
        Sum the amount field of all notification items.

        Returns:
            Decimal: Total amount across all items
        """
        from django.db.models import Sum

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
        """
        Generate and return PDF for postal notification.

        TODO: Mark is_printed=True after successful generation
        """
        # Implementation in views/prints.py
        pass

    def send_email(self):
        """
        Send notification via email.

        TODO: Implement email sending logic
        TODO: Support HTML templates with company branding
        TODO: Optionally attach PDF version of notice
        TODO: Track email opens/clicks if using service like SendGrid
        """
        # Example implementation:
        # from django.core.mail import EmailMultiAlternatives
        # from django.template.loader import render_to_string
        #
        # email_contact = self.customer.contactno.filter(is_email=True).first()
        # if not email_contact:
        #     return False
        #
        # html_content = render_to_string('notify/email_template.html', {
        #     'customer': self.customer,
        #     'notification': self,
        # })
        #
        # msg = EmailMultiAlternatives(
        #     subject=f"{self.get_notice_type_display()}",
        #     body=self.message,
        #     from_email=settings.DEFAULT_FROM_EMAIL,
        #     to=[email_contact.email],
        # )
        # msg.attach_alternative(html_content, "text/html")
        # msg.send()
        # self.update_status(self.StatusType.Sent)
        pass

    def send_sms(self):
        """
        Send notification via SMS using configured gateway (Twilio, etc.).

        TODO: Implement SMS sending logic
        TODO: Update status to Sent on success
        TODO: Handle errors and update failed_reason
        """
        # Example implementation:
        # from twilio.rest import Client
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

        TODO: Implement full Django template rendering
        TODO: Pull templates from NoticeTypeConfig or preferences
        """
        from django.template import Context, Template

        # Determine which template to use
        template_text = None
        if self.notice_type_config:
            # Use new template system based on medium type
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
            if self.items.exists():
                # New pattern: use NotificationItem
                items_list = [
                    f"{item.reference_number or item.object_id}"
                    for item in self.items.all()
                ]
                items_str = ", ".join(items_list)
                self.message = (
                    f"Dear {self.customer.name}, this is regarding items: {items_str}."
                )
            elif self.loans.exists():
                # Old pattern: use loans M2M
                loan_ids = ", ".join([loan.loan_id for loan in self.loans.all()])
                self.message = f"Dear {self.customer.name}, your loans {loan_ids} require attention."
            else:
                self.message = (
                    f"Dear {self.customer.name}, this is a notification from us."
                )
            return

        # Render template with context
        context = {
            "customer": self.customer,
            "notification": self,
            "items": [
                {
                    "object": item.content_object,
                    "amount": item.amount,
                    "due_date": item.due_date,
                    "reference": item.reference_number,
                }
                for item in self.items.all()
            ],
            "total_amount": self.calculate_total_amount(),
            "notice_type": self.notice_type_config.name
            if self.notice_type_config
            else self.get_notice_type_display(),
        }

        template = Template(template_text)
        self.message = template.render(Context(context))

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
