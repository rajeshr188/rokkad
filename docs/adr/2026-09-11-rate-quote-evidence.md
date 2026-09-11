---
status: accepted
owner: rates
updated: 2026-09-11
tags: [rates, evidence, valuation, workspace]
---

# ADR: Effective-dated, append-only reference quotes

## Context

Rates previously allowed in-place editing and hard deletion. Its creation timestamp
also determined economic applicability. Loans consumes reference prices, freezes
completed calculation evidence, and must detect subsequent quote changes without
rewriting that evidence. The owner approved quote reliability as increment 2 of
the [Rates/appraisal review](../implementation/rates-appraisal-monitoring-review.md).

## Decision

- A quote is a price **per gram of the selected purity**, excluding tax and making
  charges. Both prices must be positive. Loans uses only INR pure-metal buying
  prices for gold and silver. The existing `24k` storage key remains compatible;
  its UI label becomes **Pure metal (100%)**. Other karat choices apply only to gold.
  No hidden unit, currency, tax or purity conversion is performed.
- `effective_at` is operator-supplied applicability time. `timestamp` remains the
  immutable entry time. Historical quotes receive their original timestamp as
  effective time, with unchanged prices/purity and an explicitly unknown author.
- Ordinary entry records the authenticated actor and a snapshot of the source's
  name, location and descriptive tax flag. The flag does not alter a calculation.
  Legacy snapshots describe the source at migration time, not proven original metadata.
- Corrections append a new quote linked by `supersedes`, with actor and reason.
  A withdrawal appends a marker carrying the original quote values, actor and reason.
  The old record is retained. A row lock and unique successor relation prevent
  competing corrections from producing two branches. Withdrawals are terminal;
  restoring a quote requires a new independent entry.
- PostgreSQL rejects quote UPDATE/DELETE, invalid new prices, cross-Workspace
  source/revision links, and malformed withdrawal records. Existing invalid
  quotes are preserved and can be corrected or withdrawn; no market value is invented.
  Application commands separately require the current Workspace, membership/action
  permission and active lifecycle. Create/edit/delete permissions respectively map
  to entry/correction/withdrawal. Django admin exposes quote history read-only.
- Sources referenced by any quote are protected from deletion. Source edits affect
  future entries, while existing source snapshots remain unchanged.
- The selection rule is explicit and deterministic: among current, nonwithdrawn
  quote versions matching Workspace/metal/currency/purity and the requested time,
  choose greatest effective time, then entry time, then record ID, across sources.
  No source preference configuration is introduced without an actual need.
  Date-only queries retain inclusive local-calendar-day semantics; queries without
  an as-of value use now and exclude future effective times.
- Historical as-of reads use **current corrected knowledge for that effective
  date**. They are not “what staff knew then” queries. Existing approved loan
  evidence remains the authority for completed calculations. Withdrawal may cause
  selection to fall back to an earlier independent quote; age checks remain the
  next increment.
- Risk invalidation covers both the revised quote's prior scope and its new scope.
  Fingerprints include appended revisions affecting either scope. Immutable rows
  eliminate the previous in-place-value-edit fingerprint race.

## Consequences

No new tenant table, Redis dependency, provider feed or accounting integration is
introduced. A Rates migration and updated application must be deployed together.
Reverting the migration would discard new correction metadata and remove evidence
guards; use normal database backups and coordinated code/schema deployment.

Freshness enforcement, active-loan reappraisal, portfolio completeness and scheduled
refresh remain subsequent increments. Source prioritization, feeds/imports and
historical knowledge-time queries are not implemented by this decision.
