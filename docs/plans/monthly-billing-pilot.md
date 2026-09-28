---
status: preparation
owner: project
updated: 2026-09-28
tags: [billing, pilot, commercial, razorpay]
related: [subscription-monetization-rollout.md, ../implementation/billing-provider-readiness.md]
---

# Monthly billing pilot

The owner selected preparation of a monthly-only, operator-prepared paying pilot
on 28 September 2026. This unpublished offer does not authorize charging.
Production billing and mail dispatch remain disabled.

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
3. Complete reviewed seller configuration and applicable provider acceptance. Retain
   published refund review/initiation windows of seven/five working days; review
   cancellation wording before activation.
4. Verify live subscription methods/fees for this merchant. Protect live keys on
   the server; prepare a mode-specific webhook secret and accept signed HTTPS
   callback/recovery with purchases paused. No live keys were generated/read/moved
   during this checkpoint.
5. Prepare only the reviewed monthly live plan, preview its exact terms, then bind.
   Keep one-off checkout false; never reuse test plan IDs. Recurring authorization
   remains false until bounded activation is approved.
6. Review receipt dispatch separately: the persistent worker is invitation-only.
   Keep feedback/recovery/health, agree monitored receipt scope and confirm inbox
   continuity. Never enable the queue indiscriminately.
7. Authorize the named pilot and first collection; observe invoice, payment, access
   and receipt, then verify settlement and later renewal/recovery.

No production date is committed. Sanitized local evidence:
`outputs/billing-pending-current-20260928.json` and
`outputs/monthly-pilot-preview-20260928.json`. Credentials and personal PAN data
do not belong in the repository.
