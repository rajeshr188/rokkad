---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, configuration, receipts, operations]
---

# Declare provider mode explicitly and preserve payment-mode evidence

`BILLING_PROVIDER_MODE` is `disabled` by default. An operator must explicitly
select `test` or `live` with matching Razorpay key prefix and a nonempty secret.
SDK construction and browser signature verification fail closed on disabled,
invalid or mismatched configuration. Webhooks reject before persisting events when
the configuration is invalid. Creation/authorization switches remain separate:
pausing new recurring payments does not disable configured Test Mode recovery.
Live recurring services are still unsupported; setting live credentials does not
override that restriction or constitute activation approval.

New one-off checkout snapshots freeze provider mode. Same-key reuse and payment/
refund processing require that mode to match the process configuration. Recurring
invoices derive mode from their immutable agreement binding, including older rows.
Historical one-off snapshots are not rewritten. Unclassified legacy records can
still be reconciled with Test Mode provider evidence, but cannot be interpreted as
live purchases. A future legacy/live migration needs explicit evidence review.
Never promote the rehearsal database or switch a populated billing database to a
different provider mode as a deployment shortcut.

`check_billing_configuration` is an offline, sanitized settings report. Optional
`--include-evidence` adds read-only database counts and flags conflicting modes,
unclassified invoices, unresolved creation/webhook records and receipt statuses.
`--require-configured` checks configuration/evidence, never launch acceptance.
The report separately includes the dedicated SES configuration check. No keys,
addresses, message bodies or provider response bodies are printed. A deployment
warning highlights enabled checkout/recurring flags with invalid configuration.
No DB schema change or evidence backfill is introduced.

Test receipt previews carry `[TEST]` and explicitly state that no real money was
charged. Normal SES dispatch requires an explicitly live process and a recorded
live invoice; test/unclassified receipts stay unchanged with no attempt/provider
send. Local capture remains available. Invitations are unaffected. A separately
reviewed, recipient-specific Test Mode receipt delivery rehearsal remains necessary;
enabling general sending is not permission to send the fictional queue.

Tests use fixed dummy Test Mode credentials instead of inheriting a developer's
environment. Tests of the live receipt path use explicit dummy live mode with
mocked payment/mail transports. Configuration validity, SES approval, provider
acceptance, actual receipt delivery and launch authorization remain distinct facts.
