---
status: accepted
owner: project
updated: 2026-10-05
tags: [adr, loans, servicing, coverage, recovery]
---

# Supported servicing and explicit future capture

The owner authorized LD-06 and explicitly selected an optional per-loan choice:
"From now on, every transaction for this loan will be entered directly in Rokkad."
This follows the accepted unified admission/continuation direction. One PawnLoan,
its original agreement, financial events, items and custody remain canonical.

## Decision

Renewal and auction use the common factual servicing prerequisites: supported frozen
contract, active lifecycle, effective date, cutover and later financial/accrual/custody
dependencies. Existing authorization, loan locks, current successor approval,
statutory notice service, physical verification and exact retry rules remain owned
by their existing commands. Eligibility is an inventory, never posting authority.
Opening renewal preview already adds the unposted catch-up to recorded debt;
characterize that behavior rather than add another amount or replace its formula.

Reviewed collection openings can use current auction recovery through a dedicated
`opening-auctions/1` evidence extension. It freezes opening ID, baseline/checkpoint,
actual recovery and coupled recognition under the original anniversary contract.
The existing full settlement catch-up writer is reused. Recovery must clear the
whole known principal, interest and fees; shortfalls and surplus distribution remain
unsupported. Statutory evidence and in-vault custody remain mandatory. Reverse
recovery and its catch-up together, restore obligations and custody, then resume
continuation. Never reverse the opening or its catch-up independently.

Correction reviews reuse existing compensation/replay commands. A shared dated
dependency inventory includes immutable money events, accrual periods and custody
movements. Signed recorded receipt corrections bind this inventory alongside the
existing financial/linked-successor state. Unsupported graphs remain explicit
blockers; no accepted event or issued PDF is rewritten.

## Coverage and future capture

Reuse immutable Workspace-owned LoanTransactionReview. Add a future-capture choice,
reviewed state, last accepted event ID and a separate agreement/collateral binding
hash. No new servicing or capture table is needed. Existing reviews default to
PAPER_MIXED; origins never automatically select ROKKAD_ONLY.

A signed, actor-bound review may select ROKKAD_ONLY only for an active supported
loan, with complete records checked through today. An opening review starts at the
verified cutover, retaining unavailable earlier history. The selected prefix and
agreement stay exact. Subsequent supported current receipts, recognition, settlement,
renewal, auction and their supported reversals may maintain coverage through later
dates. Current native recognition of already eligible interest under its frozen
policy can have an earlier period date: derived recognition is not an unseen paper
cash transaction. The existing recognition writer and accrual evidence validate it.

Completed paper entry, historical compensation/replay, changed agreed terms,
unrecognized event graphs or reversals crossing the reviewed prefix suspend that
claim until another review. A fresh review defaults to PAPER_MIXED unless staff
explicitly select ROKKAD_ONLY again. Bulk book checks remain checks only. This
selection grants no new financial operation, retrospective approval or permission.

Current risk still needs dated eligible valuation and fresh snapshots, separately
from complete transaction coverage. Original valuation may remain unknown. Known
portfolio totals disclose provisional/unavailable loans; future-capture selection
changes coverage expectations, never the financial formula, maturity or quote age.

## Notices and portability

A notice retains both the original checked-source fingerprint and the current
financial fingerprint. Send-time locks and checks reject changed debt, changed
review, a different reporting date, stale risk, contact/consent/template changes or
provider unavailability. A continuing capture review can support a replacement
notice for a changed current position. The immutable notice intent uniqueness and
request key include that financial fingerprint; same-position duplicates still
fail. Ordinary notices without a transaction review keep their original uniqueness.

Old published portable wires keep their semantics. Auction/statutory graphs and
future-capture evidence need the wider LD-07 profiles. Existing per-loan exporters
explicitly refuse these graphs; they do not omit the new facts or claim a complete
restore. Exact Workspace recovery includes the existing review/auction/statutory
models, all new fields, file bytes and guard/schema fingerprints. Older recovery
archives still require their matching schema rather than silent field conversion.

Migration 0060 is additive: no new table, no tenant ownership or RLS change. It
preserves immutable reviews, validates capture checkpoints/parent Workspace binding
and strengthens position-specific reviewed notice uniqueness. Downgrade refuses
retained capture choices or multiple position-specific intents. Only disposable QA
is authorized here; application/candidate/production rollout remains separate.
