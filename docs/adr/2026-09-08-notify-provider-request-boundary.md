---
status: accepted
owner: project
updated: 2026-09-08
tags: [notify, security, workspace, callbacks]
related: [2026-08-17-workspace-request-authority-and-rls-context.md, ../architecture/control-plane-contracts.md]
---

# Notify provider request boundary

## Context

The WhatsApp webhook verified secrets and signatures in its view, but Workspace
middleware redirected anonymous providers to login first. Operator settings also
displayed an unscoped callback URL on the shared host.

## Decision

Only the exactly resolved `workspace_notify:notify_v2_whatsapp_cloud_webhook`
and legacy `notify_v2_whatsapp_cloud_webhook` endpoints use provider authentication
instead of browser-session Membership. Canonical callbacks carry an immutable
Workspace slug; the legacy endpoint requires a registered Workspace domain.
Missing identity, conflicting domain/path, and non-active lifecycle fail closed.

The middleware establishes numeric Workspace RLS context for those endpoints.
The existing view verifies the Workspace verification token for GET and the
Workspace HMAC signature plus configured phone-number identity for POST before
processing delivery evidence. No surrounding route or URL prefix is exempted.
The endpoint remains CSRF-exempt because it authenticates the provider payload.

Provider receipts do not require a commercially available browser subscription:
they reconcile already-requested delivery evidence. A logged-in browser does not
change callback authentication or bypass signatures. Other business routes keep
ordinary Membership, lifecycle, billing, permission, and CSRF checks.

## Other audited boundaries

Notify admin links require authorized staff and a registered Workspace domain;
they use that domain rather than dropping identity on the shared host. They
retain Django Admin's existing permissions. A new shared-host admin application
is not introduced in this decision.

Raw Notify artifact URLs are denied by Django's public development media view;
operators download through the guarded Workspace/batch endpoint. Production
web servers or object stores that serve media directly must enforce the same
privacy independently. This repository change cannot certify external storage
ACLs or remove copies already obtained.
