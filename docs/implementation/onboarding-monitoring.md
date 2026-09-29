---
status: active
owner: project
updated: 2026-09-29
tags: [onboarding, operations, monitoring, billing]
related: [platform-mail.md, public-trial-release-20260929.md, ../plans/monthly-billing-pilot.md]
---

# Onboarding monitoring

The owner confirmed no real customer signup yet and selected **admin@rokkad.com**
for operational failure alerts. The report observes saved control-plane evidence;
it does not create an account, send mail, grant access, start a trial or charge.

## Read-only report

Sign into Rokkad as the permanent platform administrator using Google, then open
**Django administration → Onboarding Progress → Onboarding report**. Its named
route is `admin:onboarding_progress_report`. The ordinary Workspace owner account
does not have platform-report access; do not grant extra privileges to use it.

The view accepts GET only and requires an active platform superuser. The same
guard protects the selector and command, and rejects Workspace context. It reads
only global identity, ownership/membership, onboarding, subscription/access and
invitation/delivery evidence. No borrower data or invitation/authentication tokens
are returned. There is no new schema or tracking event stream.

The default is accounts created in the last 30 days; adjust **Signed up since**
and search by email, username, Workspace name or slug. The date filters account
creation, not trial acceptance. Accounts predating that cutoff require an earlier
date even if their Workspace/trial was created recently. Results exclude disabled
and platform-superuser accounts, including the disabled account-mail rehearsal.
An active test account is not automatically distinguishable from a real customer.

The report shows:

- Account creation, current email verification, profile and wizard evidence,
  including an explicitly skipped team step and accounts without Workspaces.
- Each current owner's Workspaces, public-trial acceptance and original actor,
  stored subscription status, trial end, lifecycle and effective current access.
- Member counts including the owner, invitation outcome counts and recent mail
  delivery/attempt evidence. Invitation acceptance and current membership are
  separate: a formerly accepted teammate may have been removed.

Steps describe the furthest saved milestone, not a chronological event log.
Wizard completion alone does not prove the team joined. Provider acceptance or
delivery does not prove an email was opened; delivered means recipient mail
server acceptance. Pending stored invitation counts can include expired rows;
the recent detail shows the computed expiry state.

Pagination is 25 accounts with at most 10 owned Workspaces per account and 10
recent invitations per Workspace. Total counts and truncation are shown. The
report is a refreshable snapshot, not background polling or a failure alert.

Operator CLI, using the restricted production runtime and the actual platform
administrator ID:

```text
python manage.py report_onboarding --actor-id 9 --since 2026-09-29T13:36:55Z
python manage.py report_onboarding --actor-id 9 --query CUSTOMER_EMAIL
```

Command output contains account email addresses. Keep it private; do not attach
it to external alerts, paste it into public tickets or commit snapshots.

## First real journey

1. Refresh after a real owner signs up. Confirm their exact account and current
   verification state; do not classify a signup as successful from HTTP 200 alone.
2. Confirm Workspace ownership, saved public-trial acceptance, 30-day end date,
   full access and the intended six-person entitlement. Existing internal trials
   must not be counted as newly accepted public trials.
3. Inspect each team invitation: queued, provider-accepted/delivered, then accepted
   with current membership. Use private mail health for a failed, unknown, bounced,
   suppressed or overdue delivery; do not blindly resend an uncertain delivery.
4. Verify the invited person can enter that Workspace with the assigned role.
   Invitation acceptance alone does not prove this browser step or correct role
   permissions. Observe a customer-authorized session or ask for their result.
5. Record only a sanitized outcome and any actionable defect. Avoid fake signups
   or additional test emails as a substitute for the real journey.

## External alerts: prepared, not activated

The existing host watchdog now supports an optional **Better Stack heartbeat**.
It sends an empty HTTPS request only when the existing queue/service inspection
has no flags and the dispatch marker is present. It withholds success on failure
or pause, so an external missed-heartbeat alarm can detect worker failure, network
loss or host loss. It does not depend on the SES delivery path it monitors.

The optional `heartbeat_url` belongs only in the root-owned private watchdog
configuration. Only the documented Better Stack HTTPS heartbeat path is accepted;
redirects are refused, requests have a ten-second timeout, and exception details
and the capability URL are never printed. No customer data, email bodies, queue
contents, credentials or raw errors are sent. Local health records distinguish
disabled, withheld, sent and failed; a failed ping adds a local health flag.

**No URL is configured, no heartbeat has been created, and no external alert has
been sent or verified.** Existing local health and sticky worker-failure evidence
remain operational. `admin@rokkad.com` is the selected recipient, not yet a verified
external route. The existing Better Stack account uses a different inbox. Its
create-heartbeat page displays a billable/additional-heartbeat label; billing says
Free. Public pricing advertises a free allowance, so do not infer that this account
can create the needed monitor at no cost or that a paid upgrade is required.

Before activation, establish the recipient and actual account allowance without
buying an upgrade or granting unreviewed responder/admin access. Prepare one
`Rokkad platform mail health` heartbeat, expected every five minutes with five
minutes of grace. Keep customer details out of its metadata. Review/authorize
any account access change and the bounded failure/recovery email test, then load
its secret URL privately, observe a healthy ping, a controlled missed-ping alert
at the chosen inbox and recovery. A stopped host cannot report its own failure;
the external timeout is essential. Planned maintenance must pause that external
monitor explicitly rather than send false healthy pings.

Official references reviewed 29 September 2026:
[heartbeat behavior](https://betterstack.com/docs/uptime/cron-and-heartbeat-monitor/)
and [pricing](https://betterstack.com/pricing). Account-specific allowance and
recipient verification remain separate acceptance checks.

## Validation and deployment

Eight focused tests passed under the owner-backed test database, with report DML
fixtures and report reads executed as a restricted role. Coverage includes
authorization, global-context enforcement, SELECT-only reporting, expired trials,
delivery versus acceptance/membership, account filters/pagination, GET-only admin
access, and the heartbeat's disabled/unhealthy/redirect/secret-error behavior.
The first expiry fixture was corrected because Subscription creation initializes
its dates; it now explicitly sets the expired date after creation.

Deployment uses a five-file application overlay on the current public-trial image
plus the optional host watchdog hook. It requires no migration or static rebuild.
The first candidate exposed unreadable newly created template directories; the
image build now assigns those directories normal traversal permissions. Production
acceptance runs the selector and admin template inside a PostgreSQL READ ONLY
transaction, validates the permanent administrator and rejects the disabled test
account. Mail timers are paused only for the switch and restored before health.

Private preparation, backup, source hashes and rollback copies are stored in
`onboarding-monitor-20260929/` beneath the server deployment directory. Rollback
restores that directory's recorded compose/watchdog/service files and previous
image, reloads systemd, recreates web, restores all four timers, and verifies HTTPS,
queue health and existing access. Do not restore an old database merely to undo
this read-only feature. The shared trial override and current mail/billing flags
must be preserved.

## Production checkpoint (2026-09-29, 19:35 IST)

The overlay is live on `rokkad:onboarding-monitor-20260929-df4b82f62000`
(image `sha256:71d5844da938e29aa9efd603696c47bb0383522cdc7d8e00daa3915234f6a6d2`).
Source hashes and the next natural scheduled dispatch passed. Production read-only
report/template checks passed, billing flags stayed disabled, private binding and
public offer stayed unchanged, and mail health had no flags. The browser's existing
ordinary-user session was correctly refused platform-report access; use the
permanent administrator's normal Google session, without changing account roles.

At preparation there were no new signups. During monitoring, a new account appeared
at 19:32 IST, created its Workspace, received its verification email on the first
attempt, verified its address and explicitly accepted the public offer at 19:34.
The trial ends 29 October 2026 at 19:34 IST, with current full access. At 19:35 there
was one owner member and no invitations. These observations establish signup,
verification delivery/consumption and free-trial activation, not a completed team
journey or confirmation that the account is a real customer. No agent-created
fixture, resend, charge or account mutation was used. Private account details were
not added to this record. Observe invitations/joined membership when the owner
chooses to continue; no automatic follow-up email is authorized by this report.
