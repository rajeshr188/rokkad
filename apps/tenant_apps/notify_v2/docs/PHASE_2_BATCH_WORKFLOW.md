# Notify V2 Phase 2: Girvi Batch Reminder Workflow

## Scope implemented in this phase slice

This phase starts the first real operational workflow for `notify_v2`:

- select a group of Girvi loans
- create a `NotificationBatch`
- group the selection by borrower
- create recipient snapshots, events, and letter jobs
- render a merged PDF bundle for manual print/post handling
- mark jobs and batch as `RENDERED`

## Core services

- `apps/tenant_apps/notify_v2/services/batch_service.py`
  - `ensure_girvi_batch_defaults()`
  - `preview_girvi_reminder_batch()`
  - `create_girvi_reminder_batch()`
  - `render_batch_pdf()`

- `apps/tenant_apps/notify_v2/renderers/pdf/girvi.py`
  - `render_girvi_notice_bundle()`

## Current behavior

- a selected list of loans can now be turned into a `NotificationBatch`
- one `NotificationEvent` and one printable `NotificationJob` are created per borrower group
- a default event type/policy/template is auto-created if missing
- a dedicated `notify_v2` Girvi PDF renderer now produces a merged printable notice bundle without depending on the legacy `loan_pdf.py` notice builder
- each printable job stores a persisted `NotificationArtifact` PDF file for audit/download purposes
- the batch detail UI includes `Send Digital` for `EMAIL`/`SMS`/`WHATSAPP` jobs
- digital dispatch is handled by `apps/tenant_apps/notify_v2/services/delivery_service.py`
  - `EMAIL` uses Django `send_mail()`
  - `SMS` uses the existing Twilio adapter path
  - `WHATSAPP` defaults to Twilio, with an optional Meta WhatsApp Cloud API provider switch

## WhatsApp provider configuration

`notify_v2` now supports two WhatsApp delivery modes behind a setting switch:

### 1. Default: Twilio WhatsApp

```env
NOTIFY_V2_WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+15550001111
TWILIO_WHATSAPP_FROM_NUMBER=+15550002222
```

### 2. Future-ready: Meta WhatsApp Cloud API

```env
NOTIFY_V2_WHATSAPP_PROVIDER=cloud
WHATSAPP_CLOUD_API_VERSION=v20.0
WHATSAPP_CLOUD_PHONE_NUMBER_ID=your_phone_number_id
WHATSAPP_CLOUD_ACCESS_TOKEN=your_long_lived_token
WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN=choose_a_secret_verify_token
```

Operational notes:

- only the `WHATSAPP` channel uses the provider switch; `SMS` remains on the Twilio path
- set `NOTIFY_V2_TWILIO_STUB_FALLBACK=False` to fail fast during rollout or production validation
- when Cloud mode is enabled, `notify_v2` stores the returned Graph API message id on the `NotificationJob`
- if the template has a `layout_key`, `notify_v2` sends a **template-based Cloud message**; otherwise it falls back to a plain text WhatsApp message

### Template-based Cloud messages

For approved Meta templates, use the `NotificationTemplate.layout_key` as the WhatsApp template name and optionally define component payloads inside `sample_payload["whatsapp_template"]`.

Example:

```python
sample_payload = {
    "whatsapp_template": {
        "components": [
            {
                "type": "body",
                "parameters": [
                    {"type": "text", "text": "{{ customer.name }}"},
                    {"type": "text", "text": "{{ loan_count }}"},
                ],
            }
        ]
    }
}
```

Rendered values are resolved from the job context before the Graph API call is made.

### Delivery status webhook

Endpoint:

```text
/notify-v2/webhooks/whatsapp/cloud/
```

Behavior:

- `GET` handles Meta webhook verification using `WHATSAPP_CLOUD_WEBHOOK_VERIFY_TOKEN`
- `POST` processes `sent`, `delivered`, `read`, and `failed` statuses
- status callbacks are matched using `NotificationJob.provider_message_id`
- failures are recorded on the job and webhook payloads are appended to the attempt log

## Next step after this slice

- connect the batch service to Girvi UI actions
- expose batch list/detail/print views in `notify_v2`
- add dedicated `notify_v2` PDF layout renderers instead of relying on the legacy helper
- support `PRINTED` and `POSTED` UI actions for branch staff
