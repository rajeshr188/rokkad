---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Notify V2 Redesign Blueprint

> **Purpose:** define the clean-slate target architecture for the `notify` app if backward compatibility is not a constraint.
>
> **Status:** design reference / target-state blueprint
>
> **Implementation status:**
> - Phase 1 foundation scaffold: [`apps/tenant_apps/notify_v2/docs/PHASE_1_FOUNDATION.md`](../../notify_v2/docs/PHASE_1_FOUNDATION.md)
> - Phase 2 batch reminder workflow slice: [`apps/tenant_apps/notify_v2/docs/PHASE_2_BATCH_WORKFLOW.md`](../../notify_v2/docs/PHASE_2_BATCH_WORKFLOW.md)
> - Digital delivery slice implemented in `apps/tenant_apps/notify_v2/services/delivery_service.py` and the batch UI send action
>
> **Last updated:** 2026-04-09

---

## 1) Design goals

The redesigned `notify` app should be:

1. **Event-driven** â€” business modules emit events; notify decides what to send.
2. **Domain-agnostic** â€” one notification system for Girvi, Sales, Purchase, Inventory, HR, and future apps.
3. **Channel-native** â€” PDF print, email, SMS, WhatsApp, and in-app are first-class channels.
4. **Asynchronous and reliable** â€” delivery should happen through queued jobs with retries and audit logs.
5. **Tenant-safe** â€” every record is tenant-scoped and operationally isolated.
6. **Operator-friendly** â€” templates, preview, retries, failures, and artifacts should be visible in admin/UI.
7. **Legally printable** â€” Girvi overdue and auction notices must support fixed PDF layouts.

---

## 2) What to remove from the current V1 design

If we are redesigning without compatibility constraints, remove these ideas entirely:

- the dual model of `notice_type` **and** `notice_type_config`
- the legacy `Notification.loans` M2M field
- view-level PDF assembly and ad-hoc queryset-driven printing
- delivery methods on the model itself (`send_email()`, `send_sms()`, etc.)
- mixing business object relationships and delivery lifecycle in one table
- treating the notification record as both template definition and delivery attempt

The new system should separate:

- **event definition**
- **template definition**
- **rendering**
- **delivery**
- **audit trail**

---

## 3) Target domain model

### 3.1 `NotificationEventType`
Defines the business event contract.

| Field | Purpose |
|---|---|
| `key` | Unique event key like `loan.first_reminder_due` |
| `name` | Operator-friendly label |
| `domain` | `loan`, `sales`, `purchase`, etc. |
| `description` | Business meaning |
| `payload_schema` | JSON schema / expected context contract |
| `is_active` | Enable or disable the event |

Examples:
- `loan.created`
- `loan.first_reminder_due`
- `loan.final_notice_due`
- `loan.auction_notice_due`
- `sales.invoice_overdue`

### 3.2 `NotificationPolicy`
Defines which channels should be used and under what conditions.

| Field | Purpose |
|---|---|
| `event_type` | The business event |
| `channel` | `EMAIL`, `SMS`, `WHATSAPP`, `LETTER`, `POST`, `IN_APP` |
| `priority` | Ordering / urgency |
| `is_required` | Whether this channel is mandatory |
| `cooldown_rule` | Prevent duplicate sends |
| `schedule_rule` | Immediate / delayed / escalation |
| `is_active` | Enable or disable policy |

This is where business rules live, not inside views.

### 3.3 `NotificationTemplate`
One template per `event_type + channel + locale + version`.

| Field | Purpose |
|---|---|
| `event_type` | Event being rendered |
| `channel` | Output channel |
| `locale` | Language support |
| `renderer_type` | `PDF`, `DJANGO`, `TEXT`, `HTML` |
| `subject_template` | Email subject / title |
| `body_template` | Main template content |
| `layout_key` | PDF layout selector |
| `version` | Template version for audit |
| `is_active` | Current active template |

### 3.4 `NotificationRecipient`
Normalized recipient identity and contact endpoints.

| Field | Purpose |
|---|---|
| `customer` | Optional FK to contact entity |
| `name_snapshot` | Preserve name at send time |
| `email` | Email endpoint |
| `phone` | SMS / WhatsApp endpoint |
| `postal_address_json` | Printable address snapshot |
| `preferred_locale` | Language preference |
| `consent_flags` | Opt-in / opt-out metadata |

### 3.5 `NotificationEvent`
Immutable business event instance.

| Field | Purpose |
|---|---|
| `event_type` | Type of event |
| `recipient` | Who this event is for |
| `source_app` | e.g. `girvi` |
| `source_model` | e.g. `GivenLoan` |
| `source_pk` | Source object PK |
| `payload` | JSON snapshot used for rendering |
| `dedupe_key` | Prevent duplicates |
| `created_at` | Event creation timestamp |

> **Important:** V2 should store a **payload snapshot** rather than relying on live model traversal at render time. This makes notices auditable and stable.

### 3.6 `NotificationBatch`
Represents an operator-created bulk notification run.

This is the V2 replacement for the current `NoticeGroup` concept and is especially important for Girvi reminder and auction workflows where staff select many loans, generate notices in bulk, print them, and post them manually.

| Field | Purpose |
|---|---|
| `name` | Operator-facing batch name |
| `event_type` | Event being run in bulk |
| `created_by` | User who initiated the run |
| `status` | `DRAFT`, `RENDERED`, `PRINTED`, `POSTED`, `CANCELLED` |
| `job_count` | Number of jobs created |
| `printed_at` | When the print bundle was generated |
| `posted_at` | When the operator marked the batch as manually posted |
| `notes` | Operator remarks |

### 3.7 `NotificationJob`
One outbound job per channel.

| Field | Purpose |
|---|---|
| `event` | Related event |
| `batch` | Optional parent batch for bulk operations |
| `channel` | Delivery channel |
| `template` | Template used |
| `status` | `QUEUED`, `RENDERED`, `SENT`, `FAILED`, `CANCELLED` |
| `scheduled_for` | When to attempt delivery |
| `sent_at` | Actual send time |
| `provider_message_id` | External provider reference |
| `failure_reason` | Failure details |
| `attempt_count` | Retry count |

### 3.8 `NotificationArtifact`
Stores rendered output.

| Field | Purpose |
|---|---|
| `job` | Related job |
| `artifact_type` | `PDF`, `HTML`, `TEXT` |
| `file` | Stored file for PDFs |
| `rendered_text` | Final plain text / HTML |
| `metadata` | Render and provider metadata |

### 3.9 `NotificationAttemptLog`
Immutable operational audit trail.

| Field | Purpose |
|---|---|
| `job` | Related job |
| `attempt_number` | Which retry number |
| `status_before` | Previous status |
| `status_after` | New status |
| `message` | Human-readable log |
| `created_at` | Timestamp |

---

## 4) Service architecture

The new app should use explicit services instead of model-heavy behavior.

### Core services

- `event_service.py`
  - validates and records `NotificationEvent`
- `policy_service.py`
  - decides which channels/jobs to create
- `render_service.py`
  - resolves the correct template and creates `NotificationArtifact`
- `dispatch_service.py`
  - hands jobs to the correct adapter
- `retry_service.py`
  - retry / backoff / dead-letter handling
- `preference_service.py`
  - opt-out and channel eligibility checks

### Channel adapters

- `adapters/email.py`
- `adapters/sms.py`
- `adapters/whatsapp.py`
- `adapters/print.py`
- `adapters/in_app.py`

Each adapter should implement a small common contract:

```python
class BaseChannelAdapter:
    channel = None

    def send(self, *, job, artifact):
        raise NotImplementedError
```

Current implementation notes:

- **Email** is wired through Django's `send_mail()` path for real deliverability in configured environments.
- **SMS** remains integrated with Twilio when `TWILIO_*` settings are present.
- **WhatsApp** now supports a provider switch:
  - `NOTIFY_V2_WHATSAPP_PROVIDER=twilio` keeps the current Twilio route
  - `NOTIFY_V2_WHATSAPP_PROVIDER=cloud` uses Meta's WhatsApp Cloud API via Graph
  - required Cloud settings: `WHATSAPP_CLOUD_API_VERSION`, `WHATSAPP_CLOUD_PHONE_NUMBER_ID`, `WHATSAPP_CLOUD_ACCESS_TOKEN`, and `WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN`
  - when `NotificationTemplate.layout_key` is set, Cloud dispatch uses a template message; otherwise it falls back to text mode
  - status callbacks are handled at `/notify-v2/webhooks/whatsapp/cloud/` and reconciled against `NotificationJob.provider_message_id`
- A controlled fallback stub can remain enabled via `NOTIFY_V2_TWILIO_STUB_FALLBACK` during rollout.
- The batch detail UI now exposes a **Send Digital** action for eligible `EMAIL`, `SMS`, and `WHATSAPP` jobs.

---

## 5) Rendering design

### 5.1 PDF rendering for Girvi legal notices
Loan overdue reminders and auction notices should remain **PDF-first** where a predefined printable layout is required.

Recommended structure:

```text
apps/tenant_apps/notify/
  renderers/
    pdf/
      loan_first_reminder.py
      loan_final_notice.py
      loan_auction_notice.py
```

Each renderer should accept a normalized payload snapshot:

```python
def render(payload: dict, template: NotificationTemplate) -> NotificationArtifact:
    ...
```

### 5.2 Django/HTML/text rendering for digital channels
For email, SMS, and WhatsApp, use template rendering with a strict context contract.

Example payload for a Girvi loan reminder:

```json
{
  "customer": {
    "name": "Asha",
    "email": "asha@example.com"
  },
  "loan": {
    "loan_id": "GL-001",
    "principal": "10000.00",
    "due_date": "2026-04-15",
    "branch_name": "Main Branch"
  },
  "totals": {
    "due_amount": "11250.00"
  }
}
```

The renderer should not reach back into live Django models unless explicitly needed.

---

## 6) Execution flow

```text
Business domain action
â†’ emit NotificationEvent
â†’ resolve NotificationPolicy rows
â†’ create NotificationJob per selected channel
â†’ render NotificationArtifact
â†’ dispatch through channel adapter
â†’ store result and provider metadata
â†’ update audit log
```

### Example: `loan.auction_notice_due`

1. Girvi service determines a loan entered auction workflow.
2. It emits `NotificationEvent(event_type="loan.auction_notice_due", payload=...)`.
3. Policy service decides:
   - `LETTER` is required
   - `EMAIL` is optional if email exists
   - `SMS` is optional if consent exists
4. Three jobs are created.
5. The `LETTER` job uses a PDF renderer.
6. `EMAIL` and `SMS` use Django/text templates.
7. Dispatch happens asynchronously.
8. Operators can inspect the rendered PDF and send history in admin.

### Example: bulk reminder notice creation for manual post

This explicitly covers the current business need where a staff user selects many loans, creates reminder notices, prints them all, and posts them manually.

```text
Select loans in Girvi UI
â†’ choose â€œCreate Reminder Batchâ€
â†’ create NotificationBatch
â†’ group loans by borrower or notice policy
â†’ create one NotificationEvent per recipient
â†’ create one LETTER/POST NotificationJob per recipient
â†’ render PDFs
â†’ provide combined print bundle + individual files
â†’ operator prints all
â†’ operator marks batch as POSTED_MANUALLY
```

Recommended operator actions for a `NotificationBatch`:
- **Render batch**
- **Download merged PDF**
- **Print all**
- **Mark printed**
- **Mark posted manually**
- **Export posting register**

---

## 7) Suggested package layout

```text
apps/tenant_apps/notify/
  admin.py
  api/
    views.py
    serializers.py
  domain/
    events.py
    policies.py
    recipients.py
  models.py
  services/
    event_service.py
    policy_service.py
    render_service.py
    dispatch_service.py
    retry_service.py
  renderers/
    django_renderer.py
    pdf/
      loan_first_reminder.py
      loan_final_notice.py
      loan_auction_notice.py
  adapters/
    email.py
    sms.py
    whatsapp.py
    print.py
    in_app.py
  tasks/
    dispatch_jobs.py
    retry_failed_jobs.py
  docs/
    NOTIFY_V2_REDESIGN_BLUEPRINT.md
```

---

## 8) Admin and operator UX

The redesigned admin/workspace UI should support:

### Templates
- create/edit template per event and channel
- test render with sample payload
- preview final PDF or email body
- activate/deactivate template versions

### Operations dashboard
- queued / sent / failed counters
- filter by event, channel, status, tenant, date
- inspect payload snapshot
- inspect rendered artifact
- retry failed jobs
- cancel queued jobs
- view and manage `NotificationBatch` runs for bulk reminder/auction printing

### Batch print / manual post workflow
- select a group of loans from Girvi
- create a batch for `First Reminder`, `Final Notice`, or `Auction Notice`
- generate one PDF per customer or per loan depending on policy
- optionally download a merged PDF bundle for one-click printing
- mark the batch as `PRINTED`
- mark the batch as `POSTED` once branch staff mails the notices manually
- retain an audit trail of who generated, printed, and posted the batch

### Audit
- full attempt history
- provider IDs and error messages
- exportable compliance logs for printed/legal notices

---

## 9) API contract for business modules

Other apps should not create notification records directly.
They should emit events through one entry point:

```python
from apps.tenant_apps.notify.services.event_service import emit_event

emit_event(
    event_key="loan.first_reminder_due",
    recipient=borrower,
    payload={
        "customer": {...},
        "loan": {...},
        "totals": {...},
    },
    source_app="girvi",
    source_model="GivenLoan",
    source_pk=loan.pk,
)
```

That keeps Girvi, Sales, Purchase, and future modules decoupled from the notify internals.

---

## 10) Async processing and reliability

V2 should be queue-based from day one.

Recommended features:

- Celery or Huey-based job execution
- retry with exponential backoff
- max retry threshold and dead-letter status
- idempotency via `dedupe_key`
- provider timeout handling
- alerting for repeated failures

This is especially important for SMS, WhatsApp, and email provider errors.

---

## 11) Security and tenant isolation

The redesign must enforce:

- tenant-scoped queries only
- explicit permissions for template editing vs delivery operations
- opt-out / consent rules for digital channels
- immutable audit logs for legal notices
- safe storage of provider credentials through environment or secret manager

---

## 12) Phased implementation plan

Even though V2 itself would not preserve backward compatibility, the build-out can still be phased.

### Phase 1 â€” Foundation
- `NotificationEventType`, `NotificationPolicy`, `NotificationEvent`, `NotificationBatch`, `NotificationJob`
- add a minimal event emit API
- create admin screens for event types, templates, and batch runs

### Phase 2 â€” Rendering
- add Django renderer and PDF renderer interfaces
- build Girvi overdue reminder and auction notice PDF renderers
- support email/SMS text rendering

### Phase 3 â€” Dispatch
- implement email adapter
- implement SMS adapter
- implement WhatsApp adapter
- implement print/download adapter

### Phase 4 â€” Operations
- add queue workers, retries, and audit views
- add resend / requeue / cancel actions
- add template preview tooling

### Phase 5 â€” Cutover
- switch Girvi reminder flows to emit events instead of writing notification rows directly
- decommission V1 notify flows
- archive or drop obsolete tables and fields

---

## 13) Recommended cutover strategy for this repo

If backward compatibility is truly irrelevant, the cleanest path is:

1. freeze the current `notify` app as V1
2. build the new architecture under the same app or as `notify_v2`
3. migrate Girvi reminder generation to emit events only
4. validate print/email/SMS flows end-to-end
5. remove obsolete models and fields in one controlled cleanup

This avoids carrying legacy branching in the core design.

---

## 14) Why this fits Rokkad best

This design matches the product reality:

- **Girvi legal notices** need fixed printable PDF outputs
- **Digital reminders** need flexible template-driven messaging
- **Other business modules** will need the same notification infrastructure later
- **Tenant operations** need visibility, retries, and auditability

A clean event â†’ template â†’ render â†’ dispatch pipeline gives that without coupling the system to `GivenLoan` or any one domain.

---

## 15) Final recommendation

For a true V2 redesign, the notify app should become a **platform notification engine**, not a loan-centric model with extra delivery methods.

The target architecture should be:

- **event-driven**
- **template-versioned**
- **channel-adapter based**
- **queue-backed**
- **artifact/audit oriented**
- **PDF-first for legal Girvi notices**
- **Django-template-first for digital channels**

