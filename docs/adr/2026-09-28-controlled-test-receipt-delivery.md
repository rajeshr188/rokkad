---
status: accepted
owner: project
updated: 2026-09-28
tags: [billing, email, rehearsal, authorization]
---

# Controlled Test Mode receipt delivery

Ordinary queue dispatch continues to refuse test/unclassified invoices. A private
`rehearse_billing_receipt` command handles exactly one explicit delivery, actor,
recipient and operator reference. Default behavior renders a read-only preview;
`--preview-html` exclusively creates a local review file. Only `--send` enters the
existing durable claim/SES/feedback path, and existing mail enablement and actual
SES configuration checks still apply. There is no new web endpoint or bulk mode.

Require the explicit billing-rehearsal flag, matching Test Mode keys, a dedicated
`rokkad_baseline_rehearsal_billing_*` database through loopback, and a database role
without superuser/BYPASSRLS. Recheck the actual connected database and role. Derive
the Workspace from the invoice; require the current active billing owner/platform
authority in explicit Workspace context. Invoice mode must be recorded test and
the named inbox must match both immutable invoice contact and Delivery. Reject
fictional/reserved addresses, invalid references, nonpaid sources and suppression.
Existing fictional invoice contacts are never rewritten for this rehearsal.

The claim transaction writes the ordinary Attempt plus an attributable audit
containing IDs, recipient hash and reference. Audit failure rolls back before
network I/O. Authorization/Workspace checks finish inside that claim transaction;
no Workspace transaction spans SES. Existing attempt tags, provider IDs and SNS/
SQS reconciliation remain authoritative. Replaying a completed/uncertain claim
never resends. An attempted row accidentally requeued is refused, and even definite
throttling stays failed for this single-send rehearsal instead of automatic retry.

No schema change, credential distribution, general mail activation or live billing
is implied. Server-side worker preparation requires its own operational approval.
Local automated tests mock all external payment/mail calls. Controlled recipient
acceptance remains distinct from provider acceptance and inbox/header inspection.
See the [readiness runbook](../implementation/billing-provider-readiness.md).
