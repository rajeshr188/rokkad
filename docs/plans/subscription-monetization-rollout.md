---
status: active
owner: project
updated: 2026-09-29
tags: [plans, billing, subscriptions, razorpay]
related: [future-work.md, ../domain/subscriptions.md, ../flows/subscription-checkout.md, ../architecture/control-plane-contracts.md]
---

# Workspace subscription monetization rollout

FW-019 is **in launch validation, not complete**. The monthly pilot implementation,
live catalog, credentials, webhook registration and receipt worker are deployed
with charging paused. Invitation and account mail are enabled; receipts remain
separately controlled. The 30-day public free trial is now enabled. Free access
and account activation are not payment acceptance.
The following snapshot supersedes the dated preparation history below.

## Current monthly pilot (reviewed 2026-09-29)

- **Offer:** INR 1,499/month, owner plus five staff (six members), quantity one,
  up to 12 monthly collections. Operator-prepared; annual remains unpublished.
- **Seller:** Rajesh Rathod H, confirmed address, not GST-registered; explicit zero
  GST and immutable seller details on customer invoices. Processor fees/tax are separate.
- **Pilot:** JSK, Workspace 2, existing trial preserved through **8 October,
  23:39 IST**. Its current access is unchanged; no early trial termination.
- **Production preparation complete:** reviewed paused deployment/migrations,
  restricted runtime/RLS checks, protected live keys, separate monthly Plan 2/live
  binding 1 to `plan_ThkgxD2zC0o8FL`, permanent admin@rokkad.com platform admin,
  and enabled live webhook `ThlAT5rGIawXNH` with the 14 supported events.
- **Mail preparation complete:** SES production access, controlled Test Mode receipt
  and reply delivery, invitation acceptance, and deployed receipt-only worker
  selection (55 focused tests passed). Scheduled invitation/account dispatch is now
  enabled in batches of ten; verification/reset delivery/link acceptance passed
  and feedback/recovery/health monitoring is active.
- **Merchant review complete:** recurring Card, UPI and eMandate enabled; Rokkad
  bears fees. Exact account-specific subscription fees remain unconfirmed.
- **No live agreement, invoice, payment or receipt exists.** Webhook registration
  and HTTPS/HMAC diagnostics do not prove actual Razorpay event delivery.
- **Public trial live:** 30 days and six members, one trial Workspace per owner
  account, no card or automatic charge. [Plan 3 and consent](public-workspace-trial.md)
  are deployed and enabled; local browser, production rollback acceptance and
  scheduled mail checks passed. Existing trials/access remain unchanged.

## Production critical path (reviewed 2026-09-29)

| Gate | Current result and remaining work |
| --- | --- |
| Failure/recovery | Local regression coverage exists; actual failure simulation captured successfully. Ticket 21146171 has not supplied the required failure/Pending/Halted/recovery acceptance. Preserve evidence. |
| Naturally due held access | Existing monthly fixtures begin **28 October 2026**. Apply and verify at the real eligible time; no earlier alternative acceptance path has passed. |
| Annual completion | Deferred from launch and still unresolved: final payment Created/invoice Issued despite ticket 21146138 marked Resolved. Owner-approved follow-up sent 29 September; annual remains unpublished. |
| Merchant fees and terms | Methods verified; obtain account-specific add-on/method/tax/promotion rates, and finish cancellation/refund wording review. |
| Inbox continuity | Owner's INR 500 payment verified credited, no balance due and payment warning cleared. Business Starter and storage add-on Active. India tax info remains requested; maintain funding as paid service begins **10 October**. |
| Named pilot activation | Preserve JSK's trial, verify eligibility and obtain bounded activation/first-collection approval after applicable gates pass. Scheduled live starts remain unsupported. |
| Actual live acceptance | Observe provider callback, exact payment/invoice/access, one approved receipt and settlement during the bounded pilot before broader onboarding. |
| Remaining broader scope | Actual replacement payment, general settlement/prepaid transition acceptance and ongoing mail scope remain separate; live reservation release and annual launch are excluded. |

There is **no committed paid-billing launch date**. Under the current acceptance plan, the
28 October held-period observation remains on the path to activation; the 8 October
trial expiry is not a launch promise. An earlier date requires a reviewed alternative
acceptance path, not merely live keys or an enabled merchant account. A bounded
pilot is also not completion of the full annual/renewal acceptance scope.

See [monthly pilot evidence and next actions](monthly-billing-pilot.md),
[live runtime evidence](../implementation/billing-provider-readiness.md#permanent-admin-and-live-webhook-runtime-2026-09-29),
and the [first-receipt procedure](../implementation/platform-mail.md#receipt-only-preparation-2026-09-29).

## Historical delivery checkpoints (superseded by the current snapshot)

The following narrative records earlier states. References to unknown live keys,
local-only changes, pending configuration or earlier mail images apply only to
their dated checkpoints; they are not current production blockers.

### Production critical path (reviewed 2026-09-28)

This historical checkpoint is superseded by the 29 September critical path above.

Paused production deployment completed at **14:55 IST**: verified backup, six
billing migrations, separate static volume and pinned web image are in place.
Billing/lending fingerprints and existing access are unchanged. Payments, new
authorizations and sending remain disabled. Mail workers were aligned with the
deployed image at **15:03 IST**, with feedback/recovery/health passing and active;
dispatch remains paused with invitation-only limit one. Restricted runtime and
unchanged mail attempts were verified at **15:05 IST**. Next: complete the remaining
provider/commercial and live configuration acceptance. See the
[deployment record](../implementation/billing-paused-release-20260928.md#deployment-result).

Latest billing continuation: shared recurring services now accept matching live
bindings for immediate creation, owner authorization, verified payment/recovery,
cancellation and explicit held/refund review. New live authorization requires the
default-off flag, webhook secret and clean mode evidence. Recovery stays available
while creation is paused. Scheduled live starts and live reservation release remain
excluded. All live-mode verification used fictional fixtures and mocked responses;
no production activation or real provider action occurred in that implementation
checkpoint. The paused deployment above now includes this code; provider/commercial
acceptance remains. See the [workflow checkpoint](../implementation/billing-provider-readiness.md#live-recurring-workflow-support-2026-09-28).

Previous billing continuation: explicit live catalog preview/registration is locally
implemented without enabling mandates or charges. It validates a known provider
plan through GET, preserves immutable terms, and refuses conflicting test or
unclassified billing evidence. No live credentials or real catalog changes were
made. At 14:14 IST both unsettled Test Mode payments remained Created; annual invoice
Issued, scheduled mandate Expired. Ticket searches still showed acknowledgements
only. The live agreement implementation planned at that checkpoint is now described
above; provider acceptance and commercial review remain. See
[catalog preparation](../implementation/billing-provider-readiness.md#live-catalog-preparation-2026-09-28).

Latest monitored mail check: one owner-selected admin invitation passed Inbox,
SPF/DKIM/DMARC, TLS and canonical Send/Delivery evidence with one attempt. Feedback
and recovery are active alongside health; general dispatch stays paused. The link
rejects the current owner's mismatched email, and the fresh invitation remains
pending without a new membership. This completes bounded invitation delivery, not
ongoing sending or live billing activation. Return next to unresolved provider
acceptance and live billing implementation. See the
[monitored checkpoint](../implementation/platform-mail.md#monitored-single-invitation-delivery-2026-09-28).

Previous mail preparation: the production dispatch unit now uses a minimal tested
invitation-only overlay, one message per run, installed paused. Preflight and IAM
cleanup are complete; 39 focused tests pass. Production web/older worker lack the
local billing-mode safeguards, so general receipts require a separate deployment.
No mail was sent, migration applied or live billing enabled. See the
[mail checkpoint](../implementation/platform-mail.md#paused-invitation-worker-and-iam-cleanup-2026-09-28).

Latest receipt milestone: one actual paid monthly Test Mode receipt was delivered
to the owner-selected admin@rokkad.com mail server with exactly one audited attempt
and correlated SES Send/Delivery. The narrow command has 56 passing targeted tests.
Temporary credentials and tunnel were removed; only its settled mandate was
cancelled, preserving paid time and records. General dispatch and live billing
remain disabled. Gmail Inbox, SPF/DKIM/DMARC and receipt content now pass. One
owner-approved reply was independently confirmed delivered to billing@rokkad.com
by Google Admin. Next is a reviewed mail activation preflight; Workspace account
prepayment remains pending with 12 trial days shown. At 13:43 IST the annual payment
was still Created; the scheduled agreement was Expired with its INR 5 token still
Created, reservation and records preserved. See
[receipt evidence](../implementation/billing-provider-readiness.md#addressed-receipt-command-and-paid-fixture-2026-09-28).

28 September continuation: both provider diagnostics are now submitted with owner
authorization: annual renewal **21146138**, failure simulator **21146171**. The
provider confirmation requests 4-8 business hours for an update, not a promised fix.
At 11:43 IST the original annual attempt was still Created/Issued. Optional frozen
scheduled Test Mode starts are implemented and the initial 90 recurring tests pass.
A separate fixture has a 12:20:21 IST start; its authorization outcome still needs
reconciliation. This does not yet remove the 28 October acceptance dependency.
Recurring full-refund access review passed actual provider/owner acceptance through
the existing decision workflow. All 127 recurring/review/recovery tests pass;
settled reservation release/replacement remains separate. At 12:05 IST the annual
renewal and scheduled authorization token were still Created. See the
[latest checkpoint](../implementation/recurring-agreements.md#scheduled-start-support-and-refund-continuation-2026-09-28).

Later continuation closed the fully refunded annual agreement through explicit
settlement review (release event 64), preserving read-only access and all original
history. The 137-test billing suite and final 12 release tests pass, including
shorter replacement periods and replay protection. No replacement provider mandate
was created. Both unsettled attempts remain Created after the scheduled start.
See the [latest checkpoint](../implementation/recurring-agreements.md#refunded-agreement-release-and-replacement-2026-09-28).

New explicit provider-mode checks, frozen one-off mode and readiness
diagnostics now guard configuration and evidence; ordinary SES receipt dispatch
refuses test/unclassified payment records. Seven local recurring previews are
clearly labelled Test Mode, with all nine queued receipts unchanged. AWS SES
production approval is verified (Mumbai, 50,000/day, 14/second). Actual receipt
delivery, deployment/operations and live recurring implementation remain open. See
[billing readiness](../implementation/billing-provider-readiness.md).

With the existing held-payment fixtures, due-access acceptance cannot occur before
28 October. This is a fixture-dependent earliest checkpoint, **not a promised launch
date**. An earlier pilot would require an explicitly reviewed alternative acceptance
method or scope change; neither has been selected or silently substituted. Other
engineering and external-provider work can proceed meanwhile. Do not present
mocked tests, accelerated future captures or account approval as production readiness.

Candidate being investigated before accepting the month-long wait: Razorpay documents
an explicit future `start_at` and early Test Mode charge simulation. A fresh,
short-horizon scheduled fixture might permit real held-access application sooner,
**only if fetched invoice dates actually retain the future start**. The simulator
may instead start the period immediately. Preparation now freezes/verifies an optional
schedule, preserves durable attempts and explains authorization versus collection.
The actual short fixture has not yet passed naturally due held-access acceptance.
See [scheduled-start decision](../adr/2026-09-28-scheduled-recurring-test-start.md),
[create subscription](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/)
and [Test Mode behavior](https://razorpay.com/docs/payments/subscriptions/test/).

Self-service agreement creation and scheduled conversion are unfinished. Whether
the first pilot uses operator-prepared agreements needs an explicit scope decision;
it does not remove billing correctness, receipt or production-mode requirements.

Annual method-specific gate: with the illustrative 18% tax, INR 14,990 becomes
INR 17,688.20. Razorpay's [card mandate FAQ](https://razorpay.com/docs/payments/subscriptions/faqs)
states that subsequent domestic-card debits above INR 15,000 require customer AFA
outside its listed exceptional merchant categories. Do not describe this SaaS annual
offer as guaranteed unattended card renewal. Confirm final tax-inclusive pricing,
merchant/method eligibility and the customer approval/recovery journey before launch.
This is a documented method constraint, not a proven diagnosis of a pending test
attempt. Do not change pricing, tax treatment or merchant category to bypass it.

## Provider onboarding clarification

**Latest checkpoint:** owner-reported account approval and Live/Test activation,
plus verified access to all three test APIs, supersede the category-review request
below. Do not repeat category review or key rotation. Workflow acceptance remains
required. FW-002 preparation resumes as part of selected FW-019.

On 2026-09-26 the owner reported the NBFC/SLA request above. Razorpay's
[published category-specific KYC checklist](https://razorpay.com/docs/payments/business-types-kyc-documents)
lists NBFC evidence for Banks/NBFCs/Money Lending. A lending classification is a
possible explanation, not a verified account finding. SaaS reclassification is now
reported by the owner; the applicant legal entity is still not recorded. Do not assert
that the applicant entity never lends without checking its activities, or assume
that SaaS positioning guarantees provider approval or a regulatory exemption.

The proposed payment flow is business subscriber -> Rokkad software subscription
fee -> Rokkad merchant settlement account. Borrower principal, interest, repayments
and lender disbursements are outside this integration. Describe the pawn-lending
customer audience honestly; do not hide it or supply an unrelated certificate/SLA.
No support response has been sent by the agent. Live-mode activation is now reported
by the owner; provider workflow acceptance remains pending. Account approval alone
does not activate Rokkad's production checkout.

## Test-mode preparation

**Isolated runtime ready:** an empty dedicated loopback PostgreSQL database,
restricted web runtime and fictional owner now serve local checkout on port 8083.
The owner approved a temporary Cloudflare tunnel to a signed callback-only listener;
synthetic HTTPS transport/signature/replay checks passed. The owner completed
webhook setup; monthly/annual wallet capture, signed events, duplicate rejection,
receipt intent and partial/full refund checks passed. An observed browser
confirmation failure was recovered without duplicate access; card/netbanking and
actual receipt delivery remain unaccepted. See the
[rehearsal runbook](../implementation/billing-test-rehearsal.md) for the precise
isolation, private credentials and cleanup. Production settings are unchanged.

**Latest result, 2026-09-27 16:56:35 UTC:** Payments, Plans and Subscriptions all
returned HTTP 200 using the encrypted saved test pair. No credentials or provider
entity bodies were exposed. The previous denial is resolved; no more rotation or
support escalation is needed. Credentials remain at the DPAPI path below; source
CSVs are unchanged. The browser listener/tab are closed. No payment was created.

After support advised checking Test Mode keys, a 2026-09-26 15:19:40 UTC replay
confirmed Payments 200 versus Plans/Subscriptions 401 with identical Basic auth,
same API host and no redirects. Razorpay's documented Python SDK Plan list request
also returned 401. That historical differential justified technical investigation;
account provisioning/access is a hypothesis, not a proven root cause. No further
key rotation was indicated by those results and no support message was sent by agent.
The September 27 successful checks supersede this obstacle.

**Owner-confirmed checkpoint:** Test Mode key generation and the Subscriptions
page are accessible; test keys are now generated and saved by the owner. No secrets
in chat or the OneDrive project. Core API authentication passed; recurring transaction
acceptance remains unproven. The isolated local PostgreSQL web runtime remains
available for review; the temporary webhook is disabled and tunnel/callback stopped.
Do not use the main-domain production database.

**Current entry method:** `scripts/razorpay_test_key_form.py` serves a temporary
form bound only to 127.0.0.1 on a random port. The owner enters both masked fields
directly in Chrome. A random setup token, exact Host/Origin checks, request size
limit, no-store headers and a restrictive content policy protect entry. It rejects
live IDs before provider I/O, verifies a fixed read-only Razorpay Payments endpoint
without redirects/proxy inheritance, and encrypts the entire credential with
current-user Windows DPAPI at `%LOCALAPPDATA%\Rokkad\private\razorpay-test.dpapi`.
Existing credential files are not overwritten. No request bodies, provider bodies
or secret-bearing errors are logged. The listener stops after success or 15 minutes;
the ignored form-status JSON contains only status and the temporary setup URL.
Five focused boundary tests and a Windows encryption smoke check passed. This
replaces the terminal method below, which showed no usable prompt to the owner.
Use Referrer-Policy same-origin: no-referrer caused Chrome form submissions to
fail the strict Origin check. Real Chrome dummy submission passed after the fix;
actual credentials were subsequently imported successfully from the owner's CSV.

**Earlier terminal attempt:** `scripts/save_razorpay_test_credentials.ps1` opens an interactive
credential prompt (user name = test Key ID, password = Key Secret). It refuses live
IDs and existing-file overwrite, performs only a fixed HTTPS GET of one Razorpay
payment listing, refuses redirects, and suppresses response/error bodies. Successful verification
saves a DPAPI-encrypted PSCredential under `%LOCALAPPDATA%\Rokkad\private\razorpay-test.xml`
with a directory ACL restricted to the current Windows user. The ignored
`outputs/razorpay-test-key-status.json` reports only status/time. Run it in an
interactive PowerShell window; do not pass secrets as arguments. The test secret
is decryptable only under the same Windows user on the same machine. No provider
payment or subscription is created by this helper.

Local prerequisite check: Docker Desktop's daemon is unavailable. The existing
PostgreSQL migration connection is loopback and can create a separate database;
this is an alternative for a future isolated rehearsal, not authorization to run
test billing against the existing development database. No database was created
or changed during this prerequisite check.

1. Confirm the Dashboard mode selector is set to Test Mode; check Account &
   Settings -> API Keys and the Subscriptions section. Record availability only,
   without exposing keys. If an existing test key is in use, do not regenerate it
   without understanding affected integrations.
2. Select an isolated rehearsal runtime/database and HTTPS callback before
   installing test credentials. Test-provider transactions must not grant paid
   access in the production database. Store secrets privately outside Git and
   the OneDrive workspace; keep live checkout disabled.
3. Rehearse the implemented Orders checkout first: verified capture, duplicate
   delivery, failed attempts, recovery/refund evidence and receipt intent. Record
   provider IDs privately and compare provider records with local evidence.
4. Automatic recurring renewal requires the remaining contract/cycle/cancellation
   implementation before its provider acceptance. Dashboard access alone does not
   establish that this workflow is supported by Rokkad.

References checked 2026-09-26:
[Test and Live Modes](https://razorpay.com/docs/payments/dashboard/test-live-modes/),
[API Keys](https://razorpay.com/docs/payments/dashboard/account-settings/api-keys/).
Test and live modes use separate keys; test payments move no real money.

## Working offer

| Item | Owner-confirmed working choice |
| --- | --- |
| Billing unit | One Workspace |
| Monthly base price | INR 1,499 |
| Annual base price | INR 14,990, set explicitly |
| Seats | Owner plus five staff: six total members using existing member counting |
| Annual saving | INR 2,998 versus twelve monthly payments, approximately 16.67% |
| Publication | Unpublished until launch review |

Include core loans, customers, rates, documents and reports. Assisted onboarding
and messaging remain separately priced; amounts are undecided. No automatic seat
overages, storage charges, premium support commitments or new trial duration are
approved. Trial eligibility/duration, final feature projection and tax/invoice
configuration must be reviewed before the offer is published. Illustrative
18% tax in tests exercises the existing configured calculation, not a new tax
decision. Existing customer prices, terms and access grants are not migrated.

Six total members intentionally reuses `workspace.max_members`; do not change
membership counting globally or interpret this as five total users. Pending
invitations continue to follow the existing seat-reservation policy. Review an
over-capacity Workspace before selling this plan; no forced membership removal.

## Reviewed foundation and gaps

- `apps/subscriptions/models.py`: local plans, one Subscription per Workspace,
  invoice/payment/event evidence and legacy provider ID/auto-renew fields exist.
  A provider ID field alone does not establish a recurring contract.
- `checkout.py`, `razorpay_service.py`, `views.py`, `urls.py`: owner-authorized
  Razorpay Orders checkout freezes price and entitlements, verifies captures and
  grants individual paid terms. Recurring creation, confirmation and cycle
  processing are absent. Preserve the existing manual-purchase path.
- `templates/subscriptions/`: plan selection, checkout and billing screens exist.
  Old tier labels included fixed prices, and annual savings were hard-coded to
  20%. The dashboard also has placeholder cancellation code; it is not a working
  mandate cancellation workflow.
- `access_policy.py`: natural expiry grants seven days of normal access, then
  read-only. Stored PAST_DUE/CANCELLED/EXPIRED skip grace. Never copy a provider
  lifecycle state into commercial access without evaluating paid-through dates.
- `platform_mail`: receipts have durable delivery intent, but SES production
  approval and general sending activation remain pending in FW-014.
- `create_default_plans`: reconciles an older development catalog. Do not use it
  to publish this offer or overwrite existing subscribed plans. Plan.save's legacy
  missing-annual-price fallback remains 9.6 monthly payments; set this offer's
  annual price explicitly rather than relying on that fallback.

## Delivery stages

1. **Offer preparation (complete locally).** Record confirmed prices and six
   members; show actual annual savings and neutral tier labels; stop advertising
   trials when disabled. Verify that the existing checkout freezes the explicit
   prices, tax and six-member entitlement. Do not seed or activate production plans.
2. **Recurring contract and services (local foundation implemented).** The
   [agreement ADR](../adr/2026-09-27-recurring-agreement-evidence.md) and
   [operator runbook](../implementation/recurring-agreements.md) record the schema,
   Test Mode gate, durable creation and explicit provider-ID recovery. Prepared
   owner Checkout and paid-cycle processing are implemented; creation/authorization
   remain default-off and production billing is not activated.
   Separate the mandate's status from purchased access. Persist attempt identity
   before provider creation; a timeout with unknown provider outcome must require
   reconciliation rather than blindly creating another mandate. Retain prior
   mandate history and enforce one renewable agreement per Workspace. Bind each
   provider plan to a frozen local price, currency, cycle and entitlement snapshot;
   keep test/live provider identities distinct.
3. **Verified cycle processing and recovery (implemented; initial provider cycle passed, renewals pending).** Verify webhook signatures and
   provider subscription, invoice, payment, amount, currency and purchased period.
   Only a paid cycle grants access; authorization/token payments do not. Persist
   unique cycle/payment identities and serialize changes so duplicate and
   out-of-order events cannot double-extend or shorten paid access. Recover missing
   events through provider reads. Preserve existing refund/review evidence and
   prevent manual renewal from overlapping an active mandate without reconciliation.
   `RecurringCycle` records exact provider invoice periods with unique invoice,
   payment and period identities. Initial/renewal capture, signed replay, delayed
   events, rollback, owner recovery, refunds and restricted-role concurrency pass
   local tests. Lifecycle observations do not revoke paid time. Verified future
   periods now record financial evidence with access held; replay or reaching the
   start date does not apply them. An explicit authorized, audited Test Mode command
   now applies eligible started/unexpired holds with fresh evidence and current-term
   checks. Naturally due provider acceptance remains open. Full-refund access
   decisions now pass local tests and actual annual refund/end-access acceptance.
   Unsupported period shapes remain rejected. See the
   [paid-cycle decision](../adr/2026-09-27-recurring-paid-cycles.md).
4. **Owner journey (prepared-agreement flow implemented locally).** Owner-gated
   Test Mode Checkout, status refresh, known-invoice recovery and durable cancellation
   now have local tests. See the [owner-action decision](../adr/2026-09-27-recurring-owner-actions.md).
   Creation still uses the operator command with an explicit cycle count; self-service
   creation, a launch duration and scheduled conversion remain pending. Actual Test
   Mode initial authorization and cancellation passed on September 28. Provide mandate status, payment
   recovery and cancellation of future renewal. Cancellation preserves already-paid
   access. Display uncertainty when provider cancellation is not confirmed; do not
   report success on timeout. Start with the agreed fixed plan/cycle; defer
   mid-cycle upgrades, proration and usage billing. Explain mandate duration and
   what happens at the provider's final cycle before authorization.
5. **Provider acceptance (FW-002; partial).** Create the merchant account with the correct
   business identity and website, complete required verification and confirm
   Subscriptions eligibility. Configure private test keys and signed webhooks on
   HTTPS. Rehearse existing prepaid checkout and the recurring path. Never place
   secrets in chat, tracked files or screenshots. Account approval and actual
   commercial pricing must be confirmed before live setup. Initial recurring
   capture, signed replay, owner recovery and cancellation now pass against actual
   Test Mode provider evidence. The first accelerated failure attempt remained
   Created until after cancellation, then failed; intended failure/recovery
   acceptance remains open. Paid dates stayed unchanged, despite provider
   current-period advancement.
   See [acceptance evidence](../implementation/recurring-agreements.md#actual-provider-rehearsal-2026-09-28).
   Temporary callbacks are stopped and recurring authorization is disabled again.
   A fresh agreement subsequently proved actual initial-cycle recovery with the
   webhook disabled. Its one accelerated success attempt captured after about six
   minutes. The future paid period has now been recovered once into local financial
   evidence, with existing access and entitlements unchanged; repeated recovery
   adds nothing. Held-period application is now implemented through an explicit
   review command; real future evidence correctly stays blocked until due.
   The test agreement was cancelled after settlement. See the
   [current acceptance](../implementation/recurring-agreements.md#future-period-financial-recording-2026-09-28).
   A third fresh agreement then exercised **Charge as failure** once, but the
   payment eventually captured and the agreement stayed Active. Actual
   Pending/Halted/failure recovery is still unaccepted; clarify/reproduce the
   provider simulator behavior before repeating this path. The captured future
   cycle was reconciled once without early access, then the mandate was cancelled
   after settlement. See the [latest diagnostic](../implementation/recurring-agreements.md#failure-simulation-continuation-2026-09-28).
6. **Paying pilot.** Review the offer, tax/invoice details, terms/cancellation/refund
   information, support contacts and email readiness. Apply owner migrations through
   migration settings and verify restricted runtime. Start a bounded pilot only
   after acceptance; inspect payments, settlements, invoices, receipts and access
   recovery before broad onboarding.

## Recurring access contract to implement

Successful payment buys the verified billing period. Pending authorization and
failed collection do not invent paid time or revoke a previously paid term.
Cancellation of renewal stops future charging without setting local CANCELLED
early. When paid time naturally ends, use existing grace/read-only policy;
explicit platform restrictions and Workspace lifecycle remain authoritative.
Full-refund access review remains an explicit local decision, separate from
stopping future provider charges. A delayed event from an older mandate cannot
overwrite a newer agreement or reinstate future charging.

Subscription billing is global control-plane evidence linked to a Workspace;
it never grants Membership, bypasses roles/RLS or posts borrower loan events.
Use the current owner/platform authorization and immutable audit patterns.

## Acceptance checklist

- [x] Working monthly/annual offer confirmed; owner plus five staff clarified.
- [x] First increment's pricing display and frozen-checkout tests pass (28 focused tests).
- [x] Merchant account approved and Live/Test modes active (owner-reported); all three test list APIs verified.
- [x] Merchant recurring Card/UPI/eMandate enabled, verified in account settings (29 September).
- [ ] Account-specific subscription/method fees, GST and promotion coverage confirmed for launch.
- [x] Contract schema/ADR, durable attempt recovery and mode binding implemented locally.
- [x] Immediate live recurring workflows implemented with mode-isolation regression coverage; activation remains off, scheduled starts and live reservation release excluded.
- [x] Actual Test Mode initial recurring cycle creates one invoice/payment/term; replay/recovery do not duplicate them.
- [x] Actual provider accelerated renewal captured and recorded once locally, with exact future dates and access held for review.
- [x] Authorized, audited application of eligible held periods implemented and tested, with fresh refund/current-access checks; actual future provider hold refuses early application.
- [x] Actual annual initial capture/recovery/replay/cancellation accepted; exact midnight-IST boundary fixed and six-seat paid year preserved.
- [ ] Annual accelerated renewal and final-cycle completion accepted; fifth fixture has one pending Created attempt, preserved for GET-only reconciliation (01:34:08 IST, 28 September).
- [ ] Naturally due provider held-period application accepted without changing the clock or saved dates.
- [ ] Subsequent recurring collection creates exactly one new invoice/payment/term.
- [ ] Authorization-only payment, wrong Workspace/amount/currency and forged events grant nothing.
- [ ] Replays, delayed/out-of-order events, concurrent callbacks and local rollback reconcile safely.
- [ ] Failed collection preserves paid-through access; expiry/grace/read-only and recovery pass.
- [x] Pending/Halted owner guidance and local signed-event/status recovery regression coverage pass (50 cycle/owner tests).
- [ ] Actual failure simulation yields the documented failed/Pending outcome; latest Charge as failure instead captured, with diagnostics retained and support ticket 21146171 submitted.
- [x] Actual immediate provider cancellation preserves the already-paid term and held reservation.
- [x] Optional immutable scheduled Test Mode start, owner wording and expiry guards implemented and tested; actual shorter due-access acceptance still open.
- [x] Full recurring refund/access review implemented; actual processed annual refund, owner end-access decision and replay accepted without changing purchased dates or releasing the reservation.
- [x] Separate fully refunded reservation release implemented and actually accepted; replacement creation/exact shorter period and old replay locally tested.
- [ ] Actual replacement authorization/payment and broader settlement/prepaid transition policies accepted.
- [ ] Uncertain cancellation/provider failures accepted beyond mocked tests; final-cycle completion verified.
- [ ] Manual purchases, archived/suspended Workspaces, refunds and replaced mandates are covered.
- [ ] Real provider test-mode browser/webhook acceptance and receipt delivery pass.
- [ ] Offer publication and bounded live pilot complete.

## Provider references

Checked 2026-09-26; recheck method availability and account terms at acceptance.
[Integration](https://razorpay.com/docs/payments/subscriptions/integration-guide/)
requires a provider plan/subscription and Checkout authorization. Its signature
uses payment ID followed by the server-held subscription ID, unlike Orders.
[Create subscription](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/)
defines the provider contract, including total billing cycles.
[Cancel subscription](https://razorpay.com/docs/api/payments/subscriptions/cancel-subscription/)
is the provider boundary for stopping renewal. These APIs require implementation
and real provider testing; reading the documentation is not acceptance.
