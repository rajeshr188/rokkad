---
status: accepted
owner: project
updated: 2026-08-14
tags: [notifications, notify-v2, whatsapp, sms, providers]
related:
  - ../implementation/whatsapp-notifications-architecture-audit.md
  - ../flows/pawn-risk-alert-borrower-communication.md
---

# WhatsApp Cloud API Is the Sole WhatsApp Provider

## Context

Notify v2 supported both Twilio and Meta WhatsApp Cloud API for WhatsApp, while
SMS also depended on Twilio. This created a provider switch, duplicate settings,
and a debug stub that could resemble successful borrower delivery. The project
has chosen Meta's Cloud API for WhatsApp and does not currently require Twilio.

## Decision

1. Meta WhatsApp Cloud API is the only WhatsApp delivery adapter.
2. Remove Twilio imports, credentials, provider selection, fallback behavior,
   legacy helper code, and active documentation.
3. SMS remains a domain channel but has no delivery provider. Any SMS job fails
   closed with an explicit diagnostic until a separate provider ADR is accepted.
4. Missing WhatsApp Cloud credentials or provider errors fail the existing job;
   no stub may mark it Sent.
5. Existing Notify ownership remains unchanged: source applications own intent,
   while Notify owns rendering, attempts, artifacts, and provider evidence.

## Consequences

- Deployment needs only WhatsApp Cloud API settings for WhatsApp delivery.
- Historical Twilio references may remain in archived documents only.
- SMS templates and historical records remain readable, but new SMS delivery is
  not operational.
- WhatsApp callbacks now require Meta HMAC verification, the configured phone
  identity, a tenant route, replay-safe persisted receipts, and a uniquely
  matched WhatsApp job. Production acceptance still requires real credentials,
  approved provider templates, and an operator reconciliation exercise.
