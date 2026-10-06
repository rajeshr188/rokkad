---
status: accepted
owner: loans
updated: 2026-10-06
tags: [loans, rates, origination, evidence]
---

# Configurable quote age for prospective lending

The owner selected the latest applicable quote, with a maximum age of seven days
by default and configuration by the Workspace owner. LC-06 supersedes the
same-day quote-age requirement for **new prospective approvals** in the
[September decision](2026-09-12-origination-quote-freshness.md). It preserves that
decision's quote identities, correction/replacement checks and frozen economics.

## Decision

- Extend the existing Loans-owned `LoanOriginationSettings` record. Missing rows
  and existing rows receive a seven-day default. Owners change the limit under
  **Loans setup → Loan entry**. Administrators retain photo administration and
  read access to the limit; only canonical owners, or the existing platform
  administrator override, can change it. Writes retain business-write, Workspace
  context and preference-audit checks. Zero requires an effective quote today.
  The storage range is 0–32767 whole days, not an unlimited-age option.
- Age is the difference between local calendar dates of evaluation and quote
  effectiveness. The final permitted day is included. Future-effective quotes,
  including later today, cannot approve current lending. Each required metal
  needs its own positive applicable quote. Latest-quote selection, source
  provenance and append-only Rates corrections remain unchanged.
- New metal-dependent approvals use `quote-age-origination-v2`. Freeze the
  applied maximum, `LOCAL_CALENDAR_DAYS`, each quote's age at evaluation and all
  existing immutable quote evidence. Quote age is outside the quote identity:
  the same quote does not acquire a new identity at midnight.
- Simple review, renewal preview and updated-valuation review bind the applied
  limit as well as selected quotes. Pending payout checks require the current
  limit to match the frozen limit, quotes still eligible, and selected identities
  unchanged. Tightening or loosening the limit requires a new review. Restoring
  the exact prior limit permits an otherwise identical, still-valid approval.
  Completed authorized retries return the original result.
- Existing `same-day-origination-v1` approvals retain a zero-day requirement.
  Neither migration nor reading upgrades their evidence. New reapproval adds a
  new immutable version; it does not rewrite an earlier approval or issued PDF.
- Current lending still uses today's loan and payout date for metal-dependent
  methods. This establishes an action being performed now. Already completed
  payouts retain their actual date through their existing recording commands.
  Appraisal-only policy retains its existing checks without requiring a quote.
- Monitoring uses `LoanMonitoringPolicy.rate_freshness_days` independently.
  Current lending eligibility is not a claim that the collateral monitoring
  evidence is current. Historical recording is not subjected to today's limit
  and never invents a quote or Rokkad approval for a paper transaction.
- Khata's existing consumers of prospective quote eligibility use this same
  Workspace limit. New opening/withdrawal and collateral reviews retain the
  applied limit; changing it invalidates pending reviews. Completed operations
  and their rate evidence remain unchanged. A legacy opening without the new
  limit requires renewed review before its first payout.

No new table, financial event, source conversion, daily confirmation requirement,
policy framework or monitoring rule is introduced. Migration 0063 adds the field
and storage constraint to the existing forced-RLS table. Exact native recovery
archives continue to require a matching schema and retain the configured limit.

See [LC-06 delivery](../implementation/prospective-quote-age-lc06.md) and the
[continuation plan](../plans/loan-continuation-consolidation.md).
