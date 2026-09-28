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

## Selected scope and seller details

| Item | Preparation value / status |
| --- | --- |
| Seller name | **Rajesh Rathod H**, supplied by the owner for invoices |
| Brand | Rokkad |
| Account basis | Owner says personal PAN; no PAN number requested or recorded |
| GST position | Replies indicate no GST registration; no GSTIN supplied. Razorpay GST settings show addition unsupported for this business type and refer to a non-individual account for GST linking. Account configuration does not determine registration obligations. |
| Billing unit | One Workspace |
| Monthly working price | INR 1,499.00 |
| Draft collection | INR 1,499.00, **149900 paise**, no GST collected, subject to confirming unregistered-supplier treatment before activation |
| Capacity | Owner plus five staff, six total members; existing invitation reservation rules apply |
| Preparation | Operator prepares the agreement; the Workspace owner separately authorizes it |
| Start | Immediate only; no scheduled live conversion |
| Annual | Outside this pilot; INR 14,990 remains an unpublished working price |
| Add-ons | No automatic overages, paid messaging, onboarding fees or extra support charges approved |
| Existing customers | Preserve current plans, trials, access grants and financial history; no silent conversion |

Use the approved public address as the **draft** seller address: 11, 9th Cross
Street, Rajiv Gandhi Nagar, Vellore, Tamil Nadu, India. Confirm its suitability as
the billing address before publication. Billing replies use `billing@rokkad.com`;
general support uses `support@rokkad.com`.

For an unregistered supplier, prepare an ordinary commercial **Invoice** identifying
Rajesh Rathod H / Rokkad, the monthly software subscription, period, buyer,
reference/date and INR 1,499 total. Once that status is confirmed, use “GST not
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

Source review identified the following gaps, now addressed locally by the
[frozen-seller implementation](../implementation/billing-provider-readiness.md#frozen-seller-and-explicit-tax-settings-2026-09-28).
Production deployment and final seller/tax review remain pending:

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

1. Confirm unregistered-supplier treatment and billing address; review registration
   applicability. Confirm final feature limits and a named pilot Workspace/owner.
2. Select mandate duration. Proposal for review: at most **12 monthly collections**,
   cancellable for future collections, without collecting twelve months upfront.
   This duration is unapproved. Rokkad requires explicit `total_count`; Razorpay
   documents bounded [subscription creation](https://razorpay.com/docs/api/payments/subscriptions/create-subscription/).
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
