---
status: pending-external-setup
owner: project
updated: 2026-10-14
tags: [plan, whatsapp, pilot, sender]
---

# JCL platform WhatsApp sender and template setup

The owner selected JCL for the first setup-guidance pilot and will monitor
support@rokkad.com. Sender/template setup is still needed. A restricted READ ONLY
production metadata check confirms deployed JCL (Workspace 1, owner 1) matches the
privately supplied owner account and is active. The local JCL copy differs; do not
substitute local IDs or change ownership to match the pilot. The personal email is
not repeated here. Production has neither the platform_whatsapp app nor its tables.
No deployment, migration, provider registration or send was done.

## Sender setup handoff

Use a platform-owned Meta WhatsApp Business Platform Cloud API sender for Rokkad
owner messages. The [official developer entry point](https://whatsappbusiness.com/developers/)
and [Meta Cloud API collection](https://www.postman.com/meta/whatsapp-business-platform/documentation/wlk6lh4/whatsapp-cloud-api)
are references. Meta's portal determines applicable account, business, number,
verification and billing requirements; this checklist does not establish approval.

1. Establish the Rokkad business portfolio, developer app, WhatsApp Business Account
   and sender number. Confirm platform SaaS support use is accepted for this account.
   Record account/phone IDs privately.
2. Give the sender profile the correct Rokkad identity, website/privacy information
   and support@rokkad.com. Confirm mailbox monitoring and escalation. Ordinary
   WhatsApp chat is not mirrored into that mailbox by this implementation; users
   follow the explicit email/support route. The callback handles pairing/opt-out
   and status evidence, not a shared support inbox.
3. Configure the exact HTTPS callback
   `https://<canonical-origin>/app/integrations/whatsapp/webhook/`, private verify
   token/app secret and sender message/status subscription. Record a supported API
   version and appropriately scoped runtime access token. Keep secrets in private
   deployment configuration, never chat, screenshots or git.
4. Submit the candidate English setup template below. Save its actual approved name,
   locale, category and final body. Reject a mapping whose approved parameter order
   differs from the adapter; a dynamic URL button needs separate implementation.
5. Obtain the dated applicable INR/India category tariff and agree a positive daily
   monetary cap. Retain its source/effective dates privately. This pilot currently
   prices Indian mobile recipients only.
6. Adopt a real retention/erasure policy reference with an owner, retention periods,
   privacy notice and lawful deletion process covering immutable consent/source/
   attempt/receipt evidence, hashes and backups. The configuration reference is a
   gate, not a deletion implementation or proof that a policy was adopted.

The [current Meta messaging policy](https://whatsappbusiness.com/policy/) requires
recipient permission, opt-out handling, approved initiated templates and a human
support path. Sender/template eligibility remains subject to provider review.
Borrower lending, collections and customer messages stay in a separately gated phase.

## Candidate template for review

Proposed name: `rokkad_setup_help`. Proposed locale: `en`; use the exact approved
locale. Request utility classification for owner-requested assistance only if Meta
accepts it; do not relabel an approved marketing category.

> Hello! You requested setup guidance for {{1}} in Rokkad. Open your Workspace setup: {{2}}. For help, email support@rokkad.com. Reply STOP to stop Rokkad WhatsApp messages.

Body text parameters, in order: Workspace display name; authenticated canonical
HTTPS setup URL. Fictional samples: `Example Workspace` and
`https://example.invalid/app/example-workspace/settings/setup/`. The real URL is
generated through Django reverse and preserves normal login/ownership checks.
Use no dynamic buttons, media or additional parameters with the current adapter.
Other purpose mappings may remain absent for the setup-only pilot.

After actual approval, the private mapping is structurally:

```json
{"setup":{"name":"rokkad_setup_help","language":"en","revision":"rokkad-owner-source-preview-1","approved":true}}
```

This is an illustrative shape, not evidence of approval or a ready-to-use setting.

## Release and single-recipient pilot

Prepare a reviewed compatible deployment, backup/restore and owner-only migrations
before activating flags. Web/worker use the restricted role. Keep inbound, intent
creation and dispatch activation separate. Configuration cannot prove acceptance.

Private pilot configuration binds deployed JCL's verified owner/Workspace only,
`purposes: ["setup"]`, a short timezone-aware interval, version, count caps and the
agreed monetary cap. Start with one request/platform/day and one request/phone/day.
Tariff requires revision, effective_from/effective_until, official source_url,
currency INR, market IN and rates for utility, marketing, authentication,
authentication_international and service. Capacity reserves the largest configured
category; do not invent missing rates. Creation/sending remain off until valid.

The owner signs in, pairs their own number through the authenticated code flow and
explicitly chooses setup assistance. Email does not supply a WhatsApp recipient or
permission. Run `check_platform_whatsapp_pilot` with the authorized platform actor,
deployed slug and privately supplied owner email under runtime settings. It reports
masked readiness. Resolve schema blockers through release, never a preflight migration.

Once ready, the owner reviews/confirms a fresh request during 09:00–18:00
Asia/Kolkata. Dispatch only that recorded Workspace/delivery ID. A previous capture
remains unsendable; never rewrite it or re-enroll to manufacture a replacement.
An existing enrollment capture needs a separately reviewed source decision.

Record the real accepted ID, authenticated delivery/read callbacks when supplied,
owner receipt confirmation, working setup/login link, support handoff and STOP
suppression. Reading is optional evidence, never inferred. Unknown acceptance blocks
resend. Stop dispatch independently of source/email and preserve evidence before
expansion. Full PW-05 live acceptance remains pending until these checks occur.
