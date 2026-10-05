---
status: active
owner: loans
updated: 2026-10-05
tags: [loans, portability, contract, interest]
---

# loan-history/3

Two UTF-8 JSONL lines: manifest, then one loan. The authoritative shape is
[the v3 schema](loan-history-v3.schema.json); the
[weekly example](examples/loan-history-weekly-v3.jsonl) contains the corrected
inclusive calendar. Import uses the existing Data tools preview and confirmation.
Old v1/v2 files retain their exact meaning and remain readable.

V3 requires frozen policy version 2. Period one covers the original date through
its first anniversary; later periods start the next day. Short months clamp each
anniversary independently. A 5 April loan with month one paid upfront has no new
charge through 5 May and its next charge starts 6 May. The first inclusive period
can contain 32 days. Actual-day, started-week, slab and full-month fractions retain
their saved product convention against these corrected period bounds.

Interest is HALF_UP per item per period at the saved policy quantum, supporting
paise or whole rupees. Principal, fees and cash retain paise precision. Original
principal is the first-period basis; later bases use balances through the day
before the new charge starts. Advance coverage is applied once. Exact raw amounts,
fractions, item lines, event balances and release catch-up must reconcile.

V3 extends the existing supported full-history scope; it does not admit renewals,
auctions, reversals, concessions or fabricated pre-cutover history. Reviewed opening
positions use their separate opening evidence contract. Import does not reapprove
the original lending decision. Destination mapping, authorization, immutable batch
profile/result binding, tenant isolation and whole-history atomic confirmation remain.

Migration 0018 enables staging v3 under the existing immutable batch guard. Do not
downgrade software to readers that cannot interpret v3 after writing v3 evidence;
stop new writes and retain compatible readers instead. Its reverse migration refuses
while v3 batches exist. Existing borrowers and financial rows are never automatically
converted by this migration.
