---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Notify App Implementation & Loan Integration Guide

This guide explains how the `notify` app is currently implemented in this repository, how it works today, and how to integrate it with the Girvi loan flow for reminders, maturity alerts, and auction notices across print, email, SMS, and WhatsApp.

---

## 1) What the `notify` app is for

The `notify` app is the tenant-level communication layer for customer-facing notices.

It is designed to support:
- **Loan reminders** for overdue or matured Girvi loans
- **Auction notices** before forced closure / auction workflow
- **Welcome / loan-created notices**
- **Multi-channel delivery**: `Post`, `Letter`, `Email`, `SMS`, `WhatsApp`
- **Single or batch sending** through `Notification` and `NoticeGroup`

In the current codebase, the **data model is already generic**, and the **Girvi integration is actively using the newer service-based pattern for reminders and auction notices, while a few older loan-specific paths still remain for backward compatibility**.

---

## 2) Key files in the implementation

| Area | File |
|---|---|
| Core models | `apps/tenant_apps/notify/models.py` |
| Admin setup | `apps/tenant_apps/notify/admin.py` |
| Forms | `apps/tenant_apps/notify/forms.py` |
| Views | `apps/tenant_apps/notify/views.py` |
| Routes | `apps/tenant_apps/notify/urls.py` |
| Existing Girvi single-loan hook | `apps/tenant_apps/girvi/views/notice.py` |
| Existing Girvi bulk notice flow | `apps/tenant_apps/girvi/views/prints.py` |
| Existing SMS helper | `apps/tenant_apps/girvi/msg.py` |
| Existing legacy reminder tasks | `apps/tenant_apps/girvi/tasks.py` |
| PDF generation helper | `apps/tenant_apps/utils/loan_pdf.py` |

The tenant route is already mounted in:
- `django_project/tenant_urls.py` â†’ `path("notify/", include("apps.tenant_apps.notify.urls"))`

The app is already installed in:
- `django_project/settings/base.py`

---

## 3) Core data model

### `NoticeTypeConfig`
Located in `notify/models.py`.

This is the **configuration layer** for notice templates. It stores:
- `code` â†’ unique identifier like `LOAN_FIRST_REMINDER`
- `name` â†’ user-facing name
- `category` â†’ `LOAN`, `SALES`, `PURCHASE`, etc.
- per-medium templates:
  - `sms_template`
  - `whatsapp_template`
  - `email_subject_template`
  - `email_template`
  - `postal_template`

Use this model to define business notice types such as:
- `LOAN_FIRST_REMINDER`
- `LOAN_SECOND_REMINDER`
- `LOAN_FINAL_NOTICE`
- `LOAN_AUCTION_NOTICE`
- `LOAN_MATURITY_ALERT`

### `NoticeGroup`
Container for **batch operations**.

Use this when sending notices for many customers at once, for example:
- all loans overdue > 30 days
- all auction notices due this week
- monthly reminder runs

### `Notification`
Represents one customer-facing notice.

Important fields:
- `group`
- `customer`
- `medium_type`
- `notice_type` (**legacy**)
- `notice_type_config` (**recommended**)
- `status`
- `message`
- `is_printed`

It also exposes the main workflow methods:
- `generate_message()`
- `send_notification()`
- `send_email()`
- `send_sms()`
- `send_whatsapp()`
- `print_letter()`

### `NotificationItem`
This is the **generic relation layer**.

It links a `Notification` to any business object using Django `ContentType`.
For loans, this means one notification can point to one or many `GivenLoan` rows.

Recommended usage for new code:
- create `Notification`
- call `notification.add_item(loan, amount=..., due_date=..., reference_number=...)`

---

## 4) How the app works today

### Current flow

```text
Loan event / scheduled job
    -> create Notification or NoticeGroup
    -> link loan(s) to the notification
    -> generate_message()
    -> send_notification()
    -> update status / print / audit
```

### Message generation
`Notification.generate_message()` already supports template rendering via Django templates.

Available context includes:
- `customer`
- `notification`
- `items`
- `total_amount`
- `notice_type`

If no template is configured, it falls back to a simple default message.

### Delivery routing
`Notification.send_notification()` chooses the medium based on `medium_type`:
- `Email` â†’ `send_email()`
- `SMS` â†’ `send_sms()`
- `WhatsApp` â†’ `send_whatsapp()`
- `Post` / `Letter` â†’ `print_letter()`

### Current implementation status

| Medium | Status | Notes |
|---|---|---|
| Post / Letter | âœ… usable | PDF print flow exists via `get_notice_pdf()` |
| Email | âœ… wired for loan reminders / auction notices | Uses `Customer.email`, Django mail backend, and notice templates |
| SMS | âš ï¸ stub in `Notification`, partial Twilio helper exists in `girvi/msg.py` |
| WhatsApp | âš ï¸ stub | requires Business API integration |

---

## 5) Existing Girvi integration points

### A. Single-loan notification
`apps/tenant_apps/girvi/views/notice.py::create_loan_notification`

Current behavior:
1. Fetches the selected `GivenLoan`
2. Calls `create_loan_reminder_notification(...)` from `apps/tenant_apps/notify/services.py`
3. Creates a `Notification` using `notice_type_config`
4. Links the loan through `NotificationItem` via `add_item(...)`
5. Generates the message from the configured template
6. Sends an email copy automatically if `Customer.email` is present
7. Redirects to the notification detail page

This is now the **preferred pattern** for new single-loan reminder and auction-notice creation.

### B. Bulk notifications from filtered loans
`apps/tenant_apps/girvi/views/prints.py::notify_print`

Current behavior:
1. Takes selected unreleased loans
2. Calls `create_bulk_loan_reminder_group(...)`
3. Creates a `NoticeGroup`
4. Groups loans by customer
5. Creates one `Notification` per borrower using the notify service layer
6. Attaches the related loans through `NotificationItem` and the compatibility `loans` relation
7. Redirects to the group detail page for printing or review

This is the main batch flow for overdue reminder generation.

### C. Legacy reminder tasks
`apps/tenant_apps/girvi/tasks.py` contains old reminder jobs like:
- `notify_pending_loans`
- `notify_interest_overdue`
- `notify_Loan_reminder`

These tasks currently build raw messages and call `notify_msg()` directly.

**Recommendation:** migrate these tasks to create `Notification` rows instead, so reminders are tracked in the `notify` app with statuses and history.

---

## 6) Recommended loan integration pattern

For new reminder and auction-notice logic, use the `notify` app as the single source of truth.

### Example helper service

```python
from apps.tenant_apps.notify.models import Notification, NoticeTypeConfig


def create_loan_notice(*, loan, notice_code, medium, group=None):
    notice_type = NoticeTypeConfig.objects.get(code=notice_code, is_active=True)

    notification = Notification.objects.create(
        group=group,
        customer=loan.borrower,
        notice_type_config=notice_type,
        medium_type=medium,
        status=Notification.StatusType.Draft,
    )

    notification.add_item(
        loan,
        amount=loan.loanamount,
        due_date=getattr(loan, "maturity_date", None),
        reference_number=loan.loan_id,
        notes=f"Loan notice for {loan.loan_id}",
    )

    notification.generate_message()
    notification.save(update_fields=["message", "last_updated"])
    return notification
```

### Where to call it from the loan app

Use this helper from:
- **loan creation** â†’ send welcome / loan-created notice
- **monthly maturity scan** â†’ send first reminder
- **overdue escalation** â†’ send second/final reminder
- **pre-auction workflow** â†’ send auction notice
- **manual loan action screen** â†’ send one-off notice from loan detail

---

## 7) Reminder and auction use cases for Girvi

### Reminder stages
A clean staged approach is:

1. `LOAN_FIRST_REMINDER`
   - trigger: first overdue threshold or nearing maturity
2. `LOAN_SECOND_REMINDER`
   - trigger: still unpaid after grace period
3. `LOAN_FINAL_NOTICE`
   - trigger: final warning before auction/closure
4. `LOAN_AUCTION_NOTICE`
   - trigger: loan moved to auction-ready or final statutory step

### Example query ideas

```python
from django.utils import timezone
from datetime import timedelta
from apps.tenant_apps.girvi.models import GivenLoan


today = timezone.localdate()

maturity_candidates = GivenLoan.objects.filter(
    release__isnull=True,
    maturity_date__lte=today + timedelta(days=7),
)

overdue_candidates = GivenLoan.objects.filter(
    release__isnull=True,
    maturity_date__lt=today,
)

auction_candidates = GivenLoan.objects.filter(
    release__isnull=True,
    maturity_date__lt=today - timedelta(days=90),
)
```

You can turn each queryset into grouped notifications by customer using `NoticeGroup`.

---

## 8) Sending through different mediums

## 8.1 Print / Post / Letter
This is the most complete path already available.

Use when:
- physical reminder letters are required
- auction notices must be printed and mailed
- branch staff needs paper copies

Current implementation uses:
- `notify/views.py::notification_print`
- `notify/views.py::noticegroup_print`
- `apps/tenant_apps/utils/loan_pdf.py::get_notice_pdf()`

### Recommended setup
- create postal templates in `NoticeTypeConfig.postal_template`
- generate `message`
- print from notification/group detail pages
- optionally mark `is_printed=True` after print success

## 8.2 Email
`Notification.send_email()` is now wired for loan reminders and auction notices when the borrower has a value in `Customer.email`.

### Current behavior
- a reminder / auction notice still creates the primary notification record (typically `Letter`)
- if `customer.email` is present, an additional email notification is created and dispatched automatically
- the email subject comes from `NoticeTypeConfig.email_subject_template`
- the email body uses the generated `message` content

### Setup steps
1. Configure Django email settings:

```python
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.your-provider.com"
EMAIL_PORT = 587
EMAIL_HOST_USER = "..."
EMAIL_HOST_PASSWORD = "..."
EMAIL_USE_TLS = True
DEFAULT_FROM_EMAIL = "noreply@yourdomain.com"
```

2. Implement the body of `Notification.send_email()` using `EmailMultiAlternatives`
3. Store templates in `NoticeTypeConfig.email_subject_template` and `email_template`
4. Update status to `Sent` on success

## 8.3 SMS
`Notification.send_sms()` is also a stub, but the repo already contains a Twilio helper in `apps/tenant_apps/girvi/msg.py`.

### Suggested wiring
- move or reuse that helper inside `notify`
- use environment variables:
  - `TWILIO_ACCOUNT_SID`
  - `TWILIO_AUTH_TOKEN`
  - `TWILIO_NUMBER`
- call the helper from `Notification.send_sms()`
- save external message IDs for audit/retry if needed

## 8.4 WhatsApp
`Notification.send_whatsapp()` is ready as an extension point but needs a provider implementation.

Typical options:
- Twilio WhatsApp
- Meta WhatsApp Business Cloud API
- another BSP provider

Recommended approach:
- create `whatsapp_template` in `NoticeTypeConfig`
- render via `generate_message()`
- send via provider SDK/API
- update notification status and store provider response ID

---

## 9) Setup checklist

### Step 1: Apply migrations

```bash
python manage.py migrate
```

This will create the `notify` tables, including:
- `NoticeTypeConfig`
- `NoticeGroup`
- `Notification`
- `NotificationItem`

There is also a seed migration:
- `apps/tenant_apps/notify/migrations/0003_seed_default_notice_types.py`

### Step 2: Verify routes
The notify UI should be available under:
- `/notify/noticegroup/`
- `/notify/notification/`

### Step 3: Configure notice types in admin
Open Django admin and review `Notice Type Configurations`.

Create or verify codes such as:
- `LOAN_FIRST_REMINDER`
- `LOAN_SECOND_REMINDER`
- `LOAN_FINAL_NOTICE`
- `LOAN_AUCTION_NOTICE`
- `LOAN_CREATED`

For each notice type, fill the relevant templates for:
- SMS
- WhatsApp
- Email subject/body
- Postal letter

### Step 4: Connect channels
- **Email** â†’ configure SMTP / email provider
- **SMS** â†’ configure Twilio or another gateway
- **WhatsApp** â†’ configure Business API provider
- **Print** â†’ ensure PDF layout in `loan_pdf.py` is correct for branch use

### Step 5: Hook the loan triggers
Add calls from the loan workflow or scheduled jobs for:
- maturity reminders
- overdue reminders
- pre-auction notices
- manual â€œsend reminderâ€ button on loan detail

### Step 6: Add scheduling
Use Celery Beat or another scheduler to run daily/monthly scans.

Recommended jobs:
- daily: maturity reminder scan
- daily: overdue escalation scan
- weekly: auction candidate scan
- monthly: printable notice batch generation

---

## 10) Suggested implementation pattern for auction notices

A robust auction-notice flow should be:

1. identify loans that crossed the auction threshold
2. create a `NoticeGroup` such as `Auction Notices - 2026-04-06`
3. create one `Notification` per borrower
4. attach the borrowerâ€™s relevant loans with `add_item()`
5. generate messages from `LOAN_AUCTION_NOTICE`
6. send via SMS/WhatsApp for fast reach
7. generate print letters for branch record and postal dispatch
8. update status as the notice progresses (`Draft` â†’ `Sent` â†’ `Acknowledged`)

This gives both:
- immediate digital delivery
- audit-friendly paper trail

---

## 11) Best practice for this repo

### Prefer the new generic API
For new code, prefer:
- `notice_type_config`
- `Notification.add_item()`
- `Notification.generate_message()`
- `Notification.send_notification()`

Avoid adding new logic on the deprecated `notification.loans` + `notice_type` path unless needed for backward compatibility.

### Move legacy reminder tasks into `notify`
The existing reminder jobs in `girvi/tasks.py` should be refactored so they:
- create notification records
- render templates centrally
- send through one notification service
- preserve history and status for each send

### Add audit fields next
If this app becomes the production reminder engine, the next useful additions are:
- `scheduled_for`
- `sent_at`
- `delivered_at`
- `failed_reason`
- `retry_count`
- `external_message_id`
- `created_by`

---

## 12) Practical rollout recommendation

For the loan app, the safest rollout order is:

1. **Use print/post first** for official reminders and auction notices
2. **Wire SMS next** using the existing Twilio helper pattern
3. **Add WhatsApp** for customer-friendly reminders
4. **Add email** for richer formatted notices and branch records
5. **Move all scheduled reminders into `notify`** so every notice is tracked centrally

---

## 13) Summary

The `notify` app is already a strong foundation for a centralized notification system:
- the **generic data model is in place**
- the **loan integration entry points already exist**
- the **print workflow is usable now**
- the **SMS/Email/WhatsApp hooks are ready to be wired**

For Girvi, it can be used immediately for:
- overdue reminders
- maturity reminders
- final notices
- auction notices

The recommended path is to standardize all new loan reminders on `NoticeTypeConfig` + `NotificationItem`, then gradually connect the actual delivery providers for SMS, WhatsApp, and email.

