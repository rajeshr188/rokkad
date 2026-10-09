---
status: accepted
owner: project
updated: 2026-10-09
tags: [loans, series, numbering, servicing, paper-entry]
related: [2026-08-08-loans-license-regulatory-evidence.md, ../domain/loan-series-availability.md]
---

# Series availability controls new lending, not existing-loan servicing

## Context and authorization

The owner accepts showing only running series in routine New loan, automatic
exclusion after loan-number exhaustion, manually stopping new lending, and an
explicit old-series path for earlier paper loans. The current active flag also
blocks release-number issuance, contrary to servicing existing loans after a
series stops or its licence expires.

## Decision

- Reuse `LoanSeries.is_active` as **Open for new loans**. Do not add another lock
  state, automatic flag mutation, deletion or availability configuration model.
- Running requires an open series, a current active verified licence and an active
  PawnLoan number sequence with a counter within its configured maximum. Use one
  Workspace-scoped selector for direct/paper choices and initial purpose resolution.
  Economic/quote readiness remains its existing separate validation.
- Setup retains every register and derives Running, Stopped for new loans,
  Numbers exhausted, Licence unavailable or Numbering unavailable with a reason.
  Release-sequence problems are displayed independently.
- New allocation, approval and unpaid disbursal recheck manual availability.
  Allocation and final lending guards lock/read the current series row. The owner
  stop/reopen service is audited and serialized; it obtains a Workspace NO KEY
  UPDATE lock before the series to respect audit/combined-review dependencies
  without blocking financial foreign-key checks. Reopening never resets counters.
- Exhaustion prevents another number allocation; an already-numbered draft may
  still finish approval/payout when its series is open. Manually stopping the
  series blocks an unpaid payout. Completed successful retries remain unchanged.
- Release-number allocation checks Workspace ownership and its own sequence;
  it does not require a series or licence to remain open for new lending. Sequence
  inactivity/exhaustion, settlement authority and financial/custody checks remain.
- Routine paper entry normally shows running series. **Record an earlier loan
  from an old series** deliberately exposes retained registers with status labels.
  Its checkbox is presentation metadata stripped before canonical signed/storage
  data. It does not activate setup or permit a fresh native payout. Existing
  source-date/evidence, number-range, duplicate, terms and reconciliation rules
  remain. Signed open confirmations/retries retain access to their selected series.
- Saved drafts and specialist archive/import/correction contexts retain their
  actual series identity. Existing loan balances, policies, monitoring, documents
  and event history do not change. No model migration or production data change.

## Consequences

Routine entry avoids obsolete registers without hiding history or preventing late
paper recording. Stopped/expired setup cannot obstruct ordinary existing-loan
closure through release-number allocation. Production rollout remains separate.
