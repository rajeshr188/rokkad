---
status: accepted
owner: project
updated: 2026-09-26
tags: [email, configuration, operations]
related: [../plans/platform-email-rollout.md, ../plans/email-communication-review.md]
---

# Separate human inboxes from automated platform mail

## Decision

The owner selected Amazon SES for automated mail and approved the focused email
improvements on 2026-09-26. Human support/billing replies belong in domain-owned
inboxes, initially Google Workspace. The owner confirmed neither a Google
Workspace account nor an AWS account currently exists. Existing Google MX records
do not prove mailbox availability.

Use `notify.rokkad.com` for platform invitation/account/billing senders, with
monitored human Reply-To addresses under `rokkad.com`. Borrower traffic remains a
separately controlled rollout; changing the default backend must not activate it.
Preserve Google inbound MX while adding SES authentication on separate names.

Capture is the base-settings default, even when old SMTP credentials exist.
Environment-specific overrides remain supported. SMTP settings use explicit
integer/boolean types, bounded timeout, and mutually exclusive TLS/SSL. This is
an intentional change from the previous implicit SMTP default; installations
using SMTP must select that backend explicitly after acceptance.

An offline effective-settings check reports configuration problems and capture
mode. It must respect Django MAILERS precedence when present. It never claims
provider approval, DNS verification, external delivery or recipient interaction.
A deployment system-check warning makes configuration gaps visible; intentional
development/rehearsal capture remains valid and does not prevent startup.

## Boundaries and remaining decisions

The first increment adds configuration and diagnostics only. It does not wire
Reply-To into existing sends, create an SES account, implement a durable outbox,
change invitation acceptance, activate sending or reconcile provider receipts.
Those are required later increments in the approved rollout, not shipped claims.
Delivery persistence and transport/event handling need their own reviewed
implementation before production activation. No mail failure may undo payment.

Local tests exercise unsafe overrides, both Django configuration interfaces,
capture behavior and non-disclosure. Deployment acceptance additionally requires
provider/DNS evidence and an authorized end-to-end message. Existing sent flags
and in-memory captures must not be bulk replayed.
