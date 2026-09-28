---
status: active
owner: project
updated: 2026-09-28
tags: [plans, billing, subscriptions, razorpay]
related: [future-work.md, ../domain/subscriptions.md, ../flows/subscription-checkout.md, ../architecture/control-plane-contracts.md]
---

# Workspace subscription monetization rollout

The owner selected FW-019 for delivery on 2026-09-26 and confirmed the working
offer below. The owner reports Razorpay successfully reclassified Rokkad as a
software (SaaS) provider, allowed application submission, and KYC is complete.
The earlier NBFC-document obstacle is resolved for submission. The owner confirms
Test Mode offers key generation and Payment Products -> Subscriptions opens.
The regenerated test pair is verified through Payments (HTTP 200) and saved with
Windows DPAPI outside OneDrive. On 2026-09-27 the owner reported account approval
and Live/Test modes activated. Payments, Plans and Subscriptions now all return
HTTP 200 using the saved test pair; the earlier 401 is resolved. Live-key generation
is unknown and no live keys are needed for test acceptance. Local implementation can
proceed; account setup and FW-002 provider acceptance are prerequisites for a
paying pilot. Production checkout remains disabled pending acceptance.

## Production critical path (reviewed 2026-09-28)

There is no committed production date. Test acceptance is advancing, but the
recurring services still explicitly reject live credentials. Deploying the present
code and adding live keys would not enable a supported paying-pilot workflow.
Production activation requires a separate, reviewed implementation and release.

| Gate | Remaining result needed | Dependency |
| --- | --- | --- |
| Provider renewal and completion | Annual subsequent capture and final-cycle observations; preserve exact paid/held dates | Fifth fixture remains Active with one Created final-payment attempt; reconcile it before further mutations |
| Failed collection | Resolve the unexpected successful failure simulation; accept Pending/Halted/recovery | Razorpay ticket 21146171 or reproducible provider outcome |
| Due held access | Apply an eligible actual provider hold with fresh verification at its natural start | Existing monthly holds start **28 October 2026**; no altered clock or saved dates |
| Refunds and replacement agreements | Full-refund review and narrow settled reservation release accepted; exact replacement periods locally tested; actual replacement payment, general settlement and prepaid transition policy remain | Remaining policy and provider acceptance |
| Production billing boundary | Explicit mode/key checks, new invoice mode and diagnostics implemented; live recurring, legacy evidence migration, live plan binding, HTTPS callback and operations remain | Reviewed implementation, private live credentials and deployment acceptance |
| Receipts and email | Inbox/header/reply inspection and monitored worker activation | One controlled paid Test Mode receipt delivered with correlated SES feedback; general sending remains disabled |
| Commercial launch | Confirm published prices, tax/invoice identity, cancellation/refund terms, mandate duration, supported methods/fees and pilot scope | Owner decisions and account-specific verification |
| Bounded pilot | Migrations under owner role, restricted runtime checks, approved activation, monitored first transactions and settlements | All applicable launch gates accepted |

Latest receipt milestone: one actual paid monthly Test Mode receipt was delivered
to the owner-selected admin@rokkad.com mail server with exactly one audited attempt
and correlated SES Send/Delivery. The narrow command has 56 passing targeted tests.
Temporary credentials and tunnel were removed; only its settled mandate was
cancelled, preserving paid time and records. General dispatch and live billing
remain disabled. Inspect the existing email's inbox placement, authentication
headers and reply handling next; no resend is needed. See
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
- [ ] Account-specific fees and supported recurring payment methods confirmed for launch.
- [x] Contract schema/ADR, durable attempt recovery and mode binding implemented locally; creation is Test Mode only.
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
