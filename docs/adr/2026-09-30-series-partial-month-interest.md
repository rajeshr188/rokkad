---
status: accepted
owner: loans
updated: 2026-09-30
tags: [loans, interest, policy, series]
related: [2026-08-09-loans-effective-dated-calculation-policy.md, 2026-09-25-same-day-economic-policy-revisions.md]
---

# Series calculation policies and partial-month charging

The owner chose a minimum full first month, followed by selectable full-month,
half-month slab, started-week or actual-day charging. JSK WH is to use started
weeks. This is a new-origination policy change, not permission to rewrite loans.

## Decision

- Extend the existing economic-policy table with optional series scope. Resolve
  series, then license, then Workspace; all rows remain effective-dated revisions.
  A series row must match its Workspace and license. Setup saves its complete
  calculation policy and metal rates atomically, with actor audit.
- New setup revisions freeze `minimum_first_month=True`. First-period charge is
  one whole month even at early closure, independently of upfront collection.
  Subsequent partial periods use FULL_MONTH, SLAB, STARTED_WEEKS or ACTUAL_DAYS.
- Started weeks use `min(ceil(elapsed_days / 7) * 7, period_days) / period_days`.
  Actual days use `elapsed_days / period_days`. Elapsed days are inclusive and
  period length is the actual monthly period built by the existing calendar
  addition/clamping rule. Completed periods always use fraction 1.
- Retain monthly period-opening principal bases and existing capitalization,
  repayment, renewal, release and advance-consumption workflows. Daily proration
  does not introduce daily reducing balances or a daily repayment schedule.
- New minimum-first-month snapshots normalize trailing zeros in the saved
  currency quantum before calculation: numeric 0.0100 means paise. Historic
  snapshots keep their prior precision behavior; this release does not reprice
  them. Exact computed fractions remain in immutable event evidence; the existing
  accrual-row fraction is a four-decimal projection.
- Existing policy rows/snapshots receive False; missing keys in old approval
  payloads also mean False. Approval, disbursal and renewal freeze the new flag.
  Imported openings retain their separate reviewed source rules.
- `loan-history/1` gains an optional boolean with omission retaining the previous
  meaning. Its bounded fraction representation cannot restore weekly/daily
  calculations exactly, so exports of those loans fail explicitly. Do not claim
  a wider restore contract; full backups retain all evidence.

## Deployment

Migration 0032 adds columns and adjusts scope uniqueness on existing forced-RLS
tables. No table or ownership boundary is added. Verify old evidence preservation,
runtime RLS, the four charging tables, month ends/leap years, setup, approval,
advance consumption, release/idempotence and legacy import behavior. Append only
the reviewed WH revision, retaining its existing rates, LTV and other rules.
Once new-policy loans exist, roll forward; an old application cannot service the
new methods safely. Do not reverse schema while series revisions are retained.
