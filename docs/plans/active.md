---
status: active
owner: project
updated: 2026-09-28
tags: [plans, active]
---

# Active work

The owner selected [Workspace subscription monetization](subscription-monetization-rollout.md)
(FW-019) on 2026-09-26. The unpublished working offer is INR 1,499/month or
INR 14,990/year per Workspace, with the owner plus five staff (six total members).
Razorpay account approval and Live/Test modes are owner-confirmed; Test Mode keys
and APIs are verified. Credentials are protected outside the repository/OneDrive.

The paused production release `rokkad:billing-paused-4a131587ee80` is deployed as
of **14:55 IST**. Its six billing migrations are applied; billing/lending fingerprints
and access remain unchanged. Runtime/RLS, owner/public pages, static and backup
checks pass. Mail worker images were aligned at **15:03 IST**; feedback/recovery/
health and restricted runtime checks passed. Dispatch stays disabled and sending
false, with invitation-only limit one preserved. Next: complete
provider/commercial and live configuration acceptance. See the
[deployment record](../implementation/billing-paused-release-20260928.md#deployment-result).

Recurring agreement preparation, owner authorization/cancellation, exact paid-cycle
recording, recovery/replay and audited held-period application are implemented
locally with matching test/live mode boundaries; actual acceptance so far uses
Test Mode only. Actual monthly/annual initial card captures,
owner recovery, cancellation and accelerated monthly renewal recording have passed.
Future payments remain held without early access; actual naturally due application
is still open. The annual midnight-IST invoice boundary found in provider acceptance
is fixed. See the [current recurring runbook](../implementation/recurring-agreements.md)
and [Status](../STATUS.md) for the latest fixture state and acceptance evidence.
Annual final-cycle acceptance is the current provider task: the fifth fixture has
one Created payment awaiting provider settlement; preserve it and resume with
GET-only reconciliation. Four prior mandates are cancelled. See the latest runbook
checkpoint before creating another fixture or cancelling the pending mandate.

The 28 September continuation submitted both provider support reports (21146138 /
21146171), implemented frozen scheduled Test Mode starts, and passed actual full
recurring refund/access-review acceptance on the earlier annual fixture. All 127
focused recurring/review/recovery tests pass. A sixth, short scheduled fixture now
has an unresolved INR 5 authorization token; no invoice/access or naturally due
acceptance. Preserve that attempt too. A subsequent release increment closed the
fully refunded annual agreement after fresh settlement review, preserving read-only
access and original history. Exact replacement periods and replay safety pass local
tests; no replacement provider mandate was created. The broad 137-test suite and
final 12 release tests pass. See the
[latest checkpoint](../implementation/recurring-agreements.md#refunded-agreement-release-and-replacement-2026-09-28).

The [production critical path](subscription-monetization-rollout.md#production-critical-path-reviewed-2026-09-28)
now has explicit provider-mode/key checks, frozen one-off mode, sanitized readiness
diagnostics and test receipt sending safeguards implemented locally. Read-only
rehearsal checks originally preserved nine queued receipts. A new owner-addressed
paid Test Mode receipt is now delivered, with one attempt and correlated SES
Send/Delivery. Its temporary worker credentials/tunnel are removed, its settled
mandate cancelled, and paid time/history preserved. Gmail Inbox, SPF/DKIM/DMARC and
the independently logged billing reply delivery now pass. Monitored general sending,
Workspace mailbox billing continuity and live recurring remain open. The scheduled
agreement is now Expired but its INR 5 token remains Created; canonical owner
refresh preserved the reservation and all financial/access records. See the
[readiness checkpoint](../implementation/billing-provider-readiness.md). The path
now explicitly lists provider failure/recovery, due held access, refund/replacement
workflows, reviewed live deployment/configuration, receipt delivery and commercial
launch decisions. The existing monthly holds begin on 28 October 2026; using them
for natural due-date acceptance makes that the earliest such checkpoint, not a
promised launch. A different acceptance method or pilot scope needs review. Present
code now supports matching live recurring keys; deployment alone does not establish pilot readiness.
No production activation, published prices or production-customer term changes.

Latest billing code adds mode-matched immediate live creation, owner authorization,
verified paid-cycle recovery, cancellation and explicit held/refund review. New live
authorization requires the default-off flag, webhook secret and clean mode evidence;
existing matching-mode recovery stays available while paused. Scheduled live starts
and live reservation release remain unavailable. Fictional/mocked regression tests
cover these boundaries; no live provider action or production activation occurred.
The paused deployment above now includes this code and its evidence review;
provider/commercial acceptance remains outstanding. See the
[workflow checkpoint](../implementation/billing-provider-readiness.md#live-recurring-workflow-support-2026-09-28).

Previous billing code adds platform-only live catalog preview and immutable local
registration of an already existing Razorpay plan. It requires explicit matching
mode, paused purchase switches and no conflicting test/unclassified billing
evidence; no mandate or charge is created. Live workflows were blocked at that checkpoint.
No real live credentials, catalog registration or production deployment was used.
At 14:14 IST both pending provider payments remained Created, with only support
acknowledgements found. The workflow implementation described above followed this
checkpoint; unresolved provider/commercial acceptance remains.
See [catalog preparation](../implementation/billing-provider-readiness.md#live-catalog-preparation-2026-09-28).

Latest mail continuation sent one authorized invitation to admin@rokkad.com using
the minimal invitation-only worker and an exact delivery ID. Inbox/authentication,
Send/Delivery feedback and health passed; the received link refused the current
owner's mismatched email. Invitation acceptance remains pending, with no new
membership. Feedback/recovery monitoring is now active; general dispatch remains
paused. The bounded delivery check is complete. Next FW-019 work returns to provider
acceptance and reviewed live billing implementation; general receipts require the
local billing guards to be deployed. See the
[mail runbook](../implementation/platform-mail.md#monitored-single-invitation-delivery-2026-09-28).

The owner selected [platform email setup and reliability](platform-email-rollout.md)
on 2026-09-26: Google Workspace for human inboxes, Amazon SES for automated
platform messages. Both accounts and support/billing aliases exist; SES DKIM is
verified in Mumbai, and custom MAIL FROM is successful. The durable invitation/
paid-receipt queue, SES transport, private feedback consumer and status/retry UI are
deployed with sending disabled. Private AWS topic/queues and scoped service grants
are connected. Dedicated credentials are installed privately and verified; the web
container has none. Owner migration, restricted runtime and SQS checks pass. Worker
units validate with dispatch/feedback/recovery timers disabled; the separate health
timer is enabled. Controlled invitation/billing-sender inbox,
SPF/DKIM/DMARC, provider delivery, bounce/complaint and suppression checks passed.
Invitation acceptance as the Google-verified invitee passed with only isolated
Viewer membership. SES case 179042575700203 is approved as of 28 September
11:20:42 IST: Mumbai production access, 50,000 messages/day and 14/second.
The authorized combined external alias test reached the admin inbox. Actual
paid-receipt delivery and supervised activation remain gates. Private operator suppression,
paused dispatch and sticky failure alerts passed live acceptance; 61 focused tests
include an isolated paid-receipt workflow with mocked provider boundaries. SQS/DLQ
counts are clear. Local monitoring requires operator review; no external pager.
Account-security mail needs its own
expiry-aware integration. General production sending remains disabled.

The owner selected the first business-dashboard increment: customer/active-loan
counts, lending activity, principal outstanding and recorded unpaid interest.
It is published as `56950044` (queue-link test correction `92aa3600`) above the
existing work queues, with date controls for
activity and explicit missing-evidence handling. See the
[metric definitions](../flows/business-dashboard.md). Validation is recorded in
Status. The approved second increment adds saved-assessment financial-health cards
locally: projected interest, economic exposure, eligible collateral value and
per-loan shortfall, with explicit freshness/completeness. Older assessments need
an ordinary refresh for V3 financial evidence. This work does not start the
monitoring worker or resume capacity tests. Next operator acceptance is bounded
automatic refresh in one development Workspace; launch capacity remains shelved.

The owner approved the [Rates/appraisal improvement order](../implementation/rates-appraisal-monitoring-review.md).
Increment 1 (quote readiness and actionable loan errors) is validated locally.
Increment 2 (effective-dated, auditable quote history) is implemented and validated;
Rates migration 0003 is applied locally. Increment 3 (monitoring freshness and
active-loan reassessment) is implemented and validated; Loans 0006 is applied locally. Increment 4 is implemented locally: complete active-loan monitoring, date-based
freshness, bounded repeated refresh and immutable policy amendments.
See [Loan health](../flows/loan-health-monitoring.md); validation passed and Loans 0007 is applied locally.
The owner's newly stated launch volumes require a capacity-hardening increment
before production readiness claims. The owner has now shelved further large-scale
testing until better hardware is available under
[FW-004](future-work.md#fw-004-launch-scale-loan-monitoring-capacity). The selected
one-hour freshness target remains unproven; do not restart long local tests
without owner resumption. See the
[capacity review](../implementation/rates-appraisal-monitoring-review.md#launch-capacity-requirements-and-review-2026-09-11).
Operator UI/content and amendment submission review is complete; checkpoint
`21a48aee` is published. Closed-loan cleanup and the first homogeneous 3,000/10,000
RLS baseline/read-reuse optimization are implemented locally. Mixed-history
3,000/10,000-active benchmarks now pass, with additional closed loans, all four
product structures, repayment/reversal evidence and price invalidation. Schedule
allocation prefetch and per-loan worker transactions with bounded Workspace turns
are implemented. The continuous 100 x 3,000-active baseline failed the one-hour target locally:
121,869 of 300,000 loans were observed assessed by 3,589 seconds. The 100 x 10,000
dataset is prepared; one phase stopped after a 706-second measurement gap, and
the next retry was stopped at owner request after 19,185 assessments were observed
at 940.65 seconds. Remaining large-scale testing is shelved in FW-004. Measured
query-optimization candidates and the acceptance requirements are preserved for
later prioritization; these partial upper-size runs establish no capacity claim.
See the [full-load report](../implementation/monitoring-capacity-test.md) and [mixed results](../implementation/rates-appraisal-monitoring-review.md#mixed-workload-and-worker-increment-2026-09-11).
The optional worker is configured in code but has not been started against normal
development or production data. Origination
age enforcement and frozen quote provenance are implemented locally for methods
that consume Rates. The first version requires today's loan/disbursal dates,
blocks changed or old approved quotes and preserves completed-action replay.
Appraisal-only date behavior is unchanged. Historical entry and overrides need
their own contract before extending this scope. See the
[origination review](../implementation/origination-rate-freshness-review.md).
See the [quote operator guide](../flows/metal-rate-entry.md). Existing form cleanup is published.

Follow [incremental project hardening](project-hardening.md), based on the
[architecture review](../architecture/2026-09-09-project-review.md). The active plan
selects work; [Status](../STATUS.md) records the checkpoint and validation.

R08/R09/R10/R13 documentation, onboarding and residue cleanup are complete.
R11 dashboard visibility/batching and R07 Loans routing are complete locally.
All Loans route families use direct Workspace adapters; response rewriting is
removed. The Loans views portion of R12 is complete: focused modules own all
handlers and views.py retains compatibility imports. See the
[module map](../implementation/loans-view-organization.md). Foundation, operator
commands and billing hardening are included in the local checkpoint.
Application checkpoints are published through fdb5e97f.
Orgs view organization is complete and published, including account/preferences
and slug adapters. See the
[orgs module map](../implementation/orgs-view-organization.md). Broader
model/form/renewal-service review selected document forms, now published
with compatible public imports; see the
[review](project-hardening.md#remaining-r12-module-review). The three license/series
setup forms are also extracted and published. Remaining form families have been
reviewed; the three economic-setup forms are published as 7c043eb0.
The eight funding forms preserve compatible public imports.
Funding and the five storage/physical-verification forms are published as fdb5e97f.
Verify publication CI; intake/lifecycle forms remain together pending a concrete need. See the
[form-family review](project-hardening.md#remaining-form-families-reviewed-after-16be7149).
Model and renewal-service moves remain deferred.

Razorpay test-mode preparation resumes under FW-019 through
[FW-002](future-work.md#fw-002-razorpay-setup-and-provider-test-mode-acceptance).
License scoping is shelved as
[FW-001](future-work.md#fw-001-optional-owner-configurable-license-scope).
License scoping does not resume from unrelated work. Physical phone/camera and
printer checks remain deferred; production acceptance is separate.

Prior delivery plans and contradictory old "next" steps are preserved in the
[active-plan snapshot](../archive/context/2026-09-09/plans/active.md), not current work.
