---
status: active
owner: project
updated: 2026-09-28
tags: [email, ses, operations, delivery]
related: [../adr/2026-09-26-durable-platform-mail.md, ../plans/platform-email-rollout.md]
---

# Platform mail operations

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
python manage.py dispatch_platform_mail --send --limit 20
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
recovery run at least every few minutes. Initial dispatch is bounded to 20 per
invocation with 1.1 seconds between sends. SES throttling backs off 2, 4, 8, 16
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

The worker-only operations image is `rokkad:mail-ops-20260926-1b55551552cd`.
Web retains the preceding image. Host scripts and a root-private `watchdog.json`
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
