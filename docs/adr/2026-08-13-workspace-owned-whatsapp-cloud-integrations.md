---
status: accepted
owner: notify-v2
updated: 2026-08-13
tags: [notify-v2, whatsapp, tenancy, credentials, security]
related: [2026-08-14-whatsapp-cloud-api-only.md, ../implementation/whatsapp-notifications-architecture-audit.md]
---

# Workspace-owned WhatsApp Cloud integrations

## Context

Rokkad workspaces are independent businesses. A deployment-global Meta phone,
token, verify token, and app secret would cause unrelated tenants to share a
sender identity and would make callback ownership ambiguous.

## Decision

Each workspace owns at most one `WhatsAppCloudIntegration` in its tenant schema.
It records the Meta API version and phone-number ID and stores the access token,
verify token, and app secret encrypted with the deployment-level
`WORKSPACE_SECRET_ENCRYPTION_KEY`. Only Workspace Owner/Admin may edit it;
secrets are write-only and blank edits preserve the stored value.

Dispatch resolves the enabled integration for the active tenant. Meta uses the
workspace's HTTPS tenant hostname for its callback. Tenant middleware selects
the schema before GET verification or POST HMAC validation; the callback phone
ID must exactly equal that tenant's configured phone ID. There is no fallback
to deployment-global WhatsApp credentials.

## Consequences

Provider identity, sending, readiness, callbacks, receipts, and reconciliation
remain aligned to one workspace. Operations must provision one stable Fernet
master key per deployment and back it up; losing or changing it makes stored
credentials unreadable. Rotation of that master key requires a deliberate
decrypt/re-encrypt procedure. Workspace owners still rotate their Meta secrets
through the write-only setup form.
