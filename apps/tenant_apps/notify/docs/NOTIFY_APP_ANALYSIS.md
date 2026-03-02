# Notify App Analysis & Enhancement Plan

> **🎉 PRIORITY 0 IMPLEMENTATION COMPLETE!**  
> The generic notification system has been implemented. See [PRIORITY_0_IMPLEMENTATION.md](PRIORITY_0_IMPLEMENTATION.md) for:
> - Usage examples for all business modules (Loans, Sales, Purchase, Inventory, Accounting, HR)
> - 22 pre-configured notice types with templates
> - Migration guide from old to new system
> - Admin interface documentation
>
> **Next Step**: Run `python manage.py migrate` to apply changes.

## Executive Summary

The `notify` app is a **notification delivery system** for customer communication across multiple channels (Email, SMS, WhatsApp, Post). 

### Current State
- ✅ Supports group (batch) and individual notification workflows
- ✅ PDF generation for postal notifications
- ⚠️ Tightly coupled to Loan/Girvi module only
- ❌ Email/SMS/WhatsApp sending not implemented (stubs only)
- ❌ No message templates or automation

### Vision: Platform-Wide Notification Hub
**This system is designed to become a centralized notification service for the entire SaaS platform.** After architectural refactoring (see Priority 0), it will support notifications for:

- **Loan/Girvi:** Overdue reminders, maturity notices, auction alerts
- **Sales:** Invoice reminders, payment confirmations, shipment tracking, promotional offers
- **Purchase:** PO notifications to vendors, delivery schedules, payment reminders
- **Inventory:** Stock alerts, reorder notifications to suppliers
- **Accounting:** GST filing reminders, reconciliation alerts, statement delivery
- **HR/Payroll:** Salary slips, leave approvals, attendance notifications
- **General:** Birthday wishes, announcements, custom campaigns

The generic design (using Django ContentTypes) will allow any app to trigger notifications for any business entity without code duplication.

---

## Current Implementation Overview

The `notify` app provides customer notification functionality for the Girvi (loan management) system. It allows companies to send notifications to customers about loan status via multiple channels:

**Supported Channels:**
- **Post/Letter:** User prints PDF (Indian inland post format) and manually mails it
- **Email:** Digital delivery of notification messages *(to be implemented)*
- **SMS:** Text messaging via gateway *(to be implemented)*
- **WhatsApp:** WhatsApp Business API *(to be implemented)*

**Sending Modes:**
- **Group Notifications:** Batch notifications organized under a `NoticeGroup` (e.g., all overdue loans)
- **Individual Notifications:** Single notification to one customer for their specific items

**⚠️ Architectural Limitation:** Currently tightly coupled to `GivenLoan` model. Should be refactored to support multiple business entities (Sales, Purchase, Invoices, etc.) for maximum reusability across the SaaS platform.

### Architecture

**Models:**
- `NoticeGroup`: Container for batch notifications with name and description
  - Enables bulk operations (e.g., send reminders to 100 overdue customers at once)
  - Optional—notifications can exist without a group for individual sending
- `Notification`: Individual customer notification with:
  - Customer (FK)
  - Group (FK, optional)—links to batch for group operations
  - Loans (M2M)
  - Medium type (Post/WhatsApp/SMS/Letter/Email) *(Email missing in choices)*
  - Notice type (First Reminder/Second Reminder/Final Notice/Loan Created)
  - Status (Draft/Sent/Delivered/Acknowledged/Responded)
  - Message text
  - Timestamps and print flag

**Views:**
- `/noticegroup/` - List/create/detail/delete notice groups
- `/notification/` - List/create/detail/delete individual notifications
- `/noticegroup/<pk>/print` - Print all notifications in a group as batch PDF
- `/notification/<pk>/print` - Print single notification as PDF
- Bulk creation from loan filters (in `girvi/views/prints.py`)

**Group vs Individual Operations:**

The system supports two distinct workflows:

1. **Group (Batch) Operations:**
   - Use `NoticeGroup` as container
   - Common for periodic reminders (e.g., monthly overdue notices)
   - Benefits: Single print job for all, easier tracking, bulk status updates
   - Example: "Overdue Loans - January 2026" group with 150 notifications

2. **Individual Operations:**
   - No `NoticeGroup` required
   - Triggered by specific events (loan created, single customer inquiry)
   - Benefits: Immediate sending, targeted messaging
   - Example: Welcome notification when new loan is disbursed

Both workflows share the same `Notification` model and sending mechanisms.

**Current Workflow:**

*Group Notification (Bulk):*
1. User filters loans (e.g., overdue > 1 year) in girvi app
2. User clicks "Create Notifications" from filtered list
3. System creates a `NoticeGroup` with timestamp as name
4. Groups loans by customer (one notification per customer)
5. Bulk creates `Notification` objects linked to the group
6. User visits NoticeGroup detail page
7. User can print all (generates batch PDF) or send via other mediums

*Individual Notification:*
1. User views a single loan detail
2. User clicks "Create Notification" for that loan
3. System creates a `Notification` (no group)
4. User can print single PDF or send individually

---

## Critical Shortcomings

### 1. **No Message Generation Logic**
- `message` field is required but never populated automatically
- No templates for different notice types
- Users must manually write messages (impractical for bulk operations)

### 2. **Incomplete Sending Implementation**
```python
def send_sms(self):
    # implementation for sending an SMS
    pass

def send_notification(self):
    if self.notification_type == "Letter":
        self.print_letter()
    elif self.notification_type == "SMS":
        self.send_sms()
    elif self.notification_type == "WhatsApp":
        # implementation for sending a WhatsApp message
        pass
```
All send methods are stubs—nothing actually sends.

### 3. **Status Tracking Meaningless**
- Status field exists (Draft/Sent/Delivered/Acknowledged/Responded)
- `update_status()` method is empty
- No webhook/callback handling for delivery confirmations (email/SMS/WhatsApp)
- No audit trail of status changes
- Manual post/print has no delivery confirmation mechanism

### 4. **Print-Only Medium**
- Only Post (PDF print for manual mailing) is implemented
- Email option missing from choices entirely
- WhatsApp/SMS/Letter options exist in choices but send methods are empty stubs
- No integration with email service (SMTP, SendGrid, AWS SES)
- No integration with SMS gateways (Twilio, etc.)
- No WhatsApp Business API integration

### 5. **No Scheduling or Reminders**
- No ability to schedule future sends
- No automatic escalation (First → Second → Final)
- No retry logic for failed sends

### 6. **Poor Batch Performance**
```python
for notification in notifications:
    loans = selected_loans.filter(borrower=notification.customer)
    notification.loans.set(loans)
    notification.save()  # N saves after bulk_create
```
Defeats bulk_create benefits with N additional queries.

### 7. **Missing Business Logic**
- No rules for when to send which notice type
- No tracking of loan maturity dates, grace periods
- No calculation of overdue amounts in message
- No integration with loan workflow states

### 8. **Security & Multi-Tenancy**
- No checks in views for tenant isolation
- Admin not registered (no UI to manage)
- No permission checks beyond `@login_required`

### 9. **Incomplete Data Model**
- No sender information (who created the notification)
- No scheduled_date field
- No delivery_date, read_date tracking
- No cost tracking (SMS/WhatsApp have costs)
- `is_printed` boolean instead of print_count

### 10. **No Testing**
- `tests.py` is empty
- No validation of message content
- No mock integration tests for sending

### 11. **Tight Coupling to Loan Model (Critical Architectural Issue)**
```python
loans = models.ManyToManyField("girvi.GivenLoan", related_name="notifications")
```
- Hard-coded to `GivenLoan` model only
- Cannot be reused for Sales notifications, Purchase orders, Invoice reminders, etc.
- Violates DRY principle—each app would need its own notification system
- No generic "trigger event" abstraction
- Template system would need separate implementation per entity type

**Impact:** As the SaaS grows (sales, purchase, inventory, accounting modules), each would need duplicate notification logic. This creates:
- Code duplication and maintenance burden
- Inconsistent notification UX across modules
- Wasted development effort
- Harder to add new channels (all modules need updates)

**Real-world use cases being blocked:**
- Sales: Payment reminders for unpaid invoices
- Purchase: PO delivery notifications to vendors
- Inventory: Low stock alerts to suppliers
- Accounting: GST filing reminders to customers
- General: Birthday wishes, promotional campaigns

---

## Recommended Enhancements

### Priority 0: Architectural Refactoring (Foundation)

**Make the notification system generic and reusable across all business modules.**

#### 0.1 Polymorphic Relationship Design

Replace hard-coded `GivenLoan` relationship with Django's ContentTypes framework:

```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Notification(models.Model):
    # Replace this:
    # loans = models.ManyToManyField("girvi.GivenLoan")
    
    # With generic relationship:
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # For multiple related objects (like multiple loans), use through table:
    # See NotificationItem model below
```

#### 0.2 Support Multiple Related Objects

Since one notification can relate to multiple items (e.g., multiple loans, multiple invoices):

```python
class NotificationItem(models.Model):
    """
    Through model to link notifications with multiple business objects.
    Allows one notification to reference many loans, or many invoices, etc.
    """
    notification = models.ForeignKey('Notification', on_delete=models.CASCADE)
    
    # Generic relation to any model
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Optional item-specific data
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    
    class Meta:
        unique_together = ['notification', 'content_type', 'object_id']

class Notification(models.Model):
    # Access related items
    items = models.ManyToManyField(
        NotificationItem,
        related_name='+'
    )
    
    def add_item(self, obj, **kwargs):
        """Helper to add any object to notification"""
        item = NotificationItem.objects.create(
            notification=self,
            content_object=obj,
            **kwargs
        )
        return item
```

**Usage Example:**
```python
# For loans (current use case)
notification = Notification.objects.create(
    customer=customer,
    notice_type=Notification.NoticeType.First_Reminder
)
for loan in overdue_loans:
    notification.add_item(loan, amount=loan.loanamount, due_date=loan.maturity_date)

# For sales invoices (future use case)
notification = Notification.objects.create(
    customer=customer,
    notice_type='INVOICE_REMINDER'  # Need to make this dynamic too
)
for invoice in unpaid_invoices:
    notification.add_item(invoice, amount=invoice.total, due_date=invoice.due_date)

# For purchase orders (future use case)
notification = Notification.objects.create(
    customer=vendor,  # Vendors are also customers in contact app
    notice_type='PO_DELIVERY'
)
notification.add_item(purchase_order)
```

#### 0.3 Generic Notice Type System

Current `NoticeType` is loan-specific. Make it configurable:

```python
class NoticeTypeConfig(models.Model):
    """
    Define notification types per company/tenant.
    Allows different businesses to configure their own notice types.
    """
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=[
        ('LOAN', 'Loan'),
        ('SALES', 'Sales'),
        ('PURCHASE', 'Purchase'),
        ('INVENTORY', 'Inventory'),
        ('GENERAL', 'General'),
    ])
    description = models.TextField(blank=True)
    
    # Default templates per medium
    sms_template = models.TextField(blank=True)
    whatsapp_template = models.TextField(blank=True)
    email_template = models.TextField(blank=True)
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Notice Type Configuration"

class Notification(models.Model):
    # Replace TextChoices with FK
    notice_type = models.ForeignKey(
        NoticeTypeConfig,
        on_delete=models.PROTECT,
        related_name='notifications'
    )
```

**Seed Default Notice Types:**
```python
# In migration or management command
NoticeTypeConfig.objects.bulk_create([
    # Loan types
    NoticeTypeConfig(code='LOAN_FIRST_REMINDER', name='First Reminder', category='LOAN'),
    NoticeTypeConfig(code='LOAN_SECOND_REMINDER', name='Second Reminder', category='LOAN'),
    NoticeTypeConfig(code='LOAN_FINAL_NOTICE', name='Final Notice', category='LOAN'),
    NoticeTypeConfig(code='LOAN_CREATED', name='Loan Created', category='LOAN'),
    
    # Sales types
    NoticeTypeConfig(code='INVOICE_REMINDER', name='Invoice Payment Reminder', category='SALES'),
    NoticeTypeConfig(code='SALES_CONFIRMATION', name='Sale Confirmation', category='SALES'),
    NoticeTypeConfig(code='DELIVERY_UPDATE', name='Delivery Status Update', category='SALES'),
    
    # Purchase types
    NoticeTypeConfig(code='PO_CREATED', name='Purchase Order Created', category='PURCHASE'),
    NoticeTypeConfig(code='PO_DELIVERY', name='PO Delivery Schedule', category='PURCHASE'),
    
    # General
    NoticeTypeConfig(code='PROMOTIONAL', name='Promotional Campaign', category='GENERAL'),
    NoticeTypeConfig(code='BIRTHDAY_WISH', name='Birthday Greeting', category='GENERAL'),
])
```

#### 0.4 Generic Template Variables

Template system must extract data from any model:

```python
class NotificationTemplate(models.Model):
    notice_type = models.ForeignKey(NoticeTypeConfig, on_delete=models.CASCADE)
    medium_type = models.CharField(max_length=1, choices=Notification.MediumType.choices)
    
    template_text = models.TextField(
        help_text="Use {{customer.name}}, {{items.0.amount}}, etc."
    )
    
    def render(self, notification):
        """Generic rendering for any notification"""
        from django.template import Context, Template
        
        context = {
            'customer': notification.customer,
            'items': [
                {
                    'object': item.content_object,
                    'amount': item.amount,
                    'due_date': item.due_date,
                    # Add generic accessors
                }
                for item in notification.items.all()
            ],
            'notice_type': notification.notice_type.name,
            'company': notification.customer.company,
        }
        
        template = Template(self.template_text)
        return template.render(Context(context))
```

**Example Templates:**

*Loan Reminder Template:*
```
Dear {{customer.name}},

This is a {{notice_type}} for your loan(s):
{% for item in items %}
- Loan ID: {{item.object.loan_id}}, Amount: ₹{{item.amount}}, Due: {{item.due_date}}
{% endfor %}

Please contact us for repayment.
```

*Invoice Reminder Template:*
```
Dear {{customer.name}},

Your invoice(s) are pending payment:
{% for item in items %}
- Invoice #{{item.object.invoice_number}}, Amount: ₹{{item.amount}}, Due: {{item.due_date}}
{% endfor %}

Pay now to avoid late fees.
```

#### 0.5 Event-Driven Trigger System

Decouple notification creation from business logic:

```python
from django.dispatch import Signal, receiver

# Define signals for different events
loan_overdue = Signal()
invoice_created = Signal()
po_received = Signal()

# Generic notification handler
@receiver(loan_overdue)
def handle_loan_overdue(sender, loan, **kwargs):
    """Triggered when loan becomes overdue"""
    notification = Notification.objects.create(
        customer=loan.borrower,
        notice_type=NoticeTypeConfig.objects.get(code='LOAN_FIRST_REMINDER'),
    )
    notification.add_item(loan)
    notification.generate_message()
    notification.send_notification()

@receiver(invoice_created)
def handle_invoice_created(sender, invoice, **kwargs):
    """Triggered when invoice is created"""
    notification = Notification.objects.create(
        customer=invoice.customer,
        notice_type=NoticeTypeConfig.objects.get(code='SALES_CONFIRMATION'),
    )
    notification.add_item(invoice)
    notification.generate_message()
    # Schedule for specific time
    notification.scheduled_for = invoice.created + timedelta(hours=1)
    notification.save()
```

**Usage in business apps:**
```python
# In girvi/models.py or flows.py
loan_overdue.send(sender=GivenLoan, loan=loan_instance)

# In sales/views.py
invoice_created.send(sender=Invoice, invoice=invoice_instance)
```

#### 0.6 Migration Strategy

**Step 1:** Add new fields alongside old ones
```python
class Notification(models.Model):
    # Keep old field temporarily
    loans = models.ManyToManyField("girvi.GivenLoan", null=True, blank=True)
    
    # Add new generic fields
    content_type = models.ForeignKey(ContentType, null=True, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField(null=True)
```

**Step 2:** Data migration to populate new fields
```python
def migrate_loans_to_generic(apps, schema_editor):
    Notification = apps.get_model('notify', 'Notification')
    ContentType = apps.get_model('contenttypes', 'ContentType')
    loan_ct = ContentType.objects.get(app_label='girvi', model='givenloan')
    
    for notification in Notification.objects.all():
        # For each loan, create NotificationItem
        for loan in notification.loans.all():
            NotificationItem.objects.create(
                notification=notification,
                content_type=loan_ct,
                object_id=loan.id
            )
```

**Step 3:** Update all code to use new pattern

**Step 4:** Remove old `loans` field in future migration

#### 0.7 Benefits of Generic Design

✅ **Reusability:** One notification system for entire SaaS  
✅ **Maintainability:** Single codebase to update/fix  
✅ **Scalability:** Add new modules without duplicating notification logic  
✅ **Flexibility:** Each tenant can define custom notice types  
✅ **Consistency:** Same UX for all notification types  
✅ **Future-proof:** Easy to add new channels (push, voice, etc.)  

**Real-World Example: Adding Sales Invoice Reminders**

*Without Refactoring (Current):*
1. Create new `SalesNotification` model in sales app
2. Duplicate all sending logic (SMS, email, etc.)
3. Create separate templates and forms
4. Build separate admin and views
5. Maintain two codebases for same functionality

*With Generic Design (After Priority 0):*
1. Create a `NoticeTypeConfig` entry: "Invoice Payment Reminder"
2. Add a signal trigger in sales app
3. Done! All existing infrastructure works immediately

```python
# In sales/signals.py (2 lines of code)
from apps.tenant_apps.notify.signals import business_event_triggered

invoice_overdue.connect(
    lambda sender, invoice, **kw: business_event_triggered.send(
        sender=Invoice,
        entity=invoice,
        notice_type_code='INVOICE_REMINDER'
    )
)
```

---

### Priority 1: Core Functionality (Must Have)

#### 1.1 Message Template System
Create a preference-based or database-backed template system:

```python
class NotificationTemplate(models.Model):
    notice_type = models.CharField(choices=Notification.NoticeType.choices)
    language = models.CharField(max_length=10, default='en')
    subject = models.CharField(max_length=200)
    body_template = models.TextField(help_text="Use {{variable}} syntax")
    # Variables: customer_name, loan_ids, total_amount, due_date, overdue_days, etc.
```

Auto-generate messages on notification creation:
```python
def generate_message(self):
    template = NotificationTemplate.objects.get(notice_type=self.notice_type)
    context = {
        'customer_name': self.customer.name,
        'loan_ids': ', '.join([l.loan_id for l in self.loans.all()]),
        'total_amount': self.loans.aggregate(Sum('loanamount'))['loanamount__sum'],
        # ... more context
    }
    self.message = template.render(context)
    self.save()
```

#### 1.2 Actual Sending Implementation

**Email Integration (via Django SMTP/SendGrid/AWS SES):**
```python
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from apps.orgs.preferences import CompanyPreferences

def send_email(self):
    prefs = CompanyPreferences(get_current_tenant())
    
    # Get customer email
    email_contact = self.customer.contactno.filter(is_email=True).first()
    if not email_contact:
        self.failed_reason = "No email address found for customer"
        self.save()
        return False
    
    # Render HTML email from template
    html_content = render_to_string('notify/email_template.html', {
        'customer': self.customer,
        'notification': self,
        'items': [item.content_object for item in self.items.all()],
        'company': prefs.company,
    })
    
    # Create email
    subject = f"{self.notice_type.name} - {prefs.company.name}"
    msg = EmailMultiAlternatives(
        subject=subject,
        body=self.message,  # Plain text fallback
        from_email=prefs.email_from_address,
        to=[email_contact.email],
    )
    msg.attach_alternative(html_content, "text/html")
    
    # Optionally attach PDF
    if self.medium_type == self.MediumType.Email:
        pdf = self.generate_pdf()
        msg.attach(f'notification_{self.id}.pdf', pdf, 'application/pdf')
    
    try:
        msg.send()
        self.status = self.StatusType.Sent
        self.sent_at = timezone.now()
        self.save()
        return True
    except Exception as e:
        self.failed_reason = str(e)
        self.retry_count += 1
        self.save()
        return False
```

**SMS Integration (via Twilio/AWS SNS):**
```python
from twilio.rest import Client
from apps.orgs.preferences import CompanyPreferences

def send_sms(self):
    prefs = CompanyPreferences(get_current_tenant())
    client = Client(prefs.twilio_sid, prefs.twilio_token)
    
    for contact in self.customer.contactno.all():
        if contact.is_mobile:
            message = client.messages.create(
                body=self.message,
                from_=prefs.twilio_from_number,
                to=contact.number
            )
            self.status = self.StatusType.Sent
            self.save()
            # Log the message_sid for tracking
```

**WhatsApp Integration (via Twilio/WhatsApp Business API):**
```python
def send_whatsapp(self):
    # Similar to SMS but use whatsapp: prefix
    client.messages.create(
        body=self.message,
        from_='whatsapp:+14155238886',
        to=f'whatsapp:{contact.number}'
    )
```

#### 1.3 Status Lifecycle Management
```python
class Notification(models.Model):
    # Add fields
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    failed_reason = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    
    def update_status(self, new_status, reason=None):
        old_status = self.status
        self.status = new_status
        if new_status == self.StatusType.Sent:
            self.sent_at = timezone.now()
        elif new_status == self.StatusType.Delivered:
            self.delivered_at = timezone.now()
        self.save()
        
        # Create audit log
        NotificationStatusLog.objects.create(
            notification=self,
            from_status=old_status,
            to_status=new_status,
            reason=reason
        )
```

#### 1.4 Webhook Handler for Delivery Status
```python
# views.py
@csrf_exempt
def twilio_status_callback(request):
    message_sid = request.POST.get('MessageSid')
    status = request.POST.get('MessageStatus')
    
    notification = Notification.objects.get(external_id=message_sid)
    
    status_map = {
        'delivered': Notification.StatusType.Delivered,
        'failed': Notification.StatusType.Draft,  # or Failed status
        'undelivered': Notification.StatusType.Draft,
    }
    
    if status in status_map:
        notification.update_status(status_map[status])
    
    return HttpResponse(status=200)
```

### Priority 2: Business Logic & Automation

#### 2.1 Smart Notice Type Selection
```python
class NotificationService:
    @staticmethod
    def determine_notice_type(loan):
        days_overdue = (timezone.now().date() - loan.maturity_date).days
        
        if days_overdue < 0:
            return Notification.NoticeType.Loan_created
        elif days_overdue < 30:
            return Notification.NoticeType.First_Reminder
        elif days_overdue < 60:
            return Notification.NoticeType.Second_Reminder
        else:
            return Notification.NoticeType.Final_Notice
    
    @staticmethod
    def should_send_notification(loan):
        # Don't send if already notified recently
        last_notification = loan.notifications.order_by('-created').first()
        if last_notification:
            days_since = (timezone.now() - last_notification.created).days
            if days_since < 7:  # Configurable via preferences
                return False
        return True
```

#### 2.2 Scheduled Notifications
```python
class Notification(models.Model):
    scheduled_for = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['scheduled_for', 'status']),
        ]

# Celery task or management command
def send_scheduled_notifications():
    pending = Notification.objects.filter(
        status=Notification.StatusType.Draft,
        scheduled_for__lte=timezone.now()
    )
    
    for notification in pending:
        notification.send_notification()
```

#### 2.3 Escalation Workflow
```python
def create_escalation_chain(loans, customer, group):
    base_date = timezone.now()
    
    notifications = [
        Notification(
            group=group,
            customer=customer,
            notice_type=Notification.NoticeType.First_Reminder,
            scheduled_for=base_date + timedelta(days=0),
            medium_type=Notification.MediumType.SMS,
        ),
        Notification(
            group=group,
            customer=customer,
            notice_type=Notification.NoticeType.Second_Reminder,
            scheduled_for=base_date + timedelta(days=15),
            medium_type=Notification.MediumType.Whatsapp,
        ),
        Notification(
            group=group,
            customer=customer,
            notice_type=Notification.NoticeType.Final_Notice,
            scheduled_for=base_date + timedelta(days=30),
            medium_type=Notification.MediumType.Post,
        ),
    ]
    
    created = Notification.objects.bulk_create(notifications)
    for n in created:
        n.loans.set(loans)
```

### Priority 3: Performance & Scalability

#### 3.1 Optimize Bulk Creation
```python
def create_bulk_notifications(selected_loans, group):
    # Group by customer efficiently
    from collections import defaultdict
    customer_loans = defaultdict(list)
    
    for loan in selected_loans:
        customer_loans[loan.borrower_id].append(loan.id)
    
    # Bulk create
    notifications = Notification.objects.bulk_create([
        Notification(
            group=group,
            customer_id=customer_id,
        )
        for customer_id in customer_loans.keys()
    ])
    
    # Bulk set M2M using through table
    through_model = Notification.loans.through
    through_objects = []
    
    for notification in notifications:
        loan_ids = customer_loans[notification.customer_id]
        through_objects.extend([
            through_model(
                notification_id=notification.id,
                givenloan_id=loan_id
            )
            for loan_id in loan_ids
        ])
    
    through_model.objects.bulk_create(through_objects)
```

#### 3.2 Add Database Indexes
```python
class Notification(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['status', 'created']),
            models.Index(fields=['customer', 'notice_type']),
            models.Index(fields=['group', '-created']),
            models.Index(fields=['scheduled_for', 'status']),
        ]
```

#### 3.3 Async Task Processing
```python
# Use Celery for actual sending
@shared_task
def send_notification_async(notification_id):
    notification = Notification.objects.get(id=notification_id)
    try:
        notification.send_notification()
    except Exception as e:
        notification.failed_reason = str(e)
        notification.retry_count += 1
        notification.save()
        
        # Retry with exponential backoff
        if notification.retry_count < 3:
            send_notification_async.apply_async(
                args=[notification_id],
                countdown=2 ** notification.retry_count * 60
            )
```

### Priority 4: UX & Admin Improvements

#### 4.1 Register Admin
```python
# admin.py
from django.contrib import admin
from .models import NoticeGroup, Notification

@admin.register(NoticeGroup)
class NoticeGroupAdmin(admin.ModelAdmin):
    list_display = ['name', 'created', 'notification_count']
    search_fields = ['name', 'description']
    
    def notification_count(self, obj):
        return obj.notifications.count()

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['id', 'customer', 'notice_type', 'medium_type', 'status', 'created']
    list_filter = ['status', 'notice_type', 'medium_type', 'created']
    search_fields = ['customer__name', 'message']
    readonly_fields = ['sent_at', 'delivered_at', 'created', 'last_updated']
    date_hierarchy = 'created'
```

#### 4.2 Better Forms with Validation
```python
class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['customer', 'notice_type', 'medium_type', 'scheduled_for']
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Auto-generate message if not provided
        if not cleaned_data.get('message'):
            notification = Notification(**cleaned_data)
            notification.generate_message()
            cleaned_data['message'] = notification.message
        
        return cleaned_data
```

#### 4.3 Dashboard Widgets
```python
# Add to dashboard
def notification_stats(request):
    stats = {
        'pending': Notification.objects.filter(status='D').count(),
        'sent_today': Notification.objects.filter(
            sent_at__date=timezone.now().date()
        ).count(),
        'failed': Notification.objects.filter(
            retry_count__gte=3
        ).count(),
    }
    return render(request, 'notify/dashboard_widget.html', stats)
```

### Priority 5: Security & Compliance

#### 5.1 Tenant Isolation
```python
class TenantAwareNotificationQuerySet(models.QuerySet):
    def for_tenant(self, tenant):
        return self.filter(customer__company=tenant)

class Notification(models.Model):
    objects = TenantAwareNotificationQuerySet.as_manager()
    
# Update views
@login_required
def notification_list(request):
    tenant = request.user.profile.workspace
    notifications = Notification.objects.for_tenant(tenant)
    # ...
```

#### 5.2 Permission Checks
```python
from apps.orgs.decorators import roles_required

@roles_required(['Owner', 'Admin', 'Manager'])
def create_bulk_notifications(request):
    # ...

@roles_required(['Owner', 'Admin'])
def resend_failed_notifications(request):
    # ...
```

#### 5.3 Rate Limiting
```python
from django.core.cache import cache
from django.http import HttpResponseTooManyRequests

def check_notification_rate_limit(customer, medium_type):
    cache_key = f'notify_limit_{customer.id}_{medium_type}'
    count = cache.get(cache_key, 0)
    
    if count >= 5:  # Max 5 per hour
        return False
    
    cache.set(cache_key, count + 1, 3600)
    return True
```

#### 5.4 GDPR Compliance
```python
class Notification(models.Model):
    def anonymize(self):
        """Anonymize after retention period"""
        self.message = "[REDACTED]"
        self.customer = None
        self.save()

# Management command
def anonymize_old_notifications():
    cutoff = timezone.now() - timedelta(days=365)
    old_notifications = Notification.objects.filter(created__lt=cutoff)
    
    for notification in old_notifications:
        notification.anonymize()
```

---

## Future Enhancements

### Cross-Module Integration Examples

Once the generic architecture (Priority 0) is implemented, here are concrete examples of how other business modules can use the notification system:

#### Sales Module Integration

```python
# sales/models.py
from django.db.models.signals import post_save
from apps.tenant_apps.notify.services import NotificationService

class Invoice(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    # ... other fields

@receiver(post_save, sender=Invoice)
def send_invoice_notification(sender, instance, created, **kwargs):
    if created:
        # Send invoice confirmation
        NotificationService.create_notification(
            customer=instance.customer,
            notice_type_code='INVOICE_CREATED',
            related_objects=[instance],
            medium_type='Email',  # Send immediately via email
        )
```

#### Purchase Module Integration

```python
# purchase/views.py
def approve_purchase_order(request, po_id):
    po = PurchaseOrder.objects.get(id=po_id)
    po.status = 'APPROVED'
    po.save()
    
    # Notify vendor
    NotificationService.create_notification(
        customer=po.vendor,  # Vendors are stored as customers
        notice_type_code='PO_APPROVED',
        related_objects=[po],
        medium_type='Email',
        scheduled_for=timezone.now() + timedelta(hours=1),  # Delayed send
    )
    
    return redirect('purchase:po_detail', po_id)
```

#### Inventory Module Integration

```python
# inventory/tasks.py (Celery task)
@periodic_task(run_every=crontab(hour=9, minute=0))  # Daily at 9 AM
def check_low_stock_and_notify():
    """Check for low stock items and notify suppliers"""
    low_stock_items = Product.objects.filter(
        current_stock__lt=F('reorder_level')
    )
    
    # Group by supplier
    for supplier, products in group_by_supplier(low_stock_items):
        NotificationService.create_notification(
            customer=supplier,
            notice_type_code='LOW_STOCK_ALERT',
            related_objects=list(products),
            medium_type='Email',
        )
```

#### Accounting Module Integration

```python
# accounting/management/commands/gst_reminders.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        """Send GST filing reminders before deadline"""
        deadline = date(2026, 3, 20)  # GST deadline
        companies = Company.objects.filter(gst_registered=True)
        
        for company in companies:
            # Check if reminder already sent
            if not Notification.objects.filter(
                customer__company=company,
                notice_type__code='GST_FILING_REMINDER',
                created__gte=deadline - timedelta(days=7)
            ).exists():
                NotificationService.create_notification(
                    customer=company.primary_contact,
                    notice_type_code='GST_FILING_REMINDER',
                    related_objects=[],  # No specific business object
                    medium_type='Email',
                    context={'deadline': deadline},  # Custom context for template
                )
```

#### HR/Payroll Integration

```python
# hr/payroll.py
def generate_payslips(month, year):
    """Generate and send payslips via email"""
    employees = Employee.objects.filter(status='ACTIVE')
    
    for employee in employees:
        payslip = Payslip.objects.create(
            employee=employee,
            month=month,
            year=year,
            # ... calculate salary
        )
        
        # Send payslip automatically
        NotificationService.create_notification(
            customer=employee.as_customer(),  # Convert employee to customer
            notice_type_code='PAYSLIP_GENERATED',
            related_objects=[payslip],
            medium_type='Email',
            # Will attach PDF payslip in email
        )
```

#### Custom Campaign/Promotional Notifications

```python
# marketing/views.py
def send_promotional_campaign(request):
    """Send promotional offer to specific customer segment"""
    form = CampaignForm(request.POST)
    if form.is_valid():
        customers = Customer.objects.filter(
            segment=form.cleaned_data['target_segment']
        )
        
        # Create notice group for campaign
        group = NoticeGroup.objects.create(
            name=f"Campaign: {form.cleaned_data['campaign_name']}",
            description=form.cleaned_data['description']
        )
        
        # Bulk create notifications
        notifications = []
        for customer in customers:
            notification = Notification(
                group=group,
                customer=customer,
                notice_type=NoticeTypeConfig.objects.get(code='PROMOTIONAL'),
                medium_type='WhatsApp',  # Use WhatsApp for promotions
                message=form.cleaned_data['message'],
            )
            notifications.append(notification)
        
        Notification.objects.bulk_create(notifications)
        
        # Send asynchronously
        send_group_notifications.delay(group.id)
        
        return redirect('marketing:campaign_detail', group.id)
```

### Integration API

To make it even easier for other modules, provide a simple service layer:

```python
# notify/services.py
class NotificationService:
    @staticmethod
    def create_notification(customer, notice_type_code, related_objects=None, 
                          medium_type='Email', scheduled_for=None, context=None):
        """
        Universal notification creation API for all business modules.
        
        Args:
            customer: Customer/Vendor/Employee to notify
            notice_type_code: String code like 'INVOICE_REMINDER', 'PO_APPROVED'
            related_objects: List of any Django model instances (invoices, loans, etc.)
            medium_type: 'Email', 'SMS', 'WhatsApp', 'Post'
            scheduled_for: DateTime to send (None = send now)
            context: Dict of additional template variables
        
        Returns:
            Notification instance
        """
        notice_type = NoticeTypeConfig.objects.get(code=notice_type_code)
        
        notification = Notification.objects.create(
            customer=customer,
            notice_type=notice_type,
            medium_type=medium_type,
            scheduled_for=scheduled_for,
        )
        
        # Add related objects (any type)
        if related_objects:
            for obj in related_objects:
                notification.add_item(obj)
        
        # Generate message from template
        notification.generate_message(extra_context=context)
        
        # Send immediately if not scheduled
        if not scheduled_for:
            notification.send_notification()
        
        return notification
```

---

### Advanced Features

1. **Cross-App Integration Examples**
   - **Sales App:** Payment reminders, shipment tracking, promotional offers
   - **Purchase App:** Vendor PO notifications, delivery confirmations, payment schedules
   - **Inventory App:** Stock alerts, reorder notifications to suppliers
   - **Accounting App:** GST filing reminders, payment reconciliation alerts
   - **HR/Payroll:** Salary slips, leave approvals, attendance alerts
   
2. **Multi-Language Support**
   - Store templates per language
   - Detect customer preferred language from profile
   - Auto-translate using service (Google Translate API)

2. **Rich Media Notifications**
   - Attach PDF loan statements to WhatsApp messages
   - Send images/QR codes for payment
   - HTML email templates with branding

3. **Two-Way Communication**
   - Handle customer replies (SMS/WhatsApp)
   - Update notification status based on keywords ("PAID", "CONFIRM", etc.)
   - Create support tickets from replies

4. **AI-Powered Optimization**
   - Best time to send (when customer is likely to read)
   - Channel preference learning (SMS vs WhatsApp response rates)
   - Predictive escalation (who needs Final Notice vs will pay after First)

5. **Integration Hub**
   - Email via SendGrid/AWS SES
   - Voice calls via Twilio Voice
   - Push notifications (if mobile app exists)
   - Postal mail via Lob.com API

6. **Analytics Dashboard**
   - Delivery rates by channel
   - Response rates by notice type
   - Cost per notification
   - Customer engagement metrics

7. **A/B Testing**
   - Test different message templates
   - Test different sending times
   - Track which variations get better payment rates

8. **Preference Center**
   - Let customers opt-in/out of channels
   - Set preferred contact method
   - Frequency preferences (max 1 per week, etc.)

---

## Testing Strategy

### Unit Tests
```python
class NotificationModelTest(TestCase):
    def test_message_generation(self):
        notification = NotificationFactory()
        notification.generate_message()
        self.assertIn(notification.customer.name, notification.message)
    
    def test_status_transition(self):
        notification = NotificationFactory(status='D')
        notification.update_status('S')
        self.assertEqual(notification.status, 'S')
        self.assertIsNotNone(notification.sent_at)

class NotificationServiceTest(TestCase):
    def test_determine_notice_type_overdue(self):
        loan = LoanFactory(maturity_date=date.today() - timedelta(days=45))
        notice_type = NotificationService.determine_notice_type(loan)
        self.assertEqual(notice_type, Notification.NoticeType.Second_Reminder)
```

### Integration Tests
```python
from unittest.mock import patch, MagicMock

class SMSIntegrationTest(TestCase):
    @patch('apps.tenant_apps.notify.models.Client')
    def test_send_sms_success(self, mock_client):
        mock_client.return_value.messages.create.return_value = MagicMock(sid='SM123')
        
        notification = NotificationFactory(medium_type='S')
        notification.send_sms()
        
        self.assertEqual(notification.status, 'S')
        self.assertIsNotNone(notification.sent_at)
```

---

## Migration Path

### Phase 0 (Week 0-2): Architectural Refactoring
**Critical foundation work - do this first**
- [ ] Create `NoticeTypeConfig` model
- [ ] Create `NotificationItem` model with generic relations
- [ ] Add ContentType fields to `Notification` model (alongside existing `loans` field)
- [ ] Seed default notice types (Loan, Sales, Purchase, General)
- [ ] Create data migration to convert existing loan notifications to generic pattern
- [ ] Update `NotificationTemplate` to work with generic items
- [ ] Create signals for notification triggers
- [ ] Update forms and views to work with both old and new patterns
- [ ] Document generic API for other apps

### Phase 1 (Week 3-4): Foundation
- [ ] Add missing fields (sent_at, scheduled_for, etc.)
- [ ] Implement generic message generation with template rendering
- [ ] Register admin interfaces (✅ partially done)
- [ ] Add indexes
- [ ] Create tests for generic notification creation

### Phase 2 (Week 5-6): Core Sending
- [ ] Add Email to MediumType choices in model
- [ ] Implement Email sending (SMTP/SendGrid/AWS SES)
- [ ] Create HTML email templates
- [ ] Implement SMS sending (Twilio)
- [ ] Implement WhatsApp sending
- [ ] Add status webhook handlers (email open tracking, SMS delivery, etc.)
- [ ] Create status audit log
- [ ] Add preference fields for email configuration (SMTP settings, from address)

### Phase 3 (Week 7-8): Automation
- [ ] Add scheduled notification support
- [ ] Create Celery tasks for async sending
- [ ] Implement retry logic
- [ ] Build escalation workflow
- [ ] Integrate signals in girvi app

### Phase 4 (Week 9-10): Polish & Expansion
- [ ] Performance optimization (bulk operations)
- [ ] Security hardening (tenant isolation, permissions)
- [ ] Analytics dashboard
- [ ] Comprehensive testing
- [ ] Create example integrations for sales/purchase apps
- [ ] Documentation for other developers

---

## Configuration via Dynamic Preferences

Add to `dynamic_preferences_registry.py`:

```python
notification_section = Section("Notification")

@company_preference_registry.register
class TwilioAccountSID(StringPreference):
    section = notification_section
    name = "twilio_sid"
    default = ""

@company_preference_registry.register
class TwilioAuthToken(StringPreference):
    section = notification_section
    name = "twilio_token"
    default = ""

@company_preference_registry.register
class NotificationReminderDays(IntegerPreference):
    section = notification_section
    name = "reminder_interval_days"
    default = 7
    help_text = "Days between notification reminders"

@company_preference_registry.register
class MaxNotificationsPerDay(IntegerPreference):
    section = notification_section
    name = "max_daily_notifications"
    default = 100

@company_preference_registry.register
class EmailFromAddress(StringPreference):
    section = notification_section
    name = "email_from_address"
    default = "noreply@example.com"
    help_text = "Email address to send notifications from"

@company_preference_registry.register
class EmailFromName(StringPreference):
    section = notification_section
    name = "email_from_name"
    default = "Notifications"
    help_text = "Display name for email sender"
```

---

## Cost Estimation

**Email (Recommended for bulk):**
- SendGrid/AWS SES: Almost free (< ₹0.10 per 1000 emails)
- Django SMTP (company email): Free but may have sending limits
- Best for: All notification types, with PDF attachments
- Deliverability: High if domain is properly configured (SPF, DKIM)

**SMS Costs (via Twilio India):**
- ₹0.50 - ₹1.50 per SMS
- For 1000 customers: ₹500 - ₹1500
- Best for: Critical notices, high urgency

**WhatsApp Costs:**
- Template messages: ₹0.40 - ₹0.80
- Session messages (replies): Free for 24h
- Best for: Reminders, two-way communication

**Post/Letter (Manual):**
- Indian Inland Letter: ₹5 per item
- Printing: ₹2-3 per page
- Labor for printing and mailing: Variable
- Best for: Legal notices, formal documentation

**Recommendation:** 
1. **Primary:** Email (free, fast, can attach PDF, trackable)
2. **Critical:** SMS for urgent/final notices
3. **Engagement:** WhatsApp for reminders (cheaper than SMS, higher open rates)
4. **Legal:** Post/Letter for formal/legal requirements only

---

## Document Status

**Version:** 1.0  
**Last Updated:** 2026-02-24  
**Status:** Draft for Implementation  
**Next Review:** After Phase 0 completion

---

## Key Takeaways

1. **Current State:** Notification system works but is limited to Loan/Girvi module only
2. **Priority 0 (Critical):** Refactor to generic architecture using ContentTypes
3. **After Refactoring:** Any business module (Sales, Purchase, Inventory, etc.) can use the notification system immediately
4. **Integration:** Simple 2-line signal connection or `NotificationService.create_notification()` API call
5. **Channels:** Email (primary), SMS (critical), WhatsApp (engagement), Post (legal)
6. **Timeline:** 10-week implementation with Phase 0 being the most important foundation

**Bottom Line:** Invest in Phase 0 architectural refactoring now to avoid building duplicate notification systems in every future business module. This creates a scalable, maintainable notification hub for the entire SaaS platform.
