---
status: accepted
owner: loans
updated: 2026-10-16
tags: [loans, monitoring, evidence, time]
related: [2026-10-11-live-risk-assessment-boundary.md, ../plans/loan-boundary-simplification-20261016.md]
---

# Live monitoring evidence has an assessment instant

The owner approved the ordered origination/monitoring review on 16 October.
LS-01 corrects the calendar-date evidence boundary before broader consolidation.
It changes derivative assessment semantics, not financial agreements or events.

## Decision

Keep the business assessment date for interest, maturity, overdue and inclusive
evidence-age rules. Capture one aware evidence instant at the start of live
refresh and use it for quote/appraisal eligibility. Evidence effective exactly at
that instant is eligible; later-today evidence is excluded. An explicit cutoff
must belong to the assessment's local date, and cannot be later than now for a
live assessment. Dated read-only valuations default to local day-end restatement
from available knowledge; they do not certify what was known historically.

Quotes remain selected by the Rates facade. An optional next-effective lookup
returns the earliest upcoming eligible quote in the same Workspace, metal,
currency, purity and correction/withdrawal scope. Existing callers retain their
normal lookup behavior and query count. Monitoring also finds the earliest
upcoming approved appraisal for its items. Only evidence required by the selected
valuation method schedules expiry. Future-day expiry is harmless because the
existing business-date boundary already makes yesterday's assessment stale.

Save `valuation.evidence_at` and nullable `valuation.next_evidence_at` in derived
snapshot provenance. Object readers, portfolio/dashboard SQL, communication
readiness and worker selection treat a reached deadline as stale without needing
another source write. The SQL predicate converts the saved timestamp text to an
aware PostgreSQL timestamp rather than comparing serialized offsets lexically.
The writer rejects a calculation crossing the scheduled boundary before its
commit checks. Existing before/after source checks and midnight guards remain.

Use `LOAN_RISK_SNAPSHOT_V10`. Older snapshots remain retained but fail currentness
until ordinary refresh; no historical result, original quote, approval, financial
event, custody or loan policy is rewritten. No table or migration is required.
Keep existing per-loan worker locks and transactional invalidation in this slice.

## Release and verification

Coordinate compatible web, monitoring and scheduled/communication readers before
V10 writes. The new provenance changes derived monitoring output only; published
financial exchange contracts retain their meaning. Local implementation is not
deployment, and production remains on its prior reviewed reader until released.

Acceptance exercises morning versus later-today quotes and appraisals, exact
boundaries, dated reports, saved-result expiry, worker reselection, commit races,
financial no-writes, read parity and restricted-role isolation. See the
[implementation record](../implementation/loan-boundary-ls01-20261016.md).
