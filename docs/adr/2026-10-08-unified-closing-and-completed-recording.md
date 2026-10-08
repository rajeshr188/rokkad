---
status: accepted
owner: project
updated: 2026-10-08
tags: [loans, closure, custody, paper]
---

# Unified close action and consistent completed recording

The owner approved consolidating routine closing after the unified loan adaptation.
Origination source does not determine how a subsequent settlement happens. Use one
Close / release loan screen with current collection/return or completed-recording
purpose; standing entry preferences supply a convenience default, while an explicit
Rokkad-only loan capture commitment or Workspace current-recording commitment favors
current action. Every submitted purpose is explicit and uses its existing writer.

Keep counter batches as one combined payment today. Completed-recording batches
group independent settlements for entry/reconciliation, never assert another cash
collection on entry day, and use the same actual-date/evidence/concession options
as individual completed recording. Unknown physical collection/handover retains
PAPER_CLOSED and last-known storage, with subsequent evidenced handover available.
Confirmed returns require recipient facts; other recipients require authority.

Reuse ordinary release records and existing closure evidence meanings. Preserve old
paper-closure/1 batches and previously issued individual review/retry facts. New
extended rows use recorded-history-closure/1, whose settlement/return basis already
supports uncertainty, with additive batch/source/exception metadata. No old evidence
is rewritten or silently upgraded. Portable connected graphs retain batch evidence.

Paper practice is a supported ongoing operating model. Existing owner-controlled
Workspace cutoff/retirement fields become optional completed-recording restrictions;
their persisted meaning and existing choices remain. The all-recording restriction
can be selected without supplying a dated cutoff. Apply the same restriction to
individual and bulk completed closures, rechecking under the transition lock before
loan locks. An authorized exception requires its retained reason. No automatic
deadline, new scope configuration, permission grants or retirement backfill.

This refines the presentation and coverage of the September transition decision;
it preserves exact settlement, concessions, chronology, scope, custody, atomic
posting and explicit corrections. No new financial model or table is required. Migration 0064 updates two existing
batch guards: blank payer/collector is permitted only for PAPER rows with an
exactly bound recorded-history-closure/1 PAPER_SETTLEMENT event. Other rows retain
payer/collector checks, scope/date constraints, immutable evidence and exact totals.
