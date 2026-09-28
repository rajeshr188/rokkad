---
status: accepted
owner: project
updated: 2026-09-26
tags: [email, control-plane, delivery, ses]
related: [2026-09-26-platform-email-separation.md, ../implementation/platform-mail.md]
---

# Durable platform invitations and paid receipts

## Decision

Use a small Django `platform_mail` app for control-plane delivery evidence. An
invitation or paid invoice commits exactly one Delivery intent in its existing
business transaction. A command claims committed rows, renders current source
data, commits an Attempt, then calls SES v2 outside the transaction. No provider
call or template rendering belongs in the payment transaction. A rollback removes
the intent along with the business change; a subsequent transport failure cannot
undo a recorded payment. Do not recover historic sent flags by bulk replay.

Delivery has exactly one source: the existing global CompanyInvitation or Invoice.
These are control-plane operational records, not Workspace-owned business rows.
Attempts/events inherit that source through Delivery; hashed recipient suppression
is deliberately platform-wide. No generic payload, borrower notification or
business-document delivery is supported. Default CRUD permissions are absent;
there is no general mail browser/API. Workspace UI queries derive source ownership,
and retry requires the explicit request Workspace plus invitation-role authority
or canonical billing ownership. Existing forced RLS on WorkspaceRole grants still
applies while workers evaluate the invitation. Workers use a restricted DB role.

Invitation bodies are rendered with a configured HTTPS origin, purpose-specific
From/Reply-To and escaped source values. Tokens/bodies and raw provider events are
not copied into the queue. Dispatch rechecks expiry, revocation, recipient, role
fingerprint and inviter authority. The legacy `sent` field starts link expiry;
it is not proof of sending or delivery. Acceptance still requires verified identity
and the existing membership/capacity checks.

## Reliability and evidence

Persist real SES message IDs and UUID attempt tags. Disable SDK send retries.
Definite throttling gets finite backoff; other definite rejection requires an
authorized retry. An ambiguous timeout or interrupted claimed send becomes
`unknown`, never automatically retried. Exactly-once external delivery is not
promised: the database and SES cannot share one transaction. Conservative unknown
handling avoids claiming certainty or blindly sending duplicates.

SES configuration-set events flow through private SNS -> SQS, with a dead-letter
queue. No public webhook or HTTP-supplied event is accepted. IAM/queue/topic
policies are part of the trust boundary: SES may publish only for this account and
configuration set; only that SNS topic may enqueue; runtime may receive/delete but
cannot publish/enqueue. Preserve the SNS envelope (raw delivery off). Reconcile
topic, account, identity, configuration set, recipient, delivery/attempt tags and
message ID. Commit deduplicated evidence before acknowledgement; out-of-order
events cannot downgrade delivery/bounce/complaint evidence. Permanent bounce or
complaint suppresses future platform sends to the normalized address.

`queued`, `captured`, `sending`, `accepted`, `delivered`, `failed`, `unknown`,
`cancelled`, `bounced`, `complaint` and `suppressed` are distinct. Delivery means
recipient-server acceptance, never read or invitation acceptance. No open/click
tracking is needed. Suppression hashes are pseudonymous, not anonymized data.

## Activation boundary

Dedicated SES settings remain disabled by default. Shared Django mail and Notify
transports stay independently captured; account-security emails are not migrated
by this increment. Production requires reviewed AWS policies, scoped credentials,
an applied owner migration, restricted worker/consumer, verified DNS and authorized
delivery/bounce/complaint/reply tests. SES sandbox exit is a separate provider gate.
See the [runbook](../implementation/platform-mail.md).
