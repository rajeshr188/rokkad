---
status: active
owner: project
updated: 2026-09-29
tags: [email, ses, rollout, invitations, billing]
related: [email-communication-review.md, future-work.md, ../adr/2026-09-26-platform-email-separation.md]
---

# Platform email rollout

The owner approved SES and all focused improvements: reliable invitations,
billing receipts, honest delivery status, correct configuration and domain
authentication. Human inboxes are separate from automated mail. The owner has
now created Google Workspace and AWS accounts, confirmed on 2026-09-26.

## Current checkpoint

- **29 September, 18:49 IST:** ongoing verification/reset mail is enabled alongside
  invitations. The combined worker handles up to ten messages per scheduled run,
  with receipts excluded. Both mail flags are true in web/worker, matched signing
  settings remain intact, and supervised plus subsequent scheduled runs passed
  with an empty queue and no health flags. No new acceptance email was sent.
  The earlier two-email delivery/link rehearsal is complete. Public trial and
  payment gates remain paused. See the
  [current activation](../implementation/platform-mail.md#ongoing-account-and-invitation-mail-enabled-2026-09-29).

- **29 September, 17:14 IST:** ongoing invitation-only dispatch is now enabled,
  one per run approximately a minute apart, with healthy feedback/recovery/monitoring.
  Restricted checks confirm an empty queue, subsequent scheduled success and
  unchanged billing/mail records. Billing and public trials remain paused; receipts
  are excluded from scheduled dispatch. Thirty-five focused tests passed, including
  a fresh-owner database invitation journey with mocked provider sending. See
  [activation](../implementation/platform-mail.md#ongoing-invitation-dispatch-enabled-2026-09-29).
  Earlier paused checkpoints below are historical.

- **Latest monitored check, 28 September:** the owner-selected admin inbox received
  one Viewer invitation to the empty **Rokkad Invitation Activation TEST** Workspace.
  Inbox, SPF/DKIM/DMARC, TLS and Send/Delivery correlation passed with one attempt.
  The link refused the current owner's different email; fresh acceptance remains
  pending with no new membership. Feedback/recovery/health timers are active;
  general dispatch stays disabled. The exact send used a transient process-only
  enable override and delivery ID, not general timer activation. Queues and health
  are clear. The bounded check is complete; ongoing dispatch is a separate scope
  expansion. See the [monitored checkpoint](../implementation/platform-mail.md#monitored-single-invitation-delivery-2026-09-28).
- **Latest activation preparation, 28 September:** installed a command-only worker
  overlay, still paused, with `--limit 1 --invitations-only`. It excludes receipts
  before selecting the batch; 39 focused tests pass and CI includes the regression
  suite. Runtime/schema readiness, empty due queue, SQS/DLQ and alerts passed.
  IAM default version 3 removes only the expired sandbox recipient exception.
  Sending and dispatch/feedback/recovery timers remain disabled; health is enabled.
  Next: fresh queue review and monitored invitation activation with an explicitly
  authorized recipient and feedback/recovery supervision. The production web/older
  worker lack local billing-mode guards, so general receipts need a separate reviewed
  deployment. See the [current runbook](../implementation/platform-mail.md#paused-invitation-worker-and-iam-cleanup-2026-09-28).
- **Latest receipt acceptance, 28 September:** one actual paid Test Mode receipt
  reached the chosen admin Inbox, with correct content, SPF/DKIM/DMARC PASS and TLS.
  The separately approved reply to billing@rokkad.com was confirmed by Google Admin
  Email Log Search as delivered to its Gmail mailbox at 13:40:50 IST. The shared
  mailbox Sent copy was not used as delivery proof. Temporary worker credentials
  and tunnel are removed; general dispatch remains disabled. Next: review current
  worker/source versions, IAM cleanup, queue/DLQ and alerts for bounded activation.
  Google Admin shows prepayment pending and 12 trial days left; owner account billing
  completion is needed for human-inbox continuity. See
  [received receipt acceptance](../implementation/billing-provider-readiness.md#received-receipt-and-billing-reply-acceptance-2026-09-28).
- **28 September update:** AWS support case **179042575700203** confirms production
  access approved at **11:20:42 IST** in Mumbai (`ap-south-1`): **50,000/day**,
  **14/second**, immediate sandbox exit. Independently read after owner sign-in;
  evidence `outputs/ses-production-approved-20260928.png`. This supersedes the
  earlier pending/sandbox checkpoint below. General dispatch remains disabled;
  worker/IAM/feedback readiness and actual paid-receipt delivery still need acceptance.
  The temporary recipient exception expired at 00:00 UTC today; review its cleanup
  separately, without broadening IAM. No AWS settings were changed in this check.
- Local billing changes now require explicit provider mode and refuse ordinary
  sending of test/unclassified receipts, while clearly labelling local test previews.
  A targeted, recipient-authorized receipt rehearsal must be prepared separately;
  do not enable sending against the fictional queue. See
  [billing readiness](../implementation/billing-provider-readiness.md).

- Deployed with sending disabled: typed shared-mail settings plus a separate durable
  invitation/paid-receipt queue, SES API transport, authorized retry/status UI and
  private SNS/SQS feedback consumer. See the [decision](../adr/2026-09-26-durable-platform-mail.md)
  and [runbook](../implementation/platform-mail.md). `platform_mail.0001` is applied
  to production, with no historical replay. Shared Django/Notify mail stays independently captured.
- Scoped runtime credentials are root-private on the Linode and verified by STS.
  Web has no AWS mail key. Worker units validate; dispatch/feedback/recovery timers
  remain disabled. Separate five-minute health monitoring is enabled.
  Account-security tokens are not migrated in this increment.
- Combined local validation: 217 tests passed; no migration drift.
- Account signup completed by the owner. Browser review confirmed the active
  `admin@rokkad.com` Business Starter user and AWS SES in Mumbai (`ap-south-1`).
  Its current SES plan is Essentials; pricing was not changed. MFA has not been
  audited. SES account health is Healthy, still sandboxed in Mumbai: 200 messages
  per 24 hours, one per second. Production access is requested under case
  179042575700203; the console showed Under review and a factual use-case follow-up
  was submitted. No provider approval yet.
- Following explicit action-time approval, saved `support@rokkad.com` and
  `billing@rokkad.com` as aliases to `admin@rokkad.com`; Google Admin confirmed
  both. No extra user or paid mailbox was created.
- Created SES `notify.rokkad.com` identity with Easy DKIM RSA 2048 and
  `bounce.notify.rokkad.com`, reject on MAIL FROM MX failure, Route53 publishing
  disabled (DNS is in Linode). SES now reports identity **Verified** and DKIM
  **Successful**. Custom MAIL FROM now reports **Successful** after recheck.
- Published the three generated DKIM CNAMEs and bounce MX/SPF in Linode. Verified
  all three exact CNAME targets against `ns1.linode.com`. Bounce MX is priority 10
  `feedback-smtp.ap-south-1.amazonses.com`; TXT is
  `v=spf1 include:amazonses.com ~all`. Root Google MX/SPF and web records unchanged.
- Google Admin confirms **Authenticating email with DKIM** for `rokkad.com`;
  retained the existing `google._domainkey` record. Added root `_dmarc` TXT
  `v=DMARC1; p=none; rua=mailto:admin@rokkad.com` for monitoring, confirmed saved
  in Linode and resolving from the authoritative nameserver.
  This is monitoring, not enforcement or proof of real-message alignment.
- Production candidate `mail-20260926-2f39723e810c` is deployed; backup/migration,
  restricted runtime, empty initial queue, startup and HTTP health checks passed.
  Controlled invitation and clearly labelled no-payment billing-sender messages
  arrived at the verified admin inbox; SPF/DKIM/DMARC and expected Reply-To passed.
  Send/Delivery events correlated; simulator bounce/complaint suppression and
  refused retries passed. No real invoice/payment was created. The sandbox test
  recipient needed a separately approved, time-limited IAM statement expiring
  2026-09-28 00:00 UTC. General dispatch remains disabled.
- Invitation link correctly uses HTTPS rokkad.com and refuses a mismatched email.
  Acceptance through Google as admin@rokkad.com passed; read-only verification
  confirms only the isolated Viewer membership. The original owner session is
  restored. Both reply composers selected their intended aliases; self-mailbox
  replies were sent. With specific personal-Gmail approval, one external message
  addressed to both aliases arrived in the admin inbox and passed authentication.
  Delivered-To identifies support; this combined test does not independently
  isolate billing's envelope path. No unrelated personal messages were opened.
  Private operator opt-out/pause/sticky-alert acceptance now passes. Source and DLQ
  console counts are zero available/in-flight. Sixty-one focused tests include
  checkout-to-receipt-to-delivery with mocked providers. Local alerts require an
  operator to review; no external pager or automatic DLQ monitoring is configured.
  SES approval and bounded activation remain gates.
  Do not describe the billing transport probe as a real receipt.

## 1. Human inbox and AWS account ownership — accounts and aliases created

Create Google Workspace using the existing `rokkad.com` domain; do not register a
new domain. Start with one named human mailbox (suggested `rajesh@rokkad.com`).
Add `support@rokkad.com` and `billing@rokkad.com` as aliases if the same person
handles both; aliases share the mailbox and have no independent login. Choose
separate users or a reviewed shared-inbox arrangement when staffing needs it.
Do not buy three mailboxes just to obtain three addresses. Enable MFA.

If Google says the domain is already in use, use its existing-account recovery
process before changing DNS; current MX is not proof of account ownership.
Verify Google's requested domain token in Linode and check Gmail activation/MX
against the setup wizard. Inventory current records before editing.

Create a business-owned AWS account, complete billing/contact verification, enable
root MFA, and establish administrative access. Never create root access keys or
paste credentials into chat/repository files. Choose the SES region deliberately;
Mumbai (`ap-south-1`) is the selected and now provisioned SES region.

## 2. SES identity and DNS — DKIM and MAIL FROM verified

Prepare a verified SES identity for `notify.rokkad.com`, Easy DKIM, and a dedicated
custom MAIL FROM subdomain such as `bounce.notify.rokkad.com`. Publish the exact
SES-generated DKIM records and MAIL FROM MX/SPF in Linode. These MX records apply
to the bounce subdomain; they do not replace Google's root-domain MX.

Check Google DKIM for human mail separately. Publish DMARC in monitoring mode
after choosing a monitored reporting destination, verify all legitimate senders,
then plan stronger enforcement. Never guess DKIM values or create duplicate SPF
records at one hostname. DNS/provider verification must use the selected region.

Configure delivery/bounce/complaint event collection and suppression before real
traffic. Request SES production access with an honest description of the SaaS
pawn-lending platform and the initial account/invitation/billing-only use case.
Do not claim implemented bounce handling or existing traffic that does not exist.
Sandbox approval is region-specific; identity verification alone does not enable
arbitrary recipients. Provision narrowly scoped runtime credentials privately on
the server; keep them distinct from R2 credentials.

## 3. Durable platform delivery - deployed with sending disabled

New invitations and paid receipts commit durable intent with their source rows.
The bounded worker renders and sends after commit through SES v2; finite backoff,
authorized retry, explicit uncertain acceptance and current invitation validity
checks are implemented. Private event reconciliation validates source and attempt,
deduplicates evidence and suppresses permanent bounce/complaint recipients.
Purpose-specific From/Reply-To, canonical links and status/retry UI are wired.
Account-security emails still need a separate expiry-aware integration.

Combined local validation passed 217 tests, with no migration drift. See the
[decision](../adr/2026-09-26-durable-platform-mail.md) and
[runbook](../implementation/platform-mail.md). The disabled production deployment
and owner migration are complete, with server-local before/after backups.

SES configuration set `rokkad-platform` is created with required TLS and no
archive. Its `rokkad-platform-events` SNS destination publishes seven event types
(send, rendering failure, reject, delivery, bounce, complaint, delay). No opens/
clicks are selected. Following explicit approval, the private SNS topic, SQS queue
and dead-letter queue are created and connected. The confirmed subscription keeps
the SNS envelope (raw delivery disabled). Both queues use SSE-SQS; source has
four-day retention, two-minute visibility, ten-second poll and five-receive redrive;
DLQ retains fourteen days and admits only this source queue.

Verified exact account/configuration-set SES publish grant and exact account/topic
SNS enqueue grant; replaced the wizard's broader defaults. Real Send/Delivery,
simulator Bounce/Complaint and suppression checks now pass. The dedicated runtime
principal/key is installed; STS identity and SQS receive checks pass. Worker units
are installed; a one-shot feedback service passed. Timers/general dispatch remain
disabled. Only explicitly controlled tests were sent.

## 4. Verify and activate — pending preceding gates

Run the non-sending inspection with the actual deployed web AND worker settings:

Only the worker receives dedicated SES credentials, so run the dedicated
`check_platform_mail --require-ready` there; the web's missing-key result is
intentional. Both processes must report sending disabled until acceptance.

```text
python manage.py check_email_configuration --format json
python manage.py check_platform_mail --require-ready
python manage.py check --deploy --tag email
```

`configuration_valid_for_external_mail` concerns static transport/address values
only. `delivery_verified` remains false: the command does not inspect DNS, provider
approval, mailbox ownership, retries or actual delivery. No secrets or recipient
lists appear in its output. Production's deployment-local `production_settings`
override must be reviewed explicitly; an env variable alone cannot remove it.

Test rollback, retry idempotency, uncertain sends, expired/revoked invitations,
receipt failures, cross-Workspace permissions, callback replay and suppression.
Preview templates locally, then obtain a specific test recipient and send a
controlled authorized message. Verify receipt, SPF/DKIM/DMARC, links and replies.
Activate platform mail first with a bounded monitored queue and rollback procedure.
Borrower campaigns, marketing, Workspace custom sender domains and WhatsApp are
outside this activation. Keep deployment evidence and secrets on the server.

## Provider references

- [Google mailbox aliases](https://support.google.com/a/answer/33327)
- [SES endpoints and regions](https://docs.aws.amazon.com/general/latest/gr/ses.html)
- [SES custom MAIL FROM](https://docs.aws.amazon.com/ses/latest/dg/mail-from.html)
- [SES production access](https://docs.aws.amazon.com/ses/latest/dg/request-production-access.html)
- [SES event publishing](https://docs.aws.amazon.com/ses/latest/dg/monitor-using-event-publishing.html)

Provider references checked 2026-09-26. Mailbox provisioning, authentication and
controlled delivery and the combined external alias test are verified (see its
scope above). SES production approval and operational activation remain outstanding.
