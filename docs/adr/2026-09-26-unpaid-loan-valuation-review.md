---
status: accepted
owner: loans
updated: 2026-09-26
tags: [loans, approval, valuation, audit]
---

# Guided valuation review before cash payment

An approved loan may outlive its quote's current-day eligibility. The owner
approved a guided comparison and reapproval flow for cash **not yet paid**.
The earlier-payout path continues to record actual historical payments.

## Decision

Provide Review updated valuation on stale native, itemized approvals without
financial events. Surface it in Recommended next step and on the disbursal
screen before ordinary payout confirmation. A signed-in workspace viewer may
read the comparison; changing the approval requires both `data.edit` and
`loan.approve`, plus current writable-workspace access. No new permission or
subscription exception is introduced.

Show the frozen approval beside today's quote dates/prices, item values and LTV
limits, interest rates, policy terms, fees and net payout. Principal, collateral
identity, photos and number stay the same. Missing quotes or excessive LTV block
reapproval and provide a correction route. Do not automatically reduce principal
or relax LTV. A comparison failure can leave current totals unvalidated; show
the explicit blocker rather than inventing proposed amounts.

Confirmation explicitly attests cash has not been paid and accepts today's loan
date and shown terms. A service locks workspace and loan, rechecks a signed
actor/workspace/loan/date/input/quote/policy fingerprint, then atomically returns
to draft, resaves the same collateral with today's policy, and adds an approval.
Use existing lifecycle, edit, eligibility, appraisal and audit services.
Failure rolls the entire transition back to its original approved state.

The new immutable approval stores a valuation-review marker linking its prior
approval, original date, review digest and actor. A repeated or concurrent
confirmation recovers that result without another approval or any payment.
Current authorization is checked before replay. Invalid/expired (one hour) or
changed reviews must be refreshed. No new database table or migration is needed.

Reapproval never disburses. An authorized cashier proceeds to the existing
disbursal screen, checks/prints the updated ticket and records payment separately.
This preserves separation between approvers and cashiers. Old approvals and
issued PDF bytes remain historical evidence.

This flow excludes loans with financial events and historical approval markers.
Cash already paid must retain its actual date and evidence. Approved earlier
payouts currently require a reasoned Return to draft before Record an earlier
payout; this change explains that route but does not silently enter it or record
any production payout during deployment.

## Verification

Cover read-only comparisons, price/policy/date drift, missing/low quotes,
confirmation and rollback, number/photo/history preservation, unpaid attestation,
actor/workspace/current permission enforcement, restricted-runtime execution,
replay including after later disbursal, concurrency and UI discovery.
