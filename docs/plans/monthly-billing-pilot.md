---
status: preparation
owner: project
updated: 2026-09-30
tags: [billing, pilot, commercial, razorpay]
related: [subscription-monetization-rollout.md, ../implementation/billing-provider-readiness.md]
---

# Monthly billing pilot

The owner selected preparation of a monthly-only, operator-prepared paying pilot
on 28 September 2026. This unpublished offer does not authorize charging.
Production paid billing remains disabled. Public free trials and invitation/account
mail are enabled; receipt dispatch remains separately controlled. See the
[free-trial release](../implementation/public-trial-release-20260929.md).

## Existing Workspace rollout and self-service preparation (2026-09-30)

The owner accepted this sequence: verify JSK's first payment after trial expiry,
then onboard **JCL and Lakshmi Pawn Broker** before their grace periods end.
Production read-only policy checks confirm all three trials end on **8 October
at approximately 23:39:08 IST**, followed by seven days of normal-access grace,
then read-only from **15 October at approximately 23:39:08 IST** if neither paid
access nor an explicit temporary access decision is in place. None has a recurring
agreement or temporary override. Each Workspace requires its own subscription;
JSK's payment cannot activate the others. No access decision was made by accepting
this rollout. If delayed, obtain the exact temporary-access scope/end before
recording an audited grant; never rewrite trial or financial history.

Paid self-service is now implemented locally: selected monthly offer, explicit
signed owner consent, durable creation and the existing authorization/recovery
page. Production still exposes only operator-prepared agreements. The new
`BILLING_PUBLIC_RECURRING_BINDING_ID` defaults to zero; both a selected binding and
the recurring gate are required. Generic checkout remains off and annual stays
private. See the [decision](../adr/2026-09-30-owner-monthly-self-service.md).
All 178 focused/regression tests passed (14 new self-service cases); provider and
SES responses are fictional mocks, not live acceptance. No migration is required.

Next release: deploy the reviewed source with selection zero and recurring off,
verify paused routes/configuration and existing trials, then perform the attended
JSK pilot after expiry. After its first capture/invoice/receipt is verified, review
public selection and ongoing receipt dispatch together. Then onboard JCL/Lakshmi
before grace ends. Publication is not automatic at expiry or after a code release.

Receipt preparation reuses the existing monitored worker, feedback, stale-send
recovery and health checks. For JSK, retain the exact-delivery, limit-one procedure
below. For public activation, first review every due queue source and recipient,
verify no test/unclassified receipt can be sent, and back up the current dispatch
unit. The prepared batch is `dispatch_platform_mail --send --limit 10` (remove
only `--invitations-and-accounts` from the existing worker command). Keep the same
private worker environment, rate delay, timeout and timers; no SES secrets go to
the web container. Verify the next scheduled run, receipt acceptance/delivery and
health. Restore the prior scope if validation fails; do not retry an uncertain
send. No scheduler or email-sending change is applied by this preparation.

## JSK selected after natural trial expiry (2026-09-30)

The owner chose **Keep JSK after its trial ends**, rather than creating an empty
paying Workspace. Keep Workspace **2**, slug **jsk**, canonical owner **1**, as the
only first pilot. Its trial ends **8 October 2026 at 23:39:08 IST**. Plan an attended
activation review **9 October or later**, subject to actual eligibility and the
specific activation approval. Nothing is scheduled to charge automatically on
trial expiry. No date/plan/status changes are authorized before payment.

Read-only production/provider checks at **18:22 IST** verified the live provider
plan **plan_ThkgxD2zC0o8FL**, local binding **1** / Plan **2**, INR **149900 paise**,
six members, frozen seller, cancellation wording, live mode and paused purchase
switches. JSK is Active with three members including pending invitations, still
on trial Plan **1**. Its generic Subscription end_date is 24 October; the canonical
trial expiry is 8 October, and the generic end is not paid coverage. There are
zero live agreements/cycles/invoices/payments/webhook events or receipt rows.
Mode evidence is clean; login/pricing return 200 and callback GET returns 405.
All four mail timers are active, health is clear, and scheduled invitation/account
batches exclude receipts. These checks establish readiness components, not actual
provider callback or payment acceptance. Evidence: ignored
`outputs/pilot-readiness-review-20260930.json`.

The review found a local transition gap: the paid-cycle handler held a first
payment solely because the expired trial's plan differs from the paid offer.
The scoped fix permits an eligible, history-free expired trial to adopt the frozen
paid plan only with a verified current captured period. It preserves trial dates,
records old terms in the existing transition audit and queues one receipt.
See the [decision](../adr/2026-09-30-expired-trial-first-recurring-payment.md).
All **139** recurring/owner/cycle/held-access/live-boundary/expired-trial tests
passed (190.014 seconds), including twenty new Test/Live-mode transition cases.
The initial fixture attempted to rewrite immutable agreement creation time; it
was corrected to create the intended date initially, without weakening the guard.

The single production source file was deployed at **18:30:43 IST** as
`rokkad:expired-trial-20260930-110476c6eb7f` over the import-repairs image. Candidate
and deployed checks passed under the restricted role in read-only transactions.
JSK's trial/member count and zero billing records are unchanged; both purchase
switches remain false. Seller/cancellation renders, exact deployed source hash,
preserved configuration hashes, public HTTPS checks and four mail timers passed.
No migration, agreement, payment or email was created. The temporary server-only
candidate environment copy was removed. Prior Compose/release records and logs
remain private under `expired-trial-release-20260930/` in the existing cutover
directory; rollback was prepared but not needed. Other operator images were not
modified by this one-file web deployment.

### Attended activation and first-payment sequence

1. The tested transition patch is deployed with billing paused. At activation time,
   recheck JSK's owner, lifecycle, trial expiry, seats/pending invitations, no legacy
   mandate, invoices or conflicting agreement, and current frozen live offer.
2. Obtain specific approval for **JSK, INR 1,499/month, owner plus five staff,
   maximum twelve monthly collections**, with owner-authorized payment and a
   reviewed receipt recipient. This preparation is not that approval.
3. Enable recurring preparation/authorization only; keep one-off checkout and
   annual publication off. Prepare exactly one agreement using binding 1 and one
   durable request UUID. Unknown creation must reconcile the existing attempt;
   never generate another UUID just to retry.
4. The canonical owner reviews the frozen agreement and authorizes on Razorpay.
   No payment credentials or OTP enter chat. Observe exact provider invoice and
   captured payment, signed callback, one local cycle/invoice/payment, correct
   Plan 2/six-member access dates and the trial-conversion audit. Authorization
   alone grants nothing; a future period stays held for explicit review.
5. If the callback is missing or fails, inspect its stored status and provider
   evidence, then use the existing owner recovery or `reconcile_recurring_cycle`
   for that exact invoice. Verify replay preserves invoice/payment/access/receipt
   counts. Never ask the owner to pay again while the first outcome is uncertain.
6. Review the single receipt intent and send only its approved delivery ID with
   `dispatch_platform_mail --send --receipts-only --delivery ID --limit 1` using
   the existing private worker environment. Confirm delivery; scheduled mail
   remains invitation/account-only. Inspect real fee/GST/settlement evidence after
   settlement; fee differences alone do not invalidate the purchased access.
7. Pause new authorization after the one-Workspace pilot. This does **not** cancel
   an authorized recurring mandate: existing callbacks, reconciliation and
   cancellation stay available, and authorized renewals remain possible. Monitor
   the provider's actual next charge date, paid-through access and Pending/Halted
   events. Cancellation requires its explicit owner action and provider confirmation.

The owner-approved direction is a limited pilot despite incomplete sandbox
acceptance, not a claim that the sandbox anomalies were fixed. Held-period,
failed-renewal/recovery and annual evidence stay tracked; annual is excluded.
The 28 October test observation remains a follow-up check, not an automatic
prerequisite for this separately approved pilot. Stop broader onboarding on any
unexplained charge, identity/amount mismatch, duplicate or payment/access discrepancy.

## Owner accepts fee uncertainty; prepare a limited pilot (2026-09-30)

The owner explicitly accepts learning exact provider charges from real payments.
Detailed fee clarification is **not a launch gate**. Retain the supplied estimates
and reconcile actual fees/GST/net settlement after the first collection; do not
delay pilot preparation for another pricing response or silently change the
customer's INR 1,499 price to recover provider fees.

Fee uncertainty is commercial, separate from the unverified Test Mode scenarios.
The proposed next step is a named monthly pilot readiness review that considers
those scenarios as explicit remaining risks rather than requiring an indefinite
wait for support. This is not a claim that failed-renewal/held-period acceptance
passed or that Razorpay confirmed a sandbox limitation.

Prepare the existing INR 1,499/month, six-member, twelve-collection offer for one
eligible Workspace with owner consent. Preserve JSK's current trial; no early
conversion is authorized. Before enabling authorization, verify the current live
callback/reconciliation path and review how to contain a failed or uncertain
first collection. During the approved pilot, verify one exact captured payment,
one invoice, correct access dates, the separately approved receipt and settlement;
stop expansion on discrepancies and reconcile before retrying. Keep annual
billing unpublished. Outstanding renewal/failure and held-period observations
remain tracked independently. This instruction accepts fee uncertainty and pilot
preparation; it does not authorize a real charge or a production switch change.

## Post-call pricing email verified (2026-09-30, 17:48 IST)

Read the new reply from **Farooq.K** in pricing thread **21174094**, subject
`Re: [Merchant] Account related assistance`, delivered to `admin@rokkad.com`.
Gmail shows the sender `rzr06py08emsp@razorpay.com`, mailed by
`fwdkim1.razorpay.com`, signed by `razorpay.com`, TLS and its verified-sender badge.
The search-list date was stale; opening the thread revealed the 30 September
17:48 message. Source: [mail thread](https://mail.google.com/mail/u/3/#search/21174094/FMfcgzQhWfTQdVcKGDJXmXbdbtxxSKML).

The email adds these **first-payment examples**, not verified settlements:

| Method | Listed fee components before GST | Listed GST | Total deduction | Net from INR 1,499 |
| --- | --- | --- | --- | --- |
| UPI AutoPay | INR 7 setup + INR 13.49 subscription add-on | INR 3.69 | INR 24.18 | INR 1,474.82 |
| Cards | INR 29.98 processing + INR 13.49 subscription add-on | INR 7.82 | INR 51.29 | INR 1,447.71 |
| Aadhaar eMandate | INR 30 setup + INR 13.49 subscription add-on | INR 7.83 | INR 51.32 | INR 1,447.68 |

The displayed components sum correctly. Card total uses rounded components;
calculating GST on unrounded percentage fees before rounding the total can differ
by one paisa. Provider invoicing/settlement will establish the actual rounding.
The examples do not show renewal deductions, INR 17 auto-UPI treatment or explicit
during/after-promotion comparisons. The body separately repeats INR 22 setup/INR 20
automatic eMandate fees, while the example uses INR 30 Aadhaar setup: ask which
mandate variant is enabled and how its renewal and add-on charges combine.
The promotion still excludes the subscription add-on; setup/GST treatment remains
unitemized. The attached PDF was not re-read in this check.

The email says integration ticket **21146138** was marked resolved. A fresh
Dashboard inspection after reading it still shows **In Progress**, with our
30 September escalation as the latest message. No new authorization procedure,
failed-renewal/Pending/Halted/recovery steps, shorter-period test or documented
Test Mode limitation is provided; generic plan/subscription creation instructions
do not resolve those cases. Do not treat the email's closure statement as technical
acceptance. Next: obtain a substantive Subscriptions integration-team response
and the remaining fee examples. No reply, provider test, new plan/subscription or
live activation was performed during this verification.

## Provider blocker recheck (2026-09-30)

At **14:39:52 IST**, a fresh GET reports **sub_TiA179M8LEPooF expired**,
zero authorization attempts/paid cycles, no current period and no invoices.
The INR 5 candidate **pay_TiA4lUn0JCbQ7q** remains Created. Historical local
financial/mail counts are unchanged and Workspace 9 has no Subscription/access.
The isolated local agreement still records Created because this read-only check
does not reconcile it and its callback is disabled. The provider attempt is now
terminal; waiting for this scheduled start cannot establish successful acceptance.
No retry, new agreement or provider mutation was performed.
The subsequent dashboard check still shows ticket **21146138 In Progress**, our
approved escalation as the latest message, and a 4-8 working-hour reply estimate.
No working procedure or documented alternative has arrived in that ticket.

At **12:58:59 IST**, the preserved shorter agreement and INR 5 payment candidate
remain Created, with no invoices, paid count or Workspace access. Read-only
dashboard checks found no provider reply after our approved escalation in
**21146138**; **21146171** remains closed without a technical answer. Pricing
**21174094** still contains the 29 September responses and displays a response
target of **1 October, 13:43**. No additional message or payment attempt was made.

Earliest-launch work is blocked pending a supported authorization/failure-recovery
procedure or documented alternative that can be validated. The fixture's scheduled
start is not itself evidence that authorization succeeded. Resume acceptance work
when the provider guidance or evidence changes; do not weaken access rules or
enable live charging to bypass this blocker. Itemized fees and bounded live-pilot
acceptance remain separate unfinished launch checks.

## Cancellation notice deployed and live readiness verified (2026-09-30)

At **12:53:58 IST**, a read-only transaction under the production restricted role
confirmed live-mode configuration, the frozen INR 1,499/zero-GST/six-member offer,
permanent platform administrator, zero live agreements/cycles/invoices/payments,
and JSK's unchanged three-member trial ending 8 October at 23:39:08 IST. Public
trial/account/invitation mail remain enabled; checkout and recurring authorization
remain disabled. Rendering an unsaved agreement revealed that the reviewed
pre-confirmation cancellation notice and refund-policy link were still absent.

Prepared a **single-template overlay** on the current Form E release. Candidate
and deployed read-only renders at **12:56:31 IST** verify cancellation confirmation,
in-flight-payment uncertainty, the refund-policy link, the frozen no-GST seller,
12-cycle wording and unavailable authorization. Exact source hash and preserved
configuration files match. Web now runs **rokkad:billing-cancel-20260930-c1db71cd66e6**;
the previous image/compose/release records are retained for rollback. No schema,
provider, account, financial or trial data changed. Login, pricing and refund-policy
HTTPS checks passed; four mail timers remain active. No test email was sent.

Rebuilt the existing offline cleanup operator on the new web base as
**rokkad:storage-cleanup-20260930-e7d7bd28c3dd** without changing its implementation.
Its read-only candidate check passed with none found; no cleanup ran. Private
release records/configuration are under
`/home/rokkad/deploy/cutover-20260924/billing-cancellation-release-20260930/`.
Local sanitized readiness evidence and source-only helpers are in ignored outputs.
This closes the cancellation-copy deployment item, not actual live cancellation
or provider acceptance. At 12:52 IST the preserved short test was still Created
with no invoice/access; it was not retried.

## Shorter rehearsal attempted and technical escalation sent (2026-09-30)

The owner selected the earliest safe launch through a shorter supported test plus
the other launch checks. Reused the existing scheduled-Test-Mode implementation
and monthly binding; no application validation, provider timestamps or clocks
were changed. Five additive migrations brought only the fictional local billing
database up to current source. Historical invoice/payment/cycle/receipt counts
were preserved. Production was not changed.

Fresh fixture: Workspace **9**, `short_monthly_20260930`, ordinary owner **1**,
agreement **8**, provider **sub_TiA179M8LEPooF**, monthly binding **1**, quantity 1,
three cycles, notifications false. Frozen start **1790753952**, **30 September
13:09:12 IST**, was thirty minutes after preparation. This is a test schedule,
not a live customer commitment; the INR 1,768.82 fixture retains illustrative tax.

One authorization used the official domestic Visa subscription test card ending
4366 and fictional contacts. The visible Test Mode checkout offered the INR 5
token; its optional card-saving OTP skip was followed by **Pay on bank's page**.
That page remained `about:blank`; checkout then reported **Payment could not be
completed**. No second authorization or simulated charge was attempted.

At **12:49:45 IST**, provider GETs still showed Created, auth_attempts 0,
paid_count 0, and no invoices. The only recent matching INR 5 payment candidate,
**pay_TiA4lUn0JCbQ7q**, remained Created with no invoice or error code; support must
confirm its subscription association. Workspace 9 has no Subscription or paid
access. Global isolated counts remain ten invoices/payments/deliveries, eight
cycles, zero held-access resolutions and one historical mail attempt. The earlier
annual Created/Issued and failed-simulation Captured results were also reverified
at 12:37 IST. A browser failure message is not a final provider payment outcome.

**119 focused tests passed** in 191.695 seconds using a dedicated test database:
agreement scheduling/authority, owner actions, paid cycles, failure/Pending/Halted/
recovery, exact held-access timing/idempotence and matching live-mode boundaries.
These are local regressions, not acceptance of actual provider failure events.

The owner explicitly approved the prepared technical escalation; it was submitted
and visibly verified in [ticket 21146138](https://dashboard.razorpay.com/app/business-settings/ticket-support/rzpind/ThM5iRU28CFNdZ/merchant/conversation),
referencing **21146171**. It requests a Subscriptions engineering review of the
new blank-bank-page authorization, reproducible failed-renewal/recovery steps,
supported short scheduling and explicit limitations/alternatives. The case remains
In Progress with a displayed 4-8 working-hour reply expectation, not a promised fix.
No keys, real customer details, attachment or callback commitment were sent.

Cleanup: local 8083 runs with new authorization false, confirmed in the owner
page; Test webhook/tunnel and outbound mail remain disabled. The browser test and
blank popup are closed. Provider attempts and history are retained unchanged.
Evidence and exact approved support text are in ignored `outputs/short-rehearsal-
20260930-*`, `billing-short-preflight-20260930.json` and
`razorpay-short-test-followup-20260930.txt`.

### Requirements for replacing the 28 October checkpoint

1. Obtain working scheduled authorization or a documented provider-supported
   alternative. Re-read this preserved attempt first; if its start passes while
   Created, do not reauthorize it or edit dates. A future replacement requires a
   separately identified durable attempt, never an automatic retry.
2. On a working fixture, verify actual captured invoice/payment/plan evidence
   before its real period start. Record one future hold and prove that early
   application, replay and unpaid status observations grant no access.
3. When that real start arrives, run the existing reviewed held-period command
   with the current subscription revision. Prove exact end date and six-member
   entitlements, one resolution, unchanged original financial evidence and
   idempotent replay without a second receipt.
4. Separately validate actual provider failure/Pending/Halted and paid recovery,
   including signed event delivery through the restricted callback. No new tunnel
   was needed for today's failed authorization; a fresh temporary callback is
   required for that event-delivery phase. If Test Mode cannot support it, document
   a reviewed alternative explicitly rather than marking the scenario passed.
5. Close commercial/live rollout gates independently, then obtain bounded pilot
   activation/first-collection approval. Until this alternative passes, the older
   October fixture remains a fallback, not the target we are deliberately waiting for.

## Mail verification and callback brief (2026-09-30)

Read the admin@rokkad.com Gmail results for `in:anywhere from:(razorpay.com)
after:2026/09/29`. Three matching threads; the latest received message was
**29 September, 22:17 IST**, with no 30 September message in these results.
[Ticket 21174094 correspondence](https://mail.google.com/mail/u/3/#search/in%3Aanywhere+from%3A(razorpay.com)+after%3A2026%2F09%2F29/FMfcgzQhWfTQdVcKGDJXmXbdbtxxSKML)
independently confirms the owner-supplied WhatsApp fee components below. The
22:10 reply says both technical tickets 21146138 and 21146171 are actively being
worked on; it supplies no technical resolution. The 22:17 reply attaches a pricing
PDF and requests callback availability or an alternate number within three days
to avoid auto-closure. No callback time is confirmed in this correspondence.
The older pricing ticket 21170392 has resolution notifications; that is not
evidence that the technical cases or remaining fee questions are resolved.

Call checklist:

1. **21174094, merchant-specific costs:** request itemized INR 1,499 first-payment
   and renewal examples for card, UPI AutoPay and eMandate, during and after the
   promotion. Reconcile the reviewed PDF's INR 17 auto-UPI row with the 2% method
   fee and 0.9% add-on; clarify fixed versus percentage eMandate charges, GST and
   setup credit coverage, failed/retry/minimum fees and promotion dates. Emails
   address "Hanumanram"; confirm that the quote belongs to Rokkad's merchant
   account under Rajesh Rathod H rather than assuming the salutation is harmless.
2. **21146171, monthly failure/recovery:** explain that selecting Charge as
   failure produced Captured/Paid evidence. Request reproducible Test Mode steps
   and expected events for failure, Pending, Halted and recovery, or written
   confirmation of a limitation and its supported alternative.
3. **21146138, annual completion:** request the reason for the preserved final
   Created payment/Issued invoice after Charge as Success and supported completion
   steps. Annual stays outside the initial monthly pilot.
4. **Earlier acceptance:** ask for a supported short Test Mode schedule and clear
   handling of provider period timestamps. The official
   [test guide](https://razorpay.com/docs/payments/subscriptions/test/) supports
   simulated charges before their due date and documents a three-day test card
   token lifetime for subsequent debits. That lifetime does not explain the
   historical failure by itself and must not be confused with validity of already
   captured payment evidence. Obtain answers in the support ticket after the call.

**Timing clarification:** 28 October is the start of the paid period in existing
monthly test evidence, not a Razorpay-imposed waiting period. Rokkad recorded the
future payment while holding its access effect. The remaining check applies that
held period when eligible, preserving exact dates and preventing duplicate access.
The current acceptance plan waits for those dates; a reviewed shorter test path
could replace this dependency once it actually passes. Simulating a charge alone
does not prove that access is applied at the right time. The earlier short scheduled
attempt expired without a paid cycle. JSK's 8 October trial expiry is independent:
it neither authorizes charging nor clears these gates. Any interim access treatment
requires its own explicit decision; no extension, early charge or live activation
was made during this review. Provider API statuses were not re-fetched today.

## Owner-supplied WhatsApp pricing reply (2026-09-29)

The owner pasted a response identifying ticket **21174094**. This is supplied
correspondence, not an independently inspected Dashboard response or verified
settlement. It requests a callback time/alternate number and a "Hi" reply. No
message, phone confirmation or callback commitment was sent by the agent.

The response clarifies the quoted components:

- Subscription add-on: **0.9%**, in addition to a quoted **2% payment-method fee**.
- **18% GST on all fees**, separate from the merchant's customer invoice tax.
- UPI AutoPay mandate: **INR 7 one-time**; UPI and recurring charges are separate.
- eMandate: **INR 22 setup**, **INR 20 automatic payment**, plus GST.
- The **INR 5 lakh amount-credit promotion covers only eligible payment-method
  charges**. Subscription charges still follow the pricing plan; some methods
  are excluded. This is not free subscription processing.

Working estimates for an INR 1,499 collection, calculated with Decimal and
rounding only at the final two-decimal result:

| Scenario | Formula | Estimated processor fees | Amount remaining after those fees |
| --- | --- | --- | --- |
| A collection subject only to the quoted 2% method fee + 0.9% add-on + GST | 1499 x (0.02 + 0.009) x 1.18 | INR 51.30 | INR 1,447.70 |
| Eligible promotional collection, **if** the 2% fee and associated tax are fully waived and only add-on plus its GST remains | 1499 x 0.009 x 1.18 | INR 15.92 | INR 1,483.08 |

The first scenario has a 3.422% combined cost. These are estimates before setup,
other method-specific fees or adjustments, not guaranteed bank settlements or
profit. Component-level provider rounding may differ by a paisa. The promotional
tax treatment remains an explicit assumption pending a worked settlement example.
Standalone GST-inclusive components are INR 8.26 for UPI mandate setup, INR 25.96
for eMandate setup and INR 23.60 for an eMandate automatic payment. Do not treat
these as all-in collection costs or apply the 2% scenario to every mandate route.

Remaining clarification: how the PDF's **INR 17 auto UPI** combines with the quoted
2% method fee and 0.9% add-on; which percentage fees apply to eMandate alongside
its fixed charges; first-payment versus renewal timing; promotion coverage of
setup charges and related GST; minimum/failed-debit/retry fees; applicable method
exceptions/effective date; and itemized first/renewal examples during/after credits.
The official [credits guide](https://razorpay.com/docs/payments/dashboard/account-settings/credits/)
supports treating amount credits as eligible payment volume, not cash or a fee
balance; account-specific subscription coverage comes from this support reply.

Prepared follow-up (not sent):

> Thank you. Please record these terms in ticket 21174094 and provide itemized
> INR 1,499 first-payment and renewal examples for card, UPI AutoPay and eMandate,
> during and after the promotion. Does the PDF's INR 17 auto-UPI fee replace or add
> to the 2% method fee and 0.9% subscription add-on? Which percentage fees apply
> alongside eMandate's INR 22 setup/INR 20 collection charges? Please show setup,
> GST, credit coverage and net settlement, and confirm any minimum, failed-debit
> or retry charges and the effective date.

The customer offer remains INR 1,499 with the confirmed unregistered seller/no-GST
invoice treatment. GST on Razorpay's services is a separate merchant cost; this
reply does not change the seller's registration status or customer invoice tax.
The public trial/landing copy and disabled paid-billing gates need no change.
Technical failure/recovery, naturally due held access and live pilot acceptance
remain separate. Fee clarity has improved; the fee gate is only partially closed.

## Cancellation wording review (2026-09-29)

The recurring owner page, `request_cancellation`/`process_cancellation`, published
cancellation/refund policy and approved customer summary agree on immediate mandate
cancellation, preserved verified paid time, no automatic refund and no restart of
the cancelled agreement. Provider confirmation, uncertain outcomes and payments
already in progress must remain explicit. The official
[cancellation reference](https://razorpay.com/docs/api/payments/subscriptions/cancel-subscription/)
was rechecked: immediate versus cycle-end cancellation are distinct, and a
cancelled agreement cannot be reactivated.

The local page now presents the existing uncertainty caveat **before** the owner
confirms cancellation and links the approved refund policy, whose seven/five
working-day review/initiation windows are unchanged. Previously those caveats
appeared only after requesting cancellation or ending the agreement. No service,
provider request, access policy, legal policy or refund entitlement changed.
Two existing focused tests passed: owner page/POST-only/CSRF boundaries and
completed-agreement paid-access/final-invoice behavior. Deploy this template in
the next reviewed billing release; it is not live yet. This completes the local
wording review, not provider failure/recovery or live cancellation acceptance.

At 20:48 IST the production onboarding/mail read-only check remains healthy:
one observed verified owner, one public trial, accepted invitation and two members;
queue due zero, no flags, four active/enabled timers and a successful natural
external heartbeat at 20:46:49 IST. Whether this is a genuine customer and the
teammate's actual browser/role workflow remain unconfirmed. Sanitized local proof:
`outputs/launch-operations-check-20260929.json`.

Support has no new answer: pricing 21174094 Active, annual 21146138 In Progress
with the prior follow-up still last, failure 21146171 Closed with no technical
reply. Do not submit duplicate tickets or retry the preserved payment attempts
just because the same checks have not changed. Next substantive billing step is
to assess written provider guidance/fees, then perform the applicable acceptance;
the naturally due monthly fixture is still scheduled for 28 October.

## Pricing support reply (2026-09-29, 19:55 IST)

The latest authenticated email is a pricing response to **21170392**. It confirms
that amount credits are valid for 90 days from credit assignment on UPI, credit
cards on UPI, domestic debit cards, domestic Visa/Mastercard/RuPay credit cards,
netbanking, wallets, Pay Later/BNPL and cardless EMI. Excluded methods are AMEX,
Diners, card EMI, prepaid cards, corporate/business cards and other international
cards. This confirms method-level promotion eligibility, not every recurring fee.

Support attached **Pricing Paln - Sheet1.pdf**, said the pricing ticket would be
resolved, and stated that technical issues in 21146138 and 21146171 are still being
investigated. It also asked for a suitable callback time after an unsuccessful
call; no time, alternate number or callback commitment was supplied by the agent.
The owner subsequently approved the focused clarification below. It was submitted
through Dashboard as **21174094**, referencing the original 21170392. The original
ticket is Resolved with no reply field, and its email Reply-To is the previously
unmonitored address. A new dashboard query was therefore used for the same approved
message, prefixed with the original ticket reference. The existing approved phone
was retained without editing. No email reply or callback commitment was sent.
Creation confirmation gives a **4-8 business-hour** status-update expectation and
says confirmation was mailed to admin@rokkad.com; that confirmation email was not
independently inspected. Local screenshot:
`outputs/razorpay-pricing-followup-created-20260929.png`. Refreshed support history
shows **21174094 Active**, the full submitted text and response target **1 October,
13:43**. [Open the follow-up](https://dashboard.razorpay.com/app/business-settings/ticket-support/rzpind/ThtjAzl9Tw4JyQ/merchant/conversation).

The owner saved the PDF locally after Chrome's extension UI blocked attachment
automation, including after dismissal. Its entire single page was text-extracted
and visually inspected. The table has no footnotes, effective date, merchant ID,
tax statement or explanation of duplicated labels. Its association with this
account comes from the support email, not a merchant identifier printed in the PDF.

Relevant entries, reproduced as listed components rather than all-in charges:

| PDF label | Listed rate | Interpretation still needed |
| --- | --- | --- |
| initial upi, INR 1,000 to INR 10,000,000 | INR 7 | What event triggers it and whether it includes the first debit/setup |
| auto upi, same band | INR 17 | Whether this replaces generic UPI 2% and whether a subscription add-on applies |
| upi / upi (credit) | 2% / 2.05% | Applicability to UPI Autopay versus ordinary UPI |
| card (two separate rows) | 2% and 0.90% | Conditions, recurring applicability, and whether these add or replace each other |
| nach initial / nach auto | INR 30 / INR 10 | Mapping to the enabled Subscriptions mandate method |
| aadhaar emandate initial / auto | INR 30 / INR 5 | Eligibility and whether additional fees apply |
| emandate initial / auto | INR 22 / INR 20 | Which mandate route and how these combine with add-on/tax |

INR 1,499 is unambiguously inside the quoted UPI band. The INR 17 component is
about 1.13% of that price; this is arithmetic only, not an established effective
processing rate. No row is explicitly labelled Subscriptions, no GST percentage
or tax inclusion is stated, and credit coverage of recurring setup/collections
is not explained. Do not set a subscription add-on to 0.90% merely because that
number appears on a second card row, or treat INR 1,482 as confirmed net proceeds.
The unregistered seller's no-GST customer invoice remains separate from tax that
the processor may apply to its fees.

Private original: owner's Downloads folder, `Pricing Paln - Sheet1.pdf`, 81,407
bytes; SHA-256 `5fa874a3f63817ee46b005bf90423981b635c82d885126ea7c5af1c710d99091`. Local visual proof:
`outputs/razorpay-pricing-page-1.png`. No private attachment is committed.

The linked official [Amount Credits guide](https://razorpay.com/docs/payments/dashboard/account-settings/credits#amount-credits)
describes credits as eligible payment volume rather than cash or a fee balance;
transactions exceeding the remaining credit incur fees on the entire payment.
Its broad EMI exclusion and the email's explicit cardless-EMI inclusion should not
be generalized into an unreviewed payment-method promise. The monthly pilot only
needs its actually enabled recurring methods confirmed.

GET-only verification at **20:36:48 IST** preserves earlier evidence: annual
Active/paid_count 1 of 2 with last payment Created/invoice Issued; failed-simulation
payment Captured/invoice Paid and cleaned-up agreement Cancelled/paid_count 2 of 3;
short scheduled fixture Expired/paid_count 0 and authorization payment Created.
Local billing/mail counts did not change. The reply supplies no new failure,
Pending/Halted, recovery or held-period procedure; those launch gates stay open.

Next: review the answer to 21174094 and update the launch fee assumptions only
from clarified written terms. Keep the INR 1,499 commercial offer and disabled
paid-billing gates unchanged. Technical acceptance remains separately pending.

### Approved clarification submitted as 21174094

Thank you for the 29 September response and Pricing Paln - Sheet1.pdf. We reviewed
the table and eligible payment methods. Please keep the pricing enquiry open until
these recurring-billing details are confirmed in writing for our INR 1,499/month
Rokkad Subscriptions offer:

1. For UPI Autopay, does the INR 7 "initial upi" row mean mandate setup, first
   collection, or both? Is each later INR 1,499 collection INR 17 "auto upi", and
   does that replace the generic 2% UPI fee or apply in addition to it?
2. What is the exact Subscriptions add-on? The PDF has separate "card" rows at
   2% and 0.90%; please explain their conditions and whether they are cumulative,
   alternative or unrelated to recurring billing.
3. For the enabled eMandate option, which initial/automatic pair applies: NACH
   INR 30/10, Aadhaar eMandate INR 30/5, or eMandate INR 22/20? Please confirm any
   minimum, setup, failed-debit or retry charges and when they are billed.
4. Are these prices inclusive or exclusive of GST, and what tax applies to each
   component? Does our 90-day/INR 5 lakh amount-credit promotion cover recurring
   Card/UPI Autopay/eMandate collections, the Subscriptions add-on, mandate setup
   and tax? Please confirm each component and its post-promotion rate.
5. Please provide a worked INR 1,499 first-payment and renewal example for each
   supported recurring method, showing total deductions and net settlement both
   during and after the promotion, and the schedule's effective date.

Please reply in this ticket so the commercial terms remain documented. Technical
Test Mode acceptance remains tracked separately under 21146138 and 21146171.
No callback time or alternate phone number is being requested in this follow-up.

## Read-only launch-gate refresh (2026-09-29, 19:25 IST)

Dashboard review found no new substantive answer: annual **21146138 In Progress**
still ends with the authorized 10:21 follow-up; failure **21146171 Closed** contains
no technical response; pricing **21170392 Active** has no fee answer and still
displays 1 October 11:14 AM as the target. No additional support message was sent.

Fresh Test Mode GETs at 13:55:53 UTC confirm the annual agreement remains Active,
paid_count 1/2, with its final payment Created and invoice Issued. The attempted
failure fixture is still Captured/Paid; its cleaned-up agreement is Cancelled,
paid_count 2/3. The earlier short scheduled fixture is Expired, paid_count 0, and
its INR 5 authorization payment remains Created. No local billing/mail records
changed during these reads. Do not retry a charge or substitute ticket closure
for failure/recovery or renewal acceptance.

Production read-only checks confirm zero live agreements, private Plan 2 at
INR 1,499 with six members and one live provider binding, and public Plan 3 at
zero price with 30 days/six members. Checkout and recurring remain disabled.
The [onboarding report](../implementation/onboarding-monitoring.md) is now deployed
to observe public signup/team progress independently of the paid pilot gates.

## Dashboard support routing and trial preparation (2026-09-29)

The 12:54 reply to the fee email is an automated **unmonitored mailbox** notice,
not pricing guidance. With the existing fee-message authorization and separately
approved contact confirmation, the same inquiry was submitted through Dashboard
Account related assistance / Pricing Enquiry. **Ticket 21170392** is Active; the
Dashboard displays a response target of **1 October, 11:14 AM**. No fee is confirmed.
Sent email alone must not be treated as a monitored support request.

Dashboard support history now confirms annual **21146138 In Progress**, with a
displayed response target of **29 September, 5:48 PM**. Failure **21146171 is Closed**;
its conversation shows the original report and closure notice but no technical
answer. The 10:21 annual follow-up already references that unresolved failure.
Do not mark either provider acceptance passed or repeat an uncertain charge.
Local screenshot: `outputs/razorpay-pricing-ticket-21170392-20260929.png`.

Invitation-only delivery is now enabled independently of billing. The owner selected
a **30-day public trial draft**, six total members, no card or automatic collection,
followed by INR 1,499/month only after explicit consent. Preparation and required
private-catalog isolation are recorded in [the trial plan](public-workspace-trial.md).
Trial activation, recurring authorization and checkout stay false; existing JSK
dates and subscriptions remain unchanged.

## Individual seller continuation and fee inquiry sent (2026-09-29)

The owner reconfirmed continuing under the existing personal-PAN merchant setup,
with possible future company and GST registration. Current invoice seller remains
**Rajesh Rathod H**, with the confirmed address and unregistered/no-GST treatment.
This already matches deployed configuration; no code or production changes are
needed. PAN is provider KYC information, not a replacement GSTIN or a new public
invoice field. Do not copy it into chat, source, logs or customer documents.
Future registered-seller support and transition are recorded as
[FW-020](future-work.md#fw-020-company-registration-and-gst-ready-seller-transition).

At **12:53 IST**, after explicit owner approval, the prepared fee inquiry below
was sent from **admin@rokkad.com** to the verified Razorpay support address
**rzr06py08emsp@razorpay.com**, with subject
**Rokkad — merchant-specific Subscription fees and promotion coverage**.
Gmail confirmed Message sent and displayed the sent recipient/content. The message
asks for subscription/method/setup fees, GST, promotion coverage and subsequent
rates, requesting routing to merchant pricing support if needed. It includes no
PAN, credentials or customer details. This confirms sending, not provider receipt,
ticket creation or agreed pricing. Screenshot evidence is local in
`outputs/razorpay-fee-inquiry-sent-20260929.png`.

The technical support thread was refreshed immediately before sending; it still
ends with the owner's authorized **10:21** follow-up, with no later technical reply.
No new charge, retry, refund or provider-state mutation was attempted. Evaluate
the eventual response before choosing any new acceptance procedure.

Google's remaining India tax-info request is separate from the credited INR 500.
Use the correct actual individual/unregistered profile where supported; do not
enter PAN into a GSTIN field or choose registered status to dismiss the notice.
If the existing profile requires a GSTIN, resolve its account classification with
Google rather than inventing one. No tax declaration was submitted. Google's
[payments guidance](https://support.google.com/paymentscenter/answer/7398224?hl=en)
distinguishes individual/business profiles and GSTIN requirements; it does not
establish this account's suitability without reviewing its actual form.

## Merchant methods, fees and inbox review (2026-09-29)

Read-only authenticated merchant review confirms **Cards Recurring** and **UPI
Autopay** Activated, and Netbanking mandate methods (eNACH, eSign and Paper NACH)
Activated. Subscriptions settings separately show **Card, UPI and eMandate Enabled**.
This establishes account configuration, not a successful collection or acceptance
of failure/recovery behavior. Fee Bearer is **You pay the fee**; the customer-pays
option is disabled and identified as incompatible with Subscriptions.

The dashboard displays 88 days and INR 5,00,000 of promotional credits remaining,
with zero used. This does not establish free recurring collections. The official
[Subscriptions page](https://razorpay.com/subscriptions/) advertises a limited-time
0.5% subscription add-on plus underlying platform fees and GST, while Razorpay's
[pricing article](https://razorpay.com/blog/?p=26027) lists 0.99% plus underlying
method fees and GST. [Offer terms](https://razorpay.com/terms/90-day-free-pg-offer/)
do not waive tax on platform fees. No account-specific recurring rate was found in
the inspected settings. **Exact merchant fees remain unconfirmed**; do not select
a public rate as the contracted rate or confuse processor GST with the seller's
confirmed zero-GST customer invoice.

After owner sign-in, Google Admin shows **Business Starter Active**, one assigned
license and a Flexible Plan. Paid service starts **10 October 2026** (11 days shown).
The initial review displayed a minimum INR 500 payment pending. The owner then
reported paying, and explicitly requested re-verification. Fresh read-only review
confirms **INR 500 credit, no balance due**, with the last manual payment dated
**29 September for INR 500**. The payment-pending notification has cleared, and both
Business Starter and the separate 100 GB storage add-on now show **Active**.
The initial payment requirement is complete. **India tax information is still
requested**; ongoing billing must remain funded, and the credit is not indefinite
mailbox coverage. No payment, tax submission, mail send or account-setting change
was performed by the agent. Automatic approval review had blocked an additional
Admin screenshot before the owner's new, explicit read-only re-verification request;
the subsequent payment-account and subscription status review succeeded.

Fee question sent with owner approval at 12:53 IST (see checkpoint above):

> Please confirm the fees applicable to our activated Rokkad SaaS Subscriptions
> account for an INR 1,499 monthly plan: subscription add-on, underlying card/UPI/
> eMandate charges, applicable GST, mandate setup charges, and whether the displayed
> 90-day/INR 5 lakh promotion covers each component. Please include the rates after
> the promotion and any minimum charges. We need our merchant-specific schedule;
> public product and pricing pages show different subscription add-on rates.

Next: complete the outstanding Google India tax information and maintain billing
continuity after the credited payment; obtain the exact merchant fee schedule and
resolve provider failure/recovery/held-period acceptance,
preserving pending attempts. JSK's trial ends **8 October at 23:39 IST** and must not
be shortened. Existing naturally due held fixtures start **28 October**; an earlier
acceptance path has not passed or been approved. No launch date is committed.
Actual live callback, first payment/invoice/receipt and settlement require the
separately approved named pilot. Annual remains unpublished; all charging/sending
gates remain paused. See the [current rollout](subscription-monetization-rollout.md).

## Receipt worker prepared without sending (2026-09-29)

At **12:30 IST**, the worker command gained tested receipt-only selection while the
persistent dispatcher stayed invitation-only and disabled. All 55 focused tests,
restricted preflight, record-preservation and supervised monitoring checks passed.
The first approved live receipt will use one explicit reviewed delivery ID and limit
one; no receipt exists yet, no email was sent, and no general queue is enabled.
See the [procedure](../implementation/platform-mail.md#receipt-only-preparation-2026-09-29).

The refreshed Razorpay support thread still ends with our 10:21 follow-up. This step
does not close actual live callback delivery or failure/recovery/held-period
acceptance. Next independent review: merchant subscription methods/fees and monitored
inbox continuity. Preserve JSK's 8 October trial, annual exclusion and the separate
named pilot/first collection approval.

## Live runtime and webhook registration verified (2026-09-29)

The owner appointed **admin@rokkad.com**, verified existing user **9**, as permanent
platform administrator. Its audited staff/superuser grant preserves sign-in,
Workspace memberships and ownership. Temporary catalog operator 10 stays disabled.

At **12:15 IST**, web and workers consistently use live credentials and a separate
webhook secret, with all checkout/trial/recurring/sending gates false. Read-only
configuration/evidence checks pass, no billing record changed, and all existing
trials/private catalogs are preserved. Signed malformed-body HTTPS diagnostics
verify the callback's HMAC boundary without creating fake billing evidence.

The owner submitted the secret. Live webhook **ThlAT5rGIawXNH**, created at
12:20:44 IST, is Enabled with the canonical callback, admin failure alerts and
the exact 14 supported events. At 12:22 IST, unchanged billing fingerprints and
zero stored webhook events confirm registration has not yet demonstrated actual
provider delivery. Next: review receipt dispatch scope/monitoring and remaining
provider delivery acceptance. Provider failure/recovery/held-period
acceptance, JSK's unexpired trial and final activation approval remain outstanding.
No live collection is authorized. See the
[runtime evidence](../implementation/billing-provider-readiness.md#permanent-admin-and-live-webhook-runtime-2026-09-29).

## Live monthly catalog prepared (2026-09-29)

Live keys were generated by the owner, encrypted locally and staged root-only on
the server. GET authentication and the catalog contract passed. Provider plan
`plan_ThkgxD2zC0o8FL` is monthly interval one, INR 1,499 with zero GST; local Plan
**2** and immutable live binding **1** freeze the six-member offer and confirmed
seller. The owner-approved temporary catalog operator **10** is now inactive with
admin flags removed and no usable password. No existing account was elevated.

Shared trial Plan 1 and all existing subscriptions/access remain unchanged. Non-seat
internal values retain the existing plan values; the stored working annual price
has no annual binding or public purchase path. Twelve monthly collections remain
prepared future agreement terms. **No mandate, invoice, payment or charge exists.**
Final checks at 11:58 IST verify private catalogs for all operating Workspaces and
paused sending. Live keys are not loaded by persistent services; provider mode and
all purchase gates remain disabled. Next: signed live webhook/runtime configuration
and receipt-worker scope, with provider acceptance and JSK eligibility still required.
See [evidence](../implementation/billing-provider-readiness.md#live-keys-and-bound-monthly-catalog-2026-09-29).

## Seller configuration checkpoint (2026-09-29)

Confirmed seller name/address, unregistered status and zero tax are now configured
in the shared production web/worker environment. Restricted preflight and final
checks at **11:45 IST** preserve all billing records, JSK's trial/full access and
the private catalog. Unsaved monthly terms validate 149900 paise, zero GST and six
members; 12 collections/quantity one remain prepared. No plan/binding/agreement
was saved. All provider/purchase/trial/recurring/sending gates stay paused.

The owner confirmed live keys are not generated. The Live Mode Generate Key page
is ready for owner handoff. Complete protected key setup before provider plan
verification/binding; do not put secrets in the repository or chat. No real
collection is authorized. See the
[configuration evidence](../implementation/billing-provider-readiness.md#confirmed-seller-configuration-2026-09-29).

## Support resolution verification (2026-09-29)

Razorpay's 28 September 17:37 IST response marks **21146138** Resolved, cites the
annual subscription's Active state and recommends Live Mode validation. Its 17:43
notice provides four days to reply before closure. Neither final-payment settlement,
Test Mode AFA nor Completed transition is explained. The same Gmail thread contains
the **21146171** acknowledgement, but no specific failed-renewal simulation answer.

GET-only verification at **29 September 10:18:37 IST**:

| Evidence | Fresh result |
| --- | --- |
| Annual `sub_ThBL2wVYJZadDN` | Active; paid_count 1 / total_count 2 |
| Annual `pay_ThBR0fQ4nwVW3p` / `inv_ThBQyvwJjIJcQ0` | Created, INR 17,688.20 / Issued |
| Failure simulation `pay_ThAr4L7xHUiRqA` / `inv_ThAr2YPIv75AY9` | Captured, INR 1,768.82 / Paid |
| Failure fixture `sub_ThAoDxk8SOoSIP` | Previously Cancelled; paid_count 2 / total_count 3 |
| Scheduled `sub_ThM7GiBY7yxoHg` / `pay_ThM8vfcR0fWZik` | Expired, zero paid / Created, INR 5 |

All six checked local financial/mail record counts remain unchanged. No charge,
refund, cancellation, release or reconciliation write was performed. Annual stays
outside the monthly pilot, but applicable failure/recovery and held-period
acceptance remain open. Support's Live Mode recommendation is not payment consent
or evidence that these outcomes passed.

The owner explicitly authorized the exact-ID follow-up. It was sent from
admin@rokkad.com to the verified support address in the existing thread at
**10:21 IST**; Gmail confirms Message sent and displays the complete reply. It
requests renewed investigation, specific guidance or written confirmation of Test
Mode limitations. Provider-side reopening is not independently verified yet.
Next: assess the technical reply against exact provider evidence. Keep paused
live seller/catalog preparation separate from activation; preserve JSK's trial.
Private evidence: `outputs/billing-support-verification-20260929.json`;
sent text: `outputs/razorpay-followup-20260929.txt`; screenshot:
`outputs/razorpay-followup-sent-20260929.png`. No live key, production configuration
or payment changed at this checkpoint.

## Confirmed JSK pilot review (2026-09-28)

The owner confirmed the invoice seller **Rajesh Rathod H**, no GST registration,
and the billing address below. The owner selected **12 monthly collections** and
**JSK** as the first pilot. These decisions prepare the offer; no charge or trial
conversion is authorized. Registration applicability remains a separate business
responsibility; the app records the owner's stated registration status.

At **15:50 IST**, a restricted, repeatable-read, read-only production transaction
resolved `jsk` to Workspace **2**, canonical active owner **1**, and subscription
**2**. Its existing billing email matches the owner. The private owner email is in
the local review evidence, not this published project record. JSK has **3 members**,
**0 pending invitations**, Active lifecycle and full commercial access. There are
no open agreements, outstanding invoices or legacy mandate IDs.

JSK has an unexpired trial ending **8 October 2026 at 23:39:08 IST**
(`2026-10-08T18:09:08.926934Z`). Immediate recurring creation rejects unexpired
trials. Preserve that trial and its access; do not edit dates/status to pass the
guard. Scheduled live conversion is unsupported. Recheck eligibility after the
trial naturally ends and after other acceptance is complete; this is not a launch
date. The separate `end_date` field on this trial is not evidence of paid access.
Naturally due held-period acceptance still remains open, with the existing monthly
fixture beginning on 28 October.

An unsaved preview using the confirmed seller and the live offer-validation path
produced **149900 paise**, zero GST, and six total members. It executed **zero
database queries and zero provider requests**. The duration is 12 cycles with
quantity 1: one Workspace subscription, not six separately charged seats. No
upfront add-on or new trial is proposed. The preview's extra-user price is zero;
additional seats require a separate reviewed offer, not automatic overage billing.

The prepared customer summary is:

> Rokkad Workspace subscription for JSK: INR 1,499 per month, including the owner
> and up to five staff. GST is not charged because the supplier is not registered
> under GST. Up to 12 monthly collections, beginning only after a separately
> approved owner authorization when the Workspace is eligible. You may cancel
> future renewals; already verified paid time remains available. Cancellation does
> not itself request a refund. After the final collection, a replacement agreement
> requires separate preparation and authorization.

Rokkad sends immediate mandate cancellation (`cancel_at_cycle_end=false`) while
preserving verified paid access. An uncertain cancellation stays pending until
provider reconciliation; do not promise an already in-flight collection cannot
settle. The existing refund policy's seven/five working-day review/initiation
windows remain. Provider parameter meanings were rechecked against the official
[creation](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/)
and [cancellation](https://razorpay.com/docs/api/payments/subscriptions/cancel-subscription/)
references. The customer summary is an unpublished draft.

### Catalog review before saving

The publication fix is deployed as `rokkad:billing-paused-99bda8c1cb27`. When
checkout and trial signup are false, active plans are hidden from the generic
catalog; owners use their prepared recurring agreement's frozen monthly terms.
Live catalog review/binding requires trial signup paused too. Legacy feature and
estimated overage claims are removed from the catalog/dashboard; stored terms and
existing invoices are preserved. See the
[decision](../adr/2026-09-28-private-operator-billing-catalog.md).

Do not edit the existing plan shared by the three trial Workspaces. Prepare a
separate reviewed monthly plan. Nine non-seat entitlement defaults remain in the
model: five disabled legacy feature flags, 100 products, one warehouse, 500 monthly
transactions and 500 monthly invoices. These are internal inherited values, not
accepted new product limits or claims about supported app functionality.

Before this fix, the generic plan page advertised monthly operations and legacy feature
flags, and shows an annual price when present. `Plan.save()` fills an empty annual
price. Therefore saving an active pilot plan can expose unreviewed annual/feature
copy even with purchases disabled. The deployed fix permits private preparation;
keep both self-service switches false. A monthly binding alone does not restrict
the generic self-service catalog when it is enabled. No plan or binding was saved.

The exact live-catalog preview command is already documented in the
[configuration runbook](../implementation/billing-provider-readiness.md#live-catalog-preparation-2026-09-28).
It requires reviewed seller settings, protected live credentials, an existing live
provider plan and an authorized platform actor, with checkout, trial and recurring flags
false. Do not execute agreement creation during catalog preparation: it requires
the separate recurring activation gate and JSK transition eligibility.

Private local evidence: `outputs/jsk-pilot-review-20260928.json`,
`outputs/confirmed-pilot-preview-20260928.json` and
`outputs/billing-pilot-review-pending-20260928.json`. Production configuration and
all financial/access records were unchanged.

## Selected scope and seller details

| Item | Preparation value / status |
| --- | --- |
| Seller name | **Rajesh Rathod H**, supplied by the owner for invoices |
| Brand | Rokkad |
| Account basis | Owner says personal PAN; no PAN number requested or recorded |
| GST position | Owner explicitly confirmed not GST-registered on 28 September; no GSTIN supplied. Account configuration does not determine registration obligations. |
| Billing unit | One Workspace |
| Monthly working price | INR 1,499.00 |
| Draft collection | INR 1,499.00, **149900 paise**, no GST collected under the confirmed unregistered-supplier treatment |
| Duration | Owner selected up to **12 monthly collections**, quantity 1 |
| Pilot | JSK (`jsk`, Workspace 2); canonical owner verified; existing trial must be preserved |
| Capacity | Owner plus five staff, six total members; existing invitation reservation rules apply |
| Preparation | Operator prepares the agreement; the Workspace owner separately authorizes it |
| Start | Immediate only; no scheduled live conversion |
| Annual | Outside this pilot; INR 14,990 remains an unpublished working price |
| Add-ons | No automatic overages, paid messaging, onboarding fees or extra support charges approved |
| Existing customers | Preserve current plans, trials, access grants and financial history; no silent conversion |

The owner confirmed the seller billing address: 11, 9th Cross
Street, Rajiv Gandhi Nagar, Vellore, Tamil Nadu, India.
Billing replies use `billing@rokkad.com`;
general support uses `support@rokkad.com`.

For an unregistered supplier, prepare an ordinary commercial **Invoice** identifying
Rajesh Rathod H / Rokkad, the monthly software subscription, period, buyer,
reference/date and INR 1,499 total. For the confirmed status, use “GST not
charged — supplier not registered under GST.” Do not describe an exempt or
zero-rated GST supply, invent a GSTIN, or print personal PAN. Section 32 prohibits
GST collection by an unregistered person; registration applicability is separate.
[CBIC Act, section 32](https://cbic-gst.gov.in/hindi/CGST-bill-e.html),
[CBIC commercial-invoice guidance](https://cbic-gst.gov.in/sectoral-faq.html).

## Verified preparation and implementation gaps

At **15:19 IST**, the existing offer builder was exercised with an unsaved monthly
plan, INR 1,499, six members and process-only zero-tax override in the isolated
restricted database under a read-only transaction. It produced **149900 paise**
and INR 0.00 tax. No plan was saved, provider called or production setting changed;
existing frozen bindings and invoice count were unchanged. Other model-default
feature limits were not accepted as commercial terms.

Source review identified the following gaps, now addressed by the deployed
[frozen-seller implementation](../implementation/billing-provider-readiness.md#frozen-seller-and-explicit-tax-settings-2026-09-28).
Production deployment and owner confirmation of seller facts are complete:

1. Base billing settings now have an empty tax default and require explicit
   reviewed live seller/tax configuration. Preserve rehearsal values and old frozen
   invoices/bindings; never recalculate their history using new settings.
2. New live evidence freezes issuer/tax treatment. HTML/PDF invoices and receipts
   render it consistently, preserving historical invoices without seller snapshots.
   Configuration changes do not rewrite issued evidence.
3. Checkout and authorization now show the same seller/no-GST treatment. New live
   authorization requires a current reviewed seller; existing recovery is unaffected.
4. Enforce monthly scope through a monthly binding and controlled agreement
   preparation with one-off checkout paused. Empty `yearly_price` is insufficient:
   `Plan.save()` currently auto-populates it. Do not expose annual purchases or
   silently alter existing catalogs.

Zero-GST and historical-snapshot regressions are included. The invoice/configuration
change is deployed to web and mail workers as `rokkad:billing-paused-60c7beeb8191`
with billing/sending paused. No migration or record changes; seller fields remain
unconfigured. See the [deployment evidence](../implementation/billing-paused-release-20260928.md#seller-invoice-update-deployed-2026-09-28).

## Provider checkpoint

GET-only observations at **15:16 IST on 28 September**:

Repeated at **15:49 IST** with the same provider statuses and unchanged local
financial/mail record counts. The support inbox was not rechecked during this
later API observation; its acknowledgement-only entry below remains the 15:16
checkpoint.

| Fixture | Observation | Consequence |
| --- | --- | --- |
| Annual `sub_ThBL2wVYJZadDN` | Active, one of two paid; final `pay_ThBR0fQ4nwVW3p` Created, invoice `inv_ThBQyvwJjIJcQ0` Issued | Preserve attempt; annual renewal remains unaccepted and outside pilot |
| Scheduled `sub_ThM7GiBY7yxoHg` | Expired, zero paid; authorization `pay_ThM8vfcR0fWZik` Created (INR 5) | Preserve token/reservation; naturally due held access remains unproved |
| Tickets 21146138 / 21146171 | Refreshed inbox search has only 11:49/11:50 acknowledgements | No technical resolution received or additional message sent |

The Test Mode support-history page shows no queries; submitted ticket IDs and
email acknowledgements remain submission evidence. No repeated charge, cancellation,
refund or release. Local invoice/payment/cycle/agreement-event/delivery/attempt
counts were unchanged.

Monthly-only selection defers annual launch; it does **not** waive failed-collection,
recovery, held-period or other applicable acceptance. Actual monthly holds still
start **28 October 2026**; this scope selection alone does not permit an earlier
launch. [Razorpay Test Mode behavior](https://razorpay.com/docs/payments/subscriptions/test/).

## Remaining decisions and activation sequence

1. Seller registration status/address, 12-cycle duration and JSK selection are
   confirmed, and the catalog fix is deployed paused. Review final feature terms and registration
   applicability independently. Retain the current trial and recheck JSK's eligibility
   when it naturally ends; do not shorten it or schedule an unsupported live start.
2. Use `total_count=12`, quantity 1 after eligibility and activation approval. This
   does not collect twelve months upfront. Rokkad requires explicit duration;
   Razorpay documents bounded [subscription creation](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/).
3. Seller configuration is complete; applicable provider acceptance remains open. Retain
   published refund review/initiation windows of seven/five working days; review
   cancellation wording before activation.
4. Live Card/UPI/eMandate are enabled. The owner accepts fee uncertainty; reconcile
   actual deductions after the first approved payment instead of blocking launch
   on exact fee clarification. Live keys and the
   separate webhook secret are protected on the server; provider registration and
   HTTPS/HMAC diagnostics are complete. Actual provider event delivery/recovery
   acceptance remains open, with purchases paused.
5. The reviewed monthly provider plan is bound to separate Plan 2 / live binding 1.
   Keep one-off checkout false and annual unpublished; never reuse test plan IDs.
   Recurring authorization remains false until bounded activation is approved.
6. Receipt-only command preparation is complete; the persistent worker remains
   invitation-only and paused. Use one reviewed delivery ID/limit one for the first
   separately approved receipt. Keep feedback/recovery/health and confirm monitored
   inbox continuity: INR 500 is credited with no balance due; India tax info remains
   requested, and paid service starts 10 October. Never enable the queue indiscriminately.
7. Authorize the named pilot and first collection; observe invoice, payment, access
   and receipt, then verify settlement and later renewal/recovery.

No production date is committed. Sanitized local evidence:
`outputs/billing-pending-current-20260928.json` and
`outputs/monthly-pilot-preview-20260928.json`. Credentials and personal PAN data
do not belong in the repository.
