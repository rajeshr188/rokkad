---
status: preparation
owner: project
updated: 2026-09-29
tags: [billing, pilot, commercial, razorpay]
related: [subscription-monetization-rollout.md, ../implementation/billing-provider-readiness.md]
---

# Monthly billing pilot

The owner selected preparation of a monthly-only, operator-prepared paying pilot
on 28 September 2026. This unpublished offer does not authorize charging.
Production billing and mail dispatch remain disabled.

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
4. Live Card/UPI/eMandate are enabled; confirm the exact merchant fees described
   in the review above. Live keys and the
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
