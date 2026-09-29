---
status: active
owner: project
updated: 2026-09-29
tags: [email, ses, operations, delivery]
related: [../adr/2026-09-26-durable-platform-mail.md, ../plans/platform-email-rollout.md]
---

# Platform mail operations

## Current image after public-trial release (2026-09-29)

Web and all mail consumers now use `rokkad:public-trial-20260929-e06bb85c285c`. Both mail flags
and combined batches of ten remain enabled; receipts remain excluded. The selected
free trial is enabled, while checkout/recurring remain false. The later scheduled
run and health passed with an empty due queue. Source and shared deployment
settings changes are documented in the [trial release](public-trial-release-20260929.md).
The earlier image/paused-trial checkpoints below are historical.

## Ongoing account and invitation mail enabled (2026-09-29)

At **18:49 IST**, `ACCOUNT_EMAIL_ENABLED=True` was enabled consistently in
production Compose, the public worker environment and the root-only worker
environment. `PLATFORM_EMAIL_ENABLED=True` remains set. Web and all mail consumers
still use `rokkad:account-mail-20260929-702d1c64ba50`; there is no new image,
migration, static release or credential change. Web has no SES credentials.
Verification/reset hooks now enqueue into the monitored outbox even though the
shared default mail backend remains locmem.

Dispatch now uses `--send --limit 10 --invitations-and-accounts`. Scope filtering
happens before the limit and excludes receipts. The timer remains approximately
60 seconds after a completed run; messages are serial with their existing delay,
so delivery is queued rather than instant. `TimeoutStartSec=300` accommodates the
bounded ten-message batch and existing SES request timeouts. Feedback, recovery
and health remain enabled.

Before activation, root-only backups/candidates were checked for matched flags,
signing/token configuration, unchanged runtime identity and an empty queue. The
four timers were paused only for the configuration switch and restored before
supervised health. Supervised workers and the next natural scheduled dispatch
passed; all four timers are active/enabled, queue due is zero and health has no
flags. Existing mail/billing/Workspace records and access fingerprints are
unchanged; activation created no new message or attempt. The two delivered account
rehearsal records remain; user 11 is disabled. Permanent admin user 9 is unchanged.

Trial, checkout and recurring gates remain false. Public-trial code is not in the
current image. Private backup/candidate/evidence files live in
`account-mail-activation-20260929/` under the existing deployment directory, with
sanitized local `outputs/account-mail-activation-{prepare,apply,verify}-20260929.json`.
These settings supersede the paused/invitation-only checkpoints below. Preserve
both enabled mail flags and this worker scope in subsequent releases.

## Account mail deployed with sending paused (2026-09-29)

Subsequent owner-approved acceptance sent exactly two messages to
`admin+account-test-20260929@rokkad.com`: verification and password reset, each
delivered with one attempt. A separate non-admin account (user 11, no memberships)
was used. Only the bounded worker process enabled the account flag; persistent
settings and scheduling stayed paused/invitation-only. Verification succeeded
through the received live-site link. The user submitted the reset password; the
account acquired a usable password and the original received link then returned
Bad Token before cleanup. User 11 is disabled with an unusable password and no
memberships or platform privileges. This bounded rehearsal is complete; ongoing
account-mail activation is still pending. No additional test message is authorized.
These two retained account
intents supersede the zero-account-row evidence at deployment below.

Web, dispatch, feedback, recovery and the watchdog's inspection command now use
`rokkad:account-mail-20260929-702d1c64ba50` (image
`sha256:a5c71b750eb6eca2e5ffb44e0dda9aa5d44624b51c3a41a773af8e3e48a0d4ea`).
Deployment completed at 18:22 IST. The overlay copies only the nine account-mail
files plus a targeted base-settings adapter/flag edit; previous production UI and
the existing static volume are preserved. It does not deploy public-trial source.

An operational backup was verified, `platform_mail.0002` applied under the owner
role, and `rokkad_prod_runtime` table/sequence grants and source constraint checked.
All runtime processes remain restricted. Web/worker signing secrets and token
settings match; comparisons stayed private. The web has no SES credentials.
Configuration files, existing container environment, billing/mail records,
Workspace access and 117 forced-RLS tables remain unchanged. No account row or
real message was created by deployment.

The initial switch rolled back after the watchdog reported the deliberately paused
timers. The retry reused the additive migration and restored scheduling before
supervised health. All timers are active/enabled; workers, HTTPS login and health
checks passed. For future enabled-mail deployments, restore the dispatch/feedback/
recovery timers before running the watchdog: inactive timers are correctly treated
as failures when the dispatch marker is present.

`ACCOUNT_EMAIL_ENABLED=False` in both web and worker; invitation sending remains
enabled with `--send --limit 1 --invitations-only`. Trial/checkout/recurring remain
paused. The real verification/reset rehearsal is complete; reviewed account
scheduling and activation remain. Until activation, new
account requests still use locmem. Historical preparation instructions below must
be read with this deployed checkpoint; schema/build work is already complete.

Private evidence and previous/candidate configs are in the deployment directory's
`account-mail-20260929/`. Preserve the additive schema during any image rollback;
account source rows were empty at deployment, but now include the two rehearsal
records. Do not reverse the schema or restore workers unaware of account sources
without reviewing this retained evidence and the queue. Previous web image was
`rokkad:party-loan-pages-20260929-5143b3441f2b`; previous worker image was
`rokkad:receipt-worker-20260929-e4bee6e23a41`.

## Account mail prepared, not deployed (2026-09-29)

The new allauth adapter queues verification/reset intents when
`ACCOUNT_EMAIL_ENABLED=True`. Its default is false, preserving the existing
backend until rollout. No SES credentials are needed by the web process.
Production still uses locmem for account mail; enabled invitation sending does
not establish account delivery. See the [decision](../adr/2026-09-29-durable-account-email.md).

The outbox stores source references and a keyed state fingerprint, never links,
passwords or email bodies. Queue intent lifetime is at most 30 minutes. Native
link expiry starts at rendering and uses the existing allauth/Django settings.
Inactive/changed accounts, verified/deleted addresses, stale reset requests and
suppression are rechecked before sending. Uncertain sends are not automatically
replayed; fresh requests must use the ordinary rate-limited account flow.

Rollout sequence:

1. Back up schema/configuration and pause dispatch during the coordinated release.
   Apply migration `platform_mail.0002` with the owner-only migration settings;
   verify DML/sequence grants for the restricted runtime role.
2. Deploy the same reviewed account-mail code to web and every mail worker,
   including feedback/recovery/health. Keep `ACCOUNT_EMAIL_ENABLED=False` initially.
   Old workers cannot interpret account-source rows, so do not enqueue until all
   workers have been replaced.
3. Privately compare web/worker signing-secret and token-setting fingerprints;
   align their canonical HTTPS origin and confirm HMAC/link flows. Never print
   secrets or transfer the signing secret into a local receipt-rehearsal setup.
   `check_platform_mail` reports the account flag and rejects code-based flows
   when enabled; it cannot establish cross-process secret equality.
4. Enable account queuing/sending consistently and run specifically authorized
   verification/reset acceptance messages with `--accounts-only --limit 1` and
   an explicit delivery ID. Verify SES feedback and consume the links through
   the actual site. This checkpoint has no authorization for those new emails.
5. After acceptance, schedule `--invitations-and-accounts` with reviewed capacity
   and monitoring. It filters receipts before selecting the bounded batch.
   Retaining `--invitations-only` deliberately leaves account requests queued.
   The current live timer remains invitation-only; no timer or flag changed here.

To pause account delivery, turn off its flag in both web/worker settings and use
invitation-only dispatch; preserve attempts and feedback processing. Disabling
the flag restores the legacy backend for new account requests, so account email
delivery is unavailable if that backend remains locmem. Drain or expire pending
account rows before rolling back to pre-account worker code. Do not reverse the
schema migration while account evidence exists.

**72 focused mail tests passed**, including 15 new account/concurrency/combined
scope cases. Provider sends are mocked. Restricted-role HTTP tests consume real
allauth verification/reset links and verify single-use password reset, signup
login compatibility, generic unknown-account responses, queue atomicity,
stale-state cancellation, suppression and source isolation. Real delivery and
production activation remain outstanding.

## Ongoing invitation dispatch enabled (2026-09-29)

Owner authorized ongoing invitation email activation independently of charging.
At **17:12 IST**, `PLATFORM_EMAIL_ENABLED=True` was aligned in Compose's explicit
web environment, `platform-mail-20260926/public.env` and the root-only worker mail
environment. The existing image was preserved and web recreated with the new
setting. Dispatch marker is present; the existing dispatch timer is enabled/active
and runs **`--send --limit 1 --invitations-only`**, 60 seconds after each run ends.
Feedback, recovery and health timers remain active. Receipts are excluded before
batch selection; generic/receipt dispatch is not authorized by this activation.

Read-only restricted checks at **17:14 IST** confirm a later scheduled dispatch
succeeded, zero due messages, no queue/source/health flags, and unchanged billing
and mail fingerprints. All checkout, trial-start and recurring flags remain false.
The queue was empty at activation: no old invitation was replayed, no new test
message sent, and no subscription, invoice or payment created. Prior SES invitation
delivery/authentication/acceptance evidence remains valid; this verifies ongoing
scheduling rather than a new recipient delivery.

Two earlier enablement attempts caught independent disabled worker/Compose
overrides and rolled back before dispatch. The final candidate verified all
effective settings first. Private backup/candidate/preflight/activation evidence
is in `invitation-ongoing-20260929-v3/` under the deployment directory; local sanitized
reports are `outputs/invitation-ongoing-{prepare,apply,verify}-20260929.json`.
Credential values, billing flags, worker image and source/schema were unchanged.

To pause invitations, disable/stop `rokkad-platform-mail-dispatch.timer` and remove
`/root/rokkad-platform-mail-dispatch.enabled`; let any in-flight send finish and
inspect its recorded outcome. Keep feedback/recovery/health active. A full setting
rollback restores the three saved files and recreates web with the same image;
never rewind delivery attempts or replay uncertain sends. Future deployments must
preserve all three enablement values and the invitation-only worker arguments.

**35 tests passed** across the 34 existing focused cases and a new restricted-role
fresh-owner journey: create Workspace, queue invitation, dispatch once despite a
second worker pass, accept with verified identity, create no subscription/payment.
The provider send is mocked in that integration test. Public 30-day trial preparation
is separate: see the [selected offer](../plans/public-workspace-trial.md).

The dated paused checkpoints below remain historical. The first live receipt
procedure must now pause the ongoing invitation dispatcher for any separately
approved receipt rehearsal and restore its previously active state afterward;
there is still no authorization for scheduled receipt delivery.

## Receipt-only preparation (2026-09-29)

The command now accepts `--receipts-only`, mutually exclusive with
`--invitations-only`. Both scopes filter before the batch limit and refuse an
explicit queued delivery of the other source type for sending or capture. Neither
scope can apply to global stale-claim recovery. With neither flag, the existing
general command behavior remains unchanged. These are selection boundaries, not
permission to send: ordinary enablement, live invoice classification, paid-source,
suppression, attempt and uncertain-outcome rules remain in `dispatch_one`.

All **55 focused tests** passed across dispatch, operations, controlled receipt
rehearsal and mail delivery. At **12:30 IST**, worker service/watchdog references
were updated to `rokkad:receipt-worker-20260929-e4bee6e23a41`, image
`sha256:49b1dd5f3ce888e2a5d71ca44506db9d1b85fea07097bd3e95ba7f4a031beb9d`.
It overlays only `dispatch_platform_mail.py` on the previous worker image;
application web and schema are unchanged. Command SHA-256:
`e4bee6e23a416b7a0e3510fe6d17729a156fd3b6c3e4ab65a7de153864baff83`.

Read-only restricted preflight and verification preserve every billing/mail table
fingerprint: four historic deliveries, six attempts and zero invoice receipts.
SES configuration is ready in the worker; web deliberately has no SES credential.
Provider mode is live consistently, but checkout/trial/recurring/sending remain
false. Monitoring timers were paused only during replacement, current invocations
finished, and supervised feedback/recovery/health runs passed before resumption.
Scheduled dispatch remains **invitation-only, limit one, disabled**, with its marker
absent; its supervised start was skipped by the systemd condition. Queue due/flags
and watchdog flags are zero. Protected credential/settings hashes and sticky alerts
are unchanged; HTTPS login is 200. No external email was sent.

For the **first approved pilot receipt**, use one supervised worker invocation,
not a general queue/timer activation:

1. Complete the named pilot/payment approval and actual verified live payment first.
   There is currently no production invoice or receipt to send. Preserve JSK's
   existing trial and do not fabricate a paid source for a production rehearsal.
2. Read-only review the resulting delivery ID, paid live invoice, immutable billing
   contact, sender/reply address and rendered receipt. Confirm the intended monitored
   recipient, suppression status, attempt history and queue/DLQ/alert health. Capture
   changes status to preview-only and is not a read-only receipt preview.
3. Obtain approval for that exact email/recipient. Record and pause the currently
   active invitation dispatcher and remove its marker, allowing any in-flight send
   to finish. Shared sending is enabled for invitations; do not start a general
   queue command. Use the existing restricted worker after normal readiness checks.
   Its final command arguments must be:

   ```text
   manage.py dispatch_platform_mail --send --receipts-only --delivery <reviewed-uuid> --limit 1
   ```

4. Preserve ordinary Attempt/SES identifiers and verify feedback, recipient delivery
   and reply-path continuity. Unknown acceptance requires provider/operator review;
   never requeue it merely because feedback is absent. Keep feedback/recovery/health
   active and inspect queue and flags after the run. Restore the previous healthy
   invitation-only timer/marker state; all billing flags remain paused. Broader
   receipt scheduling needs a later explicit scope review.

This is a future receipt procedure; no such command was run during invitation activation.
Original Test Mode receipt/reply acceptance remains valid historical evidence, not
proof of a future live invoice's delivery. Google Business Starter is Active on
29 September. The owner's INR 500 payment is now verified credited with no balance
due and the payment warning cleared; the storage add-on is also Active. Paid
service starts 10 October. India tax information is still requested; maintain
ongoing billing funding. Actual live webhook delivery remains open. See the
[inbox review](../plans/monthly-billing-pilot.md#merchant-methods-fees-and-inbox-review-2026-09-29).

Private rollback copies, exact one-file build context, unit candidates, preflight
and verification logs are under `receipt-worker-20260929/` in the deployment folder.
To roll back only this command release, keep dispatch paused, pause monitoring
timers and let active work finish, restore its saved service/watchdog files, reload
systemd, verify and resume monitoring. Preserve current live credentials, shared
configuration and all delivery evidence; do not restore older pre-live environments.
Sanitized local evidence: `outputs/receipt-worker-prepare-20260929.json` and
`outputs/receipt-worker-apply-20260929.json`.

## Private catalog worker update (2026-09-28)

At **16:06 IST**, worker service and watchdog/operator references were aligned
with web on `rokkad:billing-paused-99bda8c1cb27`. Feedback/recovery/health passed
and timers resumed active; dispatch remains disabled, marker absent, invitation-only
and limit one. Final verification at **16:07 IST** confirmed restricted runtime,
paused billing/sending, six unchanged attempts, zero receipts/due messages, no
queue/health flags and HTTPS login 200 with zero web restarts. Credentials and
existing alerts are unchanged. No email was sent. Latest rollback copies and
evidence are under `/root/rokkad-catalog-release-20260928/mail-workers`.
See the [release record](billing-paused-release-20260928.md#private-catalog-update-deployed-2026-09-28).

## Seller invoice worker update (2026-09-28)

At **15:45 IST**, web and all worker image references use
`rokkad:billing-paused-60c7beeb8191`, including frozen invoice seller rendering.
Three service image references and the watchdog/operator command changed. Existing
invocations finished before replacement; supervised feedback/recovery/health runs
passed and their timers remain active/enabled. Dispatch's absent-marker condition
skipped its command; dispatch remains disabled, sending false, invitation-only,
limit one. No provider or seller configuration was installed.

Final verification found restricted runtime without superuser/BYPASSRLS, all billing
gates disabled, six unchanged attempts, zero receipts/due messages and no queue or
health flags. Credentials and alerts were preserved; no mail was sent. Private
evidence and rollback copies are under
`/root/rokkad-seller-release-20260928/mail-workers`. The rollback procedure below
applies using these latest saved files. See the
[deployment record](billing-paused-release-20260928.md#seller-invoice-update-deployed-2026-09-28).

## Worker image alignment (2026-09-28)

At **15:03 IST**, all dispatch/feedback/recovery service image references and the
watchdog/operator command were updated to `rokkad:billing-paused-4a131587ee80`,
image ID `sha256:33ed455872008db4b70c92f9eff9ea5572b6b3b47ab4c28fefe3813f109b0d48`.
This is the same source/image as the deployed web release and includes the billing
provider-mode guards. The historical invitation overlay below is superseded.

The update changed only three service image references and the image in
`watchdog.json`. Timers were briefly paused while existing invocations finished;
no in-flight consumer was killed. Unit validation and supervised feedback,
stale-claim recovery and health runs passed. Feedback/recovery/health timers remain
enabled and active. Dispatch's absent-marker condition was exercised and skipped
its command; the timer stays disabled, shared sending false, and
`--send --limit 1 --invitations-only` remains unchanged.

At **15:05 IST**, worker checks confirmed `rokkad_prod_runtime` without superuser
or BYPASSRLS, provider mode disabled, checkout/recurring/sending false, six historical
attempts and zero receipts. Queue outcomes remain two delivered, one bounced and
one complaint; no due messages, source problems, truncation or health flags.
The operator command passed; production web has zero restarts and HTTPS login 200.
Credentials, Compose, production settings and existing alerts are unchanged.
No email or payment was sent, and no schema or application source changed.

Private evidence and original configuration copies are under
`/root/rokkad-billing-release-20260928/mail-workers`: `alignment.json`,
`final-verification.json`, queue/readiness logs and `*.before` files. For an image
rollback, keep dispatch paused, stop only the monitoring timers, allow current
services to finish, restore the three saved units and watchdog configuration,
reload systemd, then verify and resume feedback/recovery/health. Preserve credentials,
alerts and delivery evidence; do not reverse database migrations. Old worker images
remain available. Broader dispatch and live billing still need launch acceptance.

## Monitored single-invitation delivery (2026-09-28)

The owner selected admin@rokkad.com for one Viewer invitation to **Rokkad Invitation
Activation TEST**, an empty new production Workspace (5), invitation 5, delivery
`89479b30-f62b-470b-bb43-f368b3f47483`. Ordinary Workspace creation and invitation
form/services enforce owner authority, saved role policy and capacity. No business
data, subscription payment or recipient membership was created for this check.

The existing **feedback and recovery timers are now enabled and active**. Their
first supervised runs succeeded before dispatch; health monitoring stays enabled.
The installed general dispatch timer remains **disabled**, marker absent and shared
`PLATFORM_EMAIL_ENABLED=False`. A transient oneshot systemd job used the reviewed
invitation image with process-only `PLATFORM_EMAIL_ENABLED=True` and exact arguments
`dispatch_platform_mail --send --limit 1 --invitations-only --delivery
89479b30-f62b-470b-bb43-f368b3f47483`. A private send-started marker prevents automatic
reruns after uncertainty. No shared configuration or persistent sending gate changed.
This accepts a bounded supervised command, not ongoing scheduled dispatch.

At 14:09 IST the invitation arrived in the Gmail Inbox in three seconds, with
SPF/DKIM/DMARC PASS, TLS, `notifications@notify.rokkad.com` sender and
`support@rokkad.com` Reply-To. The actual received HTTPS link correctly rejected
the current owner session's mismatched email. The fresh invitation stays pending
until 1 October 14:08 IST; no recipient membership has been granted. Earlier
successful recipient acceptance remains separate historical evidence.

Canonical feedback recorded Send and Delivery with exactly one attempt. At
14:11 IST, health was clear, due queue empty, six total historical attempts and
zero invoice receipts. Source SQS/DLQ each showed zero available/in-flight messages.
No additional bounce/complaint simulator messages were sent; prior suppression
acceptance remains applicable. No receipt or live billing gate changed.

Private fixture, before-send, result and final-verification reports are under
`/root/rokkad-invitation-activation-20260928`; never rerun preparation/send blindly.
Screenshots: `outputs/invitation-activation-inbox-20260928.png`,
`outputs/invitation-activation-auth-20260928.png`, and
`outputs/invitation-activation-identity-20260928.png`. Keep feedback/recovery running
to reconcile any late events. To return those monitors to the previous paused state,
disable/stop their timers and allow active consumers to finish before stopping services;
do not purge messages or clear delivery evidence. General dispatch already remains off.

Next is reviewed ongoing invitation scope if desired, or continued FW-019 provider
acceptance/live billing work. Receipt sending requires its separate deployment and
acceptance. Google Workspace account billing continuity remains an owner dependency.

## Paused invitation worker and IAM cleanup (2026-09-28)

At this earlier checkpoint the production dispatch unit was installed but **paused**, using
`rokkad:invitation-worker-20260928-31f6aa88dd72` and
`manage.py dispatch_platform_mail --send --limit 1 --invitations-only`.
This supersedes the earlier limit-20 installation below. The flag filters out all
invoice receipts before slicing the batch. An explicit queued receipt is refused
for both sending and capture; invitation-only global stale recovery is refused.
Normal dispatch authority, suppression, claims, attempts and feedback are unchanged.
The three new regressions and existing mail/operations suites total **39 passing tests**.

The image overlays only the dispatch command on
`rokkad:mail-ops-20260926-1b55551552cd`; source command SHA-256 is
`31f6aa88dd728d6e9e7e529a7f1d16b250ea2297a543e47bb2bfa241281d441e`.
The original image ID is pinned in the private manifest. Production web and original
worker lack newer billing provider-mode guards. This narrow installation does not
deploy those guards, live recurring support, migrations or receipt sending.
Web, feedback/recovery/health units and credentials remain unchanged.

Private build, preflight, unit backup and installation evidence are under
`/root/rokkad-invitation-worker-20260928`. The prior unit is
`rokkad-platform-mail-dispatch.service.before`. Roll back by restoring that file to
`/etc/systemd/system/rokkad-platform-mail-dispatch.service`, then running
`systemctl daemon-reload`, with the marker absent and timers still disabled.
Do not enable the older unscoped unit as part of rollback.

Preflight confirms the restricted production database role, no pending migrations
for this deployed image, zero due deliveries, zero invoice receipts and no queue
flags. Existing historical evidence remains delivered/bounced/complaint: one each,
with five attempts. Source SQS and DLQ each show zero available/in-flight. Health
monitoring is enabled with no sticky alerts; dispatch/feedback/recovery remain
disabled, `PLATFORM_EMAIL_ENABLED=False`, and the dispatch marker is absent.
Readiness command output alone does not prove provider delivery or active workers.

AWS IAM `RokkadPlatformMailRuntime` **version 3 is default**, saved at 14:00 IST
on 28 September. Only `SandboxAcceptanceRecipientUntilSeptember28`, expired at
00:00 UTC, was removed. `SendPlatformMessages` and `ConsumePlatformFeedback`
retain their exact actions, resource ARNs, senders and region restriction. Versions
1 and 2 are retained. Screenshot: `outputs/mail-policy-cleanup-saved-20260928.png`.

Next activation must start with fresh queue/DLQ/alert review, functioning feedback
and recovery supervision, and one specifically authorized invitation recipient.
Keep the one-message invitation-only scope during observation and verify delivery
and health before expanding it. Actual sending needs explicit message authorization;
none was sent in this checkpoint. General receipts remain gated on reviewed billing
deployment and live-mode acceptance. Google Workspace prepayment/trial continuity
also remains an owner task.

## SES approval and billing-mode checkpoint (2026-09-28)

AWS support case **179042575700203** approved production access at **11:20:42 IST**
today, effective immediately in Mumbai (`ap-south-1`), with **50,000/day** quota and
**14/second** maximum rate. The approval was independently read in the authenticated
console after the owner signed in. Screenshot:
`outputs/ses-production-approved-20260928.png`. Earlier sandbox/pending notes below
describe their historical checkpoints. No provider settings or sending were changed.

Before bounded activation, recheck worker configuration/IAM, the expired temporary
recipient exception, source queue and DLQ, feedback/recovery supervision and alerts.
Do not increase worker throughput merely because the SES quota increased. The
existing controlled sender probe is not actual paid-invoice receipt acceptance.

New local billing code requires `BILLING_PROVIDER_MODE=live` and an invoice with
recorded live mode for ordinary receipt dispatch. Test/unclassified receipts remain
unchanged without an attempt or network send; invitations are unaffected. Local
capture can preview a `[TEST]` receipt without implying delivery. Prepare a separate
recipient-specific authorized Test Mode receipt rehearsal rather than enabling the
fictional queue. See [billing readiness](billing-provider-readiness.md).

## Local implementation and scope

`apps/platform_mail` sends new team invitations and newly paid subscription
receipts. The queue commits with each source. Migration `platform_mail.0001`
creates Delivery, Attempt, ProviderEvent and Suppression. It performs no data
backfill. Owner settings apply migrations; web and commands use restricted runtime
settings. Grant runtime DML/sequence access using the existing provisioning policy.

Invitations shows access state separately from Email delivery. Paid Invoice detail
shows receipt status. Failed/preview-only mail offers a POST/CSRF-protected Retry;
the service rechecks role/owner authority, validity, suppression and attempt limit.
Retry only queues email; it never captures another payment. An uncertain send
requires private operator/provider review. Never reset it to queued merely because
there is no feedback yet. Earlier untracked invitations/receipts show no verified
delivery, rather than assuming their legacy sent fields prove arrival.

This increment does not switch password resets, account-verification mail,
operational exception mail or borrower Notify traffic to SES. Those require their
own expiry-aware acceptance path. It also adds no marketing/open/click tracking.

## Worker settings

Use `.env.example` for names. Populate canonical `PLATFORM_EMAIL_BASE_URL`, sender
domain, purpose-specific From/Reply-To, region/account, configuration set, topic ARN
and queue URL. Supply dedicated SES credentials only to the worker, privately on
the server. Never use migration DB, AWS administrator/root or R2 credentials.

```text
python manage.py check_platform_mail --require-ready
python manage.py dispatch_platform_mail --capture --delivery <uuid>
python manage.py dispatch_platform_mail --send --limit 1 --invitations-only
python manage.py dispatch_platform_mail --send --receipts-only --delivery <reviewed-uuid> --limit 1
python manage.py receive_platform_mail_events
python manage.py dispatch_platform_mail --recover-stale
```

`check_platform_mail` is offline and never prints secrets or proves delivery. The
older `check_email_configuration` checks the separate shared Django backend, which
can correctly remain in capture mode. Capture renders for validation without
networking or printing bodies/tokens; it marks the selected delivery preview-only.
It must be explicitly retried to become queued again. Do not capture the whole
production queue as an incidental readiness check.

Use one non-overlapping dispatch process, a separate feedback consumer, and a
recovery run at least every few minutes. Current initial dispatch is bounded to one
invitation per invocation; the command default remains 20 and uses 1.1 seconds
between sends. SES throttling backs off 2, 4, 8, 16
minutes and stops after five attempts. A row claimed over ten minutes ago becomes
uncertain. Provider events can subsequently resolve it. New claims must commit
before network I/O; do not call dispatch inside another transaction.

Process feedback before dispatch where practical. Poll SQS repeatedly under a
supervisor/timer; each invocation long-polls ten seconds and reads up to ten events.
Alarm on growing oldest queued age, unknown outcomes, dead-letter messages,
complaints and sustained failures. Keep logs to IDs and sanitized codes. Production
acceptance must verify these supervisors and alert handling, not just the command.

## AWS resource plan (Mumbai)

- SES configuration set `rokkad-platform`, required TLS, shared IP pool, no archive
  or open/click destination. Event destination: SEND, REJECT, BOUNCE, COMPLAINT,
  DELIVERY, RENDERING_FAILURE, DELIVERY_DELAY.
- SNS standard topic `rokkad-platform-events`, no email subscription.
- SQS standard queue `rokkad-platform-events`, managed encryption, 120-second
  visibility, four-day retention, long polling 10 seconds.
- SQS `rokkad-platform-events-dlq`, managed encryption, fourteen-day retention;
  source redrive after five receives; allow redrive only from the source queue.
- SNS-to-SQS subscription with RawMessageDelivery=false; queue policy allows
  `sns.amazonaws.com` SendMessage only from this exact topic and AWS account.
- SNS topic policy allows `ses.amazonaws.com` Publish only from this AWS account
  and configuration-set ARN. Do not permit public subscribe/publish.
- A dedicated runtime IAM principal can `ses:SendEmail` for the verified
  `notify.rokkad.com` identity/configuration set and the two chosen From addresses,
  and `sqs:ReceiveMessage`/`sqs:DeleteMessage` on the one source queue. No IAM,
  identity administration, SNS Publish, SQS SendMessage or other bucket access.
  Keep only operators able to inspect/redrive the dead-letter queue.

Queue bodies contain recipient/header metadata and need restricted access and
finite retention. SNS message signature validation is not a replacement for these
private queue policies; the consumer is not an HTTP webhook. Do not enable a public
endpoint that calls its reconciliation function.

The following statements are the prepared service grants. Substitute the current
account ID in the console; preserve separately reviewed operator administration.
Never substitute a wildcard account, configuration set or topic. The SNS grant
matches the [SES configuration-set destination policy](https://docs.aws.amazon.com/ses/latest/dg/event-publishing-add-event-destination-sns.html).

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "OnlyRokkadConfigurationSetPublishes",
    "Effect": "Allow",
    "Principal": {"Service": "ses.amazonaws.com"},
    "Action": "sns:Publish",
    "Resource": "arn:aws:sns:ap-south-1:ACCOUNT_ID:rokkad-platform-events",
    "Condition": {"StringEquals": {
      "AWS:SourceAccount": "ACCOUNT_ID",
      "AWS:SourceArn": "arn:aws:ses:ap-south-1:ACCOUNT_ID:configuration-set/rokkad-platform"
    }}
  }]
}
```

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Sid": "OnlyRokkadTopicEnqueues",
    "Effect": "Allow",
    "Principal": {"Service": "sns.amazonaws.com"},
    "Action": "sqs:SendMessage",
    "Resource": "arn:aws:sqs:ap-south-1:ACCOUNT_ID:rokkad-platform-events",
    "Condition": {
      "StringEquals": {"aws:SourceAccount": "ACCOUNT_ID"},
      "ArnEquals": {"aws:SourceArn": "arn:aws:sns:ap-south-1:ACCOUNT_ID:rokkad-platform-events"}
    }
  }]
}
```

Audit identity policies as well as these resource policies: do not give runtime
`sns:Publish` or `sqs:SendMessage`. The consumer's trust assumes that only SES's
configured publication path can insert events; a general queue writer would
invalidate that assumption. Keep resource policy administration operator-only.

## Acceptance and deployment order

Installed runtime policy name: `RokkadPlatformMailRuntime`; programmatic
user: `rokkad-platform-mail-runtime`, without console access. The console JSON
validator reports zero errors, warnings and security findings. Its service summary
also displays a generic unused-action/resource notice; do not broaden resources to
silence that notice. The [SES v2 authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_sesv2.html)
supports both resource types and the sender condition below. Real-provider
acceptance has proved sending from both configured addresses and private feedback.
The baseline policy below excludes the temporary sandbox-recipient exception.

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "SendPlatformMessages",
      "Effect": "Allow",
      "Action": "ses:SendEmail",
      "Resource": [
        "arn:aws:ses:ap-south-1:ACCOUNT_ID:identity/notify.rokkad.com",
        "arn:aws:ses:ap-south-1:ACCOUNT_ID:configuration-set/rokkad-platform"
      ],
      "Condition": {"StringEquals": {
        "ses:FromAddress": [
          "notifications@notify.rokkad.com",
          "billing@notify.rokkad.com"
        ],
        "aws:RequestedRegion": "ap-south-1"
      }}
    },
    {
      "Sid": "ConsumePlatformFeedback",
      "Effect": "Allow",
      "Action": ["sqs:ReceiveMessage", "sqs:DeleteMessage"],
      "Resource": "arn:aws:sqs:ap-south-1:ACCOUNT_ID:rokkad-platform-events"
    }
  ]
}
```

Controlled acceptance on 2026-09-26 exposed an `AccessDeniedException` for the
verified **recipient** identity `admin@rokkad.com` while simulator sends succeeded.
Policy version 2 adds a separate approved statement on that exact identity only:
`ses:SendEmail`, the same two `ses:FromAddress` values and Mumbai condition,
`ForAllValues:StringEquals` on `ses:Recipients` to `admin@rokkad.com`, and
`DateLessThan aws:CurrentTime=2026-09-28T00:00:00Z`. It does not permit sending
**from** admin or provide mailbox access. Remove this obsolete test statement at
post-sandbox policy cleanup; its permission expires independently of cleanup.
Do not broaden to `Resource: "*"` to bypass this sandbox issue.

The inbox invitation had two definite rejections followed by one accepted attempt
through the audited retry service. Both the invitation and separate no-payment
billing-sender probe arrived and passed Gmail SPF/DKIM/DMARC; support/billing
Reply-To, custom MAIL FROM and TLS were verified. Simulator Bounce/Complaint
events created suppression; retries were refused without another send. A later
Delivery did not downgrade Complaint. The invitation link correctly rejected the
existing owner's mismatched email. Subsequently accepted through ordinary Google
sign-in as the invited admin address; verified email and exactly one isolated
Viewer membership were confirmed read-only. The test Workspace's subscription
gate remains intact, and the original owner browser session was restored.

Server-private `platform-mail-20260926/acceptance/` holds fixture IDs, invitation
outcomes and billing transport/event evidence, with bounded test scripts/logs
alongside it. The billing probe never created an invoice or claimed payment: its
separate collector checked exact SNS source, account, identity, configuration set,
recipient and saved attempt/message IDs before acknowledging its events. Ordinary
source-backed invitations used the application reconciler. Do not feed arbitrary
untracked probes into the normal consumer or fabricate paid production fixtures.
Reply composers selected the correct support/billing aliases and labelled
self-mailbox replies were sent. After specific permission, one external Gmail
message addressed to both aliases arrived in admin's Inbox, with SPF/DKIM/DMARC
PASS and `Delivered-To: support@rokkad.com`. Reference: `ROKKAD-ALIAS-20260926`.
This is actual external receipt, unlike a self-mailbox Sent copy, but the combined
message does not independently isolate billing's envelope-delivery path. Record
that limit rather than claiming two separate recipient tests were performed.

SES production access was requested on 2026-09-26 with explicit acknowledgement of
AWS terms/AUP and requested-recipient/bounce-handling commitments. Case
`179042575700203` received a factual follow-up describing the limited transactional
scope, recipient sourcing, frequency, controls and placeholder content examples.
AWS shows **Customer action completed** after the response; this is not production
approval. Keep general dispatch disabled until approval and operational acceptance.
The private operator procedure for human stop-mail requests and alerts has passed
operational acceptance, alongside automatic bounce/complaint suppression. Do not claim a
marketing unsubscribe interface or automated opt-out UI exists.

Credential installation plan: after explicit access/transfer approval, create one
access key for this user and transfer it through a loopback-only form and SSH to
`/root/rokkad-platform-mail.env` on the production Linode. Use root ownership and
mode 0600, no repository/OneDrive copy, no credential-bearing logs or snapshots.
The temporary receiver must accept only the intended credential fields, validate
Origin/Host and a single-use nonce, and stop after installation. Keep dispatch
disabled; provide these dedicated credentials only to the mail worker at rollout.

2026-09-26 installation completed with explicit approval: the root-private file
has mode 0600, STS confirms the intended principal, clipboard was cleared and the
one-use receiver exited. Web receives only the separate nonsecret `public.env`.
The deployed image is `rokkad:mail-20260926-2f39723e810c`; private archive/source
manifests identify the working-tree overlay on `0f582472` (not a new Git commit).
Owner migration and runtime grants passed, with no backfill and server-only backups.

On this Linode, `rokkad-platform-mail-{dispatch,feedback,recovery}.service` and
matching timers are installed and validated. Timers remain disabled. Dispatch
requires `/root/rokkad-platform-mail-dispatch.enabled` as well as
`PLATFORM_EMAIL_ENABLED=True`; both gates are off. Services run bounded commands
inside a read-only, nonroot Docker container with the restricted database role,
dedicated mail key and no published port. Intervals are 60 seconds for dispatch,
15 seconds for feedback, five minutes for recovery; same-unit invocations do not
overlap. Review queue age/failures and service alerts before enabling schedules.
Keep feedback active when subsequently pausing dispatch. The successful zero-event
SQS poll proves queue access only, not SES event routing or recipient delivery.

1. Verify SES identity/DKIM/MAIL FROM, Google inbox aliases and monitoring DMARC.
2. Create and review the exact topic/queue/configuration-set policies. Test allowed
   SES publication and denied public/wrong-topic/wrong-account enqueue.
3. Create/install scoped runtime credentials privately; do not emit them in logs,
   chat, browser snapshots or repository files. Retain application sending off.
4. Build/test the release candidate; take the usual server-local backup; apply
   the migration through owner settings. Verify restricted web/worker access and
   zero unintended backfill. Configure supervisors without starting bulk dispatch.
5. Authorize a synthetic invitation to a verified controlled inbox. Send only its
   delivery UUID and reconcile the real provider ID/delivery event. Confirm headers
   (SPF/DKIM/DMARC), human Reply-To and the verified invitation acceptance workflow.
6. Use explicitly authorized SES simulator addresses for bounce/complaint tests;
   verify suppression and no later resend. Confirm payment failures cannot alter
   recorded invoice/payment truth with an isolated fixture, not real billing.
7. Request SES production access truthfully; wait for approval before arbitrary
   recipients. Start bounded platform traffic and observe queue/event health.

Pause by disabling the dispatch worker or `PLATFORM_EMAIL_ENABLED`; keep feedback
consumption running. Do not delete queue evidence or undo successful payments.
Rollback to a prior image needs an explicit dispatch pause and source/queue review
because old inline invitation handling does not produce durable intent.

## Operator checks and stop-mail requests

The current worker image is `rokkad:billing-paused-99bda8c1cb27`, matching web.
Host scripts and a root-private `watchdog.json`
are installed in `/home/rokkad/deploy/cutover-20260924/platform-mail-ops-20260926`.
The JSON contains the exact restricted Docker worker invocation, not credentials.
Only existing privileged SSH/deployment operators can invoke these commands;
Workspace membership does not authorize global mail suppression. No new platform
superuser is required. Use your attributable operator identifier and a request
reference, never message content, in the audit arguments.

On the server:

```sh
MAIL_OPS=/home/rokkad/deploy/cutover-20260924/platform-mail-ops-20260926
sudo python3 "$MAIL_OPS/platform_mail_operator.py" --config "$MAIL_OPS/watchdog.json" check
sudo systemctl status rokkad-platform-mail-health.service --no-pager
sudo journalctl -u rokkad-platform-mail-health.service -n 20 --no-pager
```

The check prints status counts, due age, sanitized problems and delivery UUIDs,
never addresses, bodies or invitation tokens. It flags uncertain acceptance,
failed sends, stale claims, invalid queued sources and new bounce/complaint events.
The queue review is bounded to 200 pending sources and explicitly flags truncation.
Paused queues do not trigger an overdue-send alarm. Do not replay old `sent` flags,
retry unknown acceptance, or erase evidence to clear a warning.

`rokkad-platform-mail-health.timer` runs every five minutes. Worker `OnFailure`
hooks write root-private sticky alerts under `/var/lib/rokkad/platform-mail/alerts/`.
The health service fails while these remain, even after a later successful worker
run. `/var/lib/rokkad/platform-mail/health.json` records the latest inspection.
These are local journal/SSH-visible alerts, not email/SMS/external paging. The
operator must check them during monitored activation and at least daily afterward.
Also inspect **AWS Mumbai SQS > Queues** for source/DLQ available and in-flight
counts. Runtime credentials deliberately lack DLQ administration; no automatic
DLQ monitor or redrive is installed. Preserve rejected event evidence, investigate
the cause and authorize any redrive separately; never purge to make counts green.

For a verified request received through the support/billing inbox:

1. Record the request reference privately. Pause dispatch by moving its root-owned
   marker to a private paused filename, stop its timer, and let any current service
   invocation finish. Do not kill an in-flight provider request or claim an already
   accepted message can be recalled. Keep feedback running after general activation.
2. Confirm dispatch is inactive, then run the command below. It refuses if the marker
   exists or dispatch is active. Enter the address at the hidden prompt; never put it
   in shell history. The address is normalized and hashed. The audit records the
   operator/reference and hash, not the raw address; existing suppression reasons
   are preserved. Audit failure rolls back the change.
3. Run the queue check, verify suppression, and review whether controlled resumption
   is appropriate. Suppression applies to platform invitations and paid receipts;
   it does not delete invoices/payments or unsubscribe unrelated message systems.

```sh
sudo python3 "$MAIL_OPS/platform_mail_operator.py" --config "$MAIL_OPS/watchdog.json" suppress --operator YOUR_OPERATOR_ID --reference REQUEST-123
```

There is no general unsuppress UI/command. A disputed suppression needs an explicit
operator review, including the original complaint/bounce and the recipient's request.
The operator identifier is an audited assertion by an already privileged SSH user,
not an impersonated application account. Retain SSH/sudo logs for that attribution.

For an alert, inspect its service journal and source outcome, resolve the cause,
then archive **only that reviewed alert file** in a root-private incident directory
with the reviewer, reason and resolution. Run the health service again. Do not
bulk-clear alerts. `reviewed_before` is the explicit acknowledged-event baseline;
advance it only after reviewing intervening bounce/complaint records. Failed or
uncertain deliveries still require their normal source-aware resolution.

Acceptance on 2026-09-26 temporarily started the three schedules while both sending
gates were off, proved dispatch was skipped, ran feedback/recovery, and injected
one synthetic systemd failure. Its alert persisted until explicitly archived;
health then passed. The existing bounce simulator suppression was audited again,
without a send or new recipient. Queue hashes/attempt count were unchanged. Both
SQS queues showed zero available/in-flight. All three worker timers were restored
to disabled; only the health timer stays enabled. Evidence is server-private in
`operations-acceptance.json`. Sixty-one focused tests passed, including isolated
checkout/payment confirmation, exactly one receipt, rendering, feedback and replay
protection with mocked payment/SES boundaries. This is distinct from the previous
live no-payment billing-sender transport test.

After SES approval, recheck the identity/configuration, queue sources, suppression,
worker health and SQS/DLQ; remove the obsolete sandbox-recipient exception in a
separately reviewed IAM cleanup. Set both sending gates deliberately, enable
feedback/recovery and only bounded dispatch, then inspect each initial outcome.
Approval alone is not activation. Any later pause must preserve feedback collection
and payment truth. Broader unattended traffic needs an agreed external alert route.

References: [SES event contents](https://docs.aws.amazon.com/ses/latest/dg/event-publishing-retrieving-sns-contents.html),
[SNS-to-SQS permissions](https://docs.aws.amazon.com/sns/latest/dg/subscribe-sqs-queue-to-sns-topic.html),
[SES SendEmail API](https://docs.aws.amazon.com/ses/latest/APIReference-V2/API_SendEmail.html).

## External health heartbeat preparation (2026-09-29)

The host watchdog now accepts an optional root-private Better Stack heartbeat URL.
It pings only on healthy, enabled dispatch; failures or pauses withhold success,
allowing an external timeout to detect worker or host loss. It sends no customer
payload, refuses redirects and redacts URL-bearing errors. Eight focused combined
report/watchdog tests passed. The hook is deployed but **unconfigured/disabled**;
local health remains the only activated alert evidence. The owner selected
admin@rokkad.com, but external recipient/account allowance and a bounded failure/
recovery email rehearsal still need acceptance. No external alert was sent.
See [configuration, semantics and next steps](onboarding-monitoring.md#external-alerts-preparation-checkpoint).
