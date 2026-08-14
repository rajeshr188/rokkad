---
status: active
owner: project
updated: 2026-07-02
tags: [whatsapp, notifications, architecture, audit, tenancy, compliance]
related: [../domain/notifications.md, ../STATUS.md, ../AGENT_MEMORY.md, tenancy-architecture-audit-rls-vs-django-tenants.md]
---

# WhatsApp / Notifications Architecture Audit

This document captures the current implementation state of WhatsApp and notification flows in Rokkad, the tenant-safety risks, and the target architecture recommended for future implementation.

## Executive Summary

Rokkad currently has two notification stacks:

- `notify`: a legacy tenant app centered on `Notification`, `NoticeGroup`, and template-backed message generation.
- `notify_v2`: a more structured tenant app with event, policy, template, batch, job, artifact, and webhook handling.

The codebase can generate Girvi reminder batches, print PDFs, and send WhatsApp
digital jobs through Meta WhatsApp Cloud API settings. Twilio support has been
removed and SMS has no selected provider. It is not yet a complete tenant-scoped
communications platform:

- WhatsApp provider credentials are workspace-owned encrypted integrations;
  global credential settings have been removed.
- The WhatsApp Cloud webhook exists, but it is only challenge-verified and does not verify provider signatures.
- The webhook path currently sits inside tenant URL space, so the middleware/auth path can block provider callbacks unless explicitly exempted.
- Inbound processing is status-only; there is no inbox/conversation model and no raw webhook event table.
- Consent and opt-out are not modeled strongly enough for marketing-grade use.

Recommendation: adopt a **hybrid model**.

- Use a Rokkad-owned number for platform/system communication such as onboarding, invites, OTP/auth, billing, and workspace alerts.
- Use workspace-owned numbers for all tenant-to-customer communication such as receipts, reminders, service notices, campaigns, and marketing.

This is the best fit for brand trust, compliance, routing simplicity, and long-term scale.

## Current Implementation Map

### Legacy `notify`

- Models live in [apps/tenant_apps/notify/models.py](../../apps/tenant_apps/notify/models.py).
- Core entities are `NoticeTypeConfig`, `NoticeGroup`, `NotificationItem`, `Notification`, and `NotificationTemplate`.
- `NoticeTypeConfig` stores SMS, WhatsApp, email, and postal template text per notice code.
- `Notification` is tenant-scoped by schema, not by explicit workspace foreign key.
- `Notification.send_whatsapp()` and `Notification.send_sms()` are stubs.
- `Notification.send_email()` is the only fully implemented send path.
- Printing is implemented through PDF generation, not through provider delivery.

### `notify_v2`

- Models live in [apps/tenant_apps/notify_v2/models.py](../../apps/tenant_apps/notify_v2/models.py).
- The data model is more operational:
  - `NotificationEventType`
  - `NotificationPolicy`
  - `NotificationRecipient`
  - `NotificationTemplate`
  - `NotificationBatch`
  - `NotificationEvent`
  - `NotificationJob`
  - `NotificationArtifact`
  - `NotificationAttemptLog`
- `NotificationRecipient` carries `customer`, `party`, `email`, `phone`, and a generic `consent_flags` JSON field.
- `NotificationJob` tracks `status`, `sent_at`, `provider_message_id`, `failure_reason`, `attempt_count`, and `last_attempt_at`.
- `NotificationBatch` is the user-facing batch container.

### Delivery logic

- Delivery logic lives in [apps/tenant_apps/notify_v2/services/delivery_service.py](../../apps/tenant_apps/notify_v2/services/delivery_service.py).
- Email goes through Django mail.
- WhatsApp goes through Meta WhatsApp Cloud API exclusively.
- SMS fails closed until a separate provider is deliberately selected.
- Callback POSTs require `X-Hub-Signature-256` verified with the active
  workspace integration's decrypted app secret, its configured phone-number
  ID, and a tenant schema route. Each status event is persisted by content hash and replays do
  not reapply job state.
- Outbound WhatsApp is template-only. Set the approved Meta template name in
  the Notify template `layout_key` or `sample_payload.whatsapp_template.name`.

Run the tenant readiness and reconciliation gate with:

```powershell
python manage.py tenant_command check_whatsapp_cloud_readiness --schema=TENANT_SCHEMA --fail-on-blocker --format=json
```

The gate checks all four Cloud settings, unknown authenticated receipts, and
sent jobs without a callback after 24 hours.
- Message rendering uses Django templates and optional `sample_payload["whatsapp_template"]` structure.
- Status webhooks only update job delivery status by matching `provider_message_id`.

### Girvi triggers

- Single-loan notice creation is in [apps/tenant_apps/girvi/views/notice.py](../../apps/tenant_apps/girvi/views/notice.py).
- Batch notice creation is in [apps/tenant_apps/girvi/views/prints.py](../../apps/tenant_apps/girvi/views/prints.py).
- Auction transition notices are triggered in [apps/tenant_apps/girvi/transitions/commands.py](../../apps/tenant_apps/girvi/transitions/commands.py).
- Legacy scheduled reminder task is in [apps/tenant_apps/girvi/tasks.py](../../apps/tenant_apps/girvi/tasks.py).
- Girvi uses the adapter boundary in [apps/tenant_apps/girvi/integrations/notification_adapter.py](../../apps/tenant_apps/girvi/integrations/notification_adapter.py) to bridge to `notify` and `notify_v2`.

## Current Risks

### Tenant safety

- The tenant model is schema-per-tenant through `django-tenants`, so most data is isolated by schema rather than by explicit workspace foreign keys.
- `notify` and `notify_v2` do not yet carry explicit `workspace_id` columns.
- This is acceptable for the current schema-per-tenant architecture, but it will need explicit workspace ownership later if RLS is introduced.

### Webhook handling

- The WhatsApp Cloud webhook endpoint is public in the sense that it is `csrf_exempt` and only challenge-verifies on GET.
- The middleware currently treats `/notify-v2/` as a workspace-required route, which can interfere with provider callbacks.
- There is no signature verification for incoming webhook payloads.
- There is no raw inbound webhook event table for dedupe and replay protection.

### Consent and compliance

- `consent_flags` exists, but there is no strongly typed consent model.
- There is no explicit opt-out table, no STOP/UNSUBSCRIBE processing, and no category-level send enforcement.
- Marketing, service, and utility messages are not strongly separated in the data model.

### Operations and scale

- Sending currently happens inside request-driven view paths.
- There is no Celery-backed outbound queue for notify_v2.
- There is no conversation/inbox model for replies.
- Provider identity and encrypted credentials are tenant-scoped and configured
  by Workspace Owner/Admin.

## Decision

Adopt the **hybrid** communication model.

### Why this is the best fit

- Brand trust stays high for tenant customer communication because the customer sees the business they know.
- Platform/system messages remain centrally managed and consistent under the Rokkad brand.
- Compliance is easier because marketing and utility traffic can be separated by integration and policy.
- Reply routing is simpler because tenant business conversations stay on tenant-owned numbers.
- Reputation risk is contained because a bad campaign from one workspace does not destroy the platform number.
- Billing and usage tracking are cleaner because platform and tenant traffic can be metered separately.

### Why not a single shared number

- It creates customer confusion across businesses.
- It increases blast radius for spam reports, quality degradation, and provider rate limits.
- It makes brand identity less credible for jewellery and loan workflows.

### Why not pure per-workspace numbers only

- Rokkad still needs a platform identity for invites, auth, onboarding, and subscription reminders.
- A pure per-workspace model makes platform/system flows awkward and fragmented.

## Target Architecture

### Core concepts

Introduce a dedicated communications module with these boundaries:

- `WhatsAppIntegration` per workspace.
- `WhatsAppPhoneNumber` per integration.
- `WhatsAppTemplate` synced per workspace and phone number.
- `WhatsAppConsent` per customer and message category.
- `WhatsAppOptOut` per customer and category.
- `WhatsAppMessage` outbox table.
- `WhatsAppWebhookEvent` raw inbound event table with idempotency.
- `WhatsAppConversation` inbox/thread model.
- `WhatsAppCampaign` for broadcast or marketing runs.
- Provider abstraction so Cloud API and any future provider remain isolated.

### Recommended model shape

```text
WhatsAppIntegration
  - workspace
  - provider
  - purpose: platform | tenant_customer
  - display_name
  - status
  - created_by

WhatsAppPhoneNumber
  - integration
  - provider_phone_number_id
  - display_phone_number
  - verified_name
  - is_default
  - is_active

WhatsAppTemplate
  - integration
  - provider_template_id
  - name
  - language
  - category: utility | service | authentication | marketing
  - body_schema
  - status
  - version

WhatsAppConsent
  - workspace
  - customer/party
  - category
  - status: opted_in | opted_out | pending
  - source
  - captured_by
  - captured_at
  - context_json

WhatsAppOptOut
  - workspace
  - customer/party
  - category
  - reason
  - source
  - captured_at

WhatsAppMessage
  - workspace
  - integration
  - phone_number
  - recipient
  - category
  - direction: outbound | inbound
  - status
  - idempotency_key
  - provider_message_id
  - template
  - payload_json
  - failure_reason
  - sent_at / delivered_at / read_at / failed_at

WhatsAppWebhookEvent
  - workspace
  - integration
  - provider
  - provider_event_id
  - event_type
  - payload_json
  - signature_valid
  - processed_at
  - processing_status

WhatsAppConversation
  - workspace
  - integration
  - customer/party
  - last_message_at
  - state

WhatsAppCampaign
  - workspace
  - integration
  - name
  - category
  - audience_snapshot
  - approval_status
  - scheduled_for
  - sent_at
```

### Service layer

Keep provider-specific code in a narrow adapter service:

- `WhatsAppProvider` interface
- `MetaCloudProvider`
- Add an SMS provider only after a separate explicit provider decision.
- `WhatsAppMessageService`
- `WhatsAppConsentService`
- `WhatsAppWebhookService`
- `WhatsAppCampaignService`
- `WhatsAppTemplateSyncService`

### Celery/background jobs

- `enqueue_whatsapp_message`
- `send_whatsapp_message`
- `process_whatsapp_webhook_event`
- `sync_whatsapp_templates`
- `dispatch_whatsapp_campaign`
- `retry_failed_whatsapp_message`

### Idempotency and failure handling

- Use a stable idempotency key based on workspace + recipient + category + business object + template version.
- Store raw webhook payloads first, then process asynchronously.
- Retry transient failures with exponential backoff.
- Move hard failures to a dead-letter state for manual review.
- Never mutate posted/audited message history in place.

## Domain Use-Case Classification

### Platform messages

- Workspace invite
- Portal invite
- OTP/authentication
- onboarding reminders
- subscription/payment reminders
- platform/system alerts

### Tenant customer messages

- Sale invoice/receipt
- Purchase confirmation
- Inventory/order-ready alerts
- Loan due reminders
- Loan interest reminders
- Loan release notifications
- Overdue and auction notices
- Savings reminders
- Gold/silver rate broadcasts
- Festival/new design campaigns

### Sensitive / high-risk

- Auction notices
- Overdue debt notices
- Any content that may be read as collection enforcement or legal escalation

These should have stronger approval, template governance, and audit visibility.

## Compliance and Consent

- Store consent per workspace and per category.
- Separate utility/service consent from marketing consent.
- Capture opt-in source, actor, timestamp, and context metadata.
- Block marketing sends unless marketing consent exists.
- Block sends to opted-out customers.
- Treat inbound STOP/UNSUBSCRIBE as immediate category-level opt-out.
- Surface admin warnings for debt/auction-related content.

## Billing Design

- Maintain a workspace usage ledger.
- Track costs by category, channel, and provider.
- Support included credits and overage billing.
- Add monthly invoice line items from usage records.
- Warn owners before threshold breach.
- Throttle or block sends when plan quota is exceeded.

## Security Requirements

- Encrypt integration secrets at rest.
- Verify WhatsApp Cloud webhook signatures.
- Store raw webhook payloads in a restricted audit table.
- Restrict message body and phone-number access by role.
- Separate campaign creation, approval, and execution permissions.
- Audit all send and retry actions.

## Migration Plan

### Phase 0: Safe current-state hardening

- Exempt the WhatsApp webhook path from auth redirects or move it to a safe public callback route.
- Add provider signature verification.
- Add raw webhook event persistence.
- Add tests for duplicate webhook payload handling.

### Phase 1: Introduce the communications module

- Add provider interfaces and service wrappers.
- Route current `notify_v2` sending through the new service layer.

### Phase 2: Workspace integrations

- Add `WhatsAppIntegration` and `WhatsAppPhoneNumber`.
- Allow platform integration and tenant integration to coexist.

### Phase 3: Outbox and webhook event logging

- Add `WhatsAppMessage` outbox and webhook event tables.
- Move delivery into Celery tasks.

### Phase 4: Consent and opt-out enforcement

- Add structured consent and opt-out models.
- Enforce category-based send rules.

### Phase 5: Templates, campaigns, inbox

- Sync templates per integration.
- Add campaigns and conversation threads.

### Phase 6: Legacy cleanup

- Gradually retire direct legacy notify paths once parity tests pass.

## Files Likely To Change

- [apps/orgs/middleware_v2.py](../../apps/orgs/middleware_v2.py)
- [django_project/settings/base.py](../../django_project/settings/base.py)
- [apps/tenant_apps/notify/models.py](../../apps/tenant_apps/notify/models.py)
- [apps/tenant_apps/notify/services.py](../../apps/tenant_apps/notify/services.py)
- [apps/tenant_apps/notify_v2/models.py](../../apps/tenant_apps/notify_v2/models.py)
- [apps/tenant_apps/notify_v2/services/delivery_service.py](../../apps/tenant_apps/notify_v2/services/delivery_service.py)
- [apps/tenant_apps/notify_v2/views.py](../../apps/tenant_apps/notify_v2/views.py)
- [apps/tenant_apps/notify_v2/urls.py](../../apps/tenant_apps/notify_v2/urls.py)
- [apps/tenant_apps/girvi/integrations/notification_adapter.py](../../apps/tenant_apps/girvi/integrations/notification_adapter.py)
- [apps/tenant_apps/girvi/views/notice.py](../../apps/tenant_apps/girvi/views/notice.py)
- [apps/tenant_apps/girvi/views/prints.py](../../apps/tenant_apps/girvi/views/prints.py)
- [apps/tenant_apps/girvi/transitions/commands.py](../../apps/tenant_apps/girvi/transitions/commands.py)
- [apps/orgs/management/commands/seed_tenant_defaults.py](../../apps/orgs/management/commands/seed_tenant_defaults.py)

## Acceptance Criteria For The First Implementation Slice

- Webhook callback reaches the app reliably without login redirects.
- Webhook payloads are verified and stored idempotently.
- Outbound messages are queued, not sent inline from views.
- Consent and opt-out are enforced before any marketing send.
- Workspace-owned and platform-owned message paths are separate.
- Existing Girvi reminder workflows continue to work during migration.
