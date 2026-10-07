---
status: accepted
owner: project
updated: 2026-10-07
tags: [loans, origination, workflow, correction]
related: [2026-10-05-unified-loan-admission-and-continuation.md, ../plans/loan-origination-completion.md]
---

# Shared routine loan entry and explicit origination correction

## Context

The owner accepted the 7 October analysis and requested phased completion of all
recommendations and four deployment items. PawnLoan/continuation are shared,
but routine entry still dispatches to two editors. SIMPLE owner confirmation
already records approval/disbursal atomically; EXTENDED supports separate actions.

D01623 demonstrates a missing correction: a later native payout was fully reversed,
while the actual earlier paper advance remains unrecorded. Retained review lacks
original-day digital evidence; general draft admission excludes posted history.
Neither should silently fall back after failure.

## Decision

1. Share the routine editor/review for current lending and completed recording.
   Existing scoped defaults choose purpose, not financial semantics. Use ordinary
   Django forms/formsets and existing services.
2. Retain authorization/payout as internal facts. SIMPLE exposes one confirmation;
   EXTENDED retains separate responsibility/permissions. Completed recording
   verifies facts without inventing historical approval, policy or prices.
   Historical valuation, current lending and current monitoring remain distinct.
3. Add explicit review for the demonstrated fully reversed native-to-recorded
   correction, retaining identity and old evidence and establishing at most one
   unreversed origin. Inspect origin/schedule/reversal/portability guards before
   selecting final evidence/command details. Broader shapes are not automatically
   supported.
4. Imports/openings/terminal preparation feed the ordinary domain with truthful
   history boundaries. Unsupported archives stay browsable.
5. Complete actual source/staff acceptance, media recovery and capacity evidence
   before the concrete production rollout review.

## Consequences

Staff get a familiar entry experience; evidence differences remain visible where
they matter. Frozen profiles and posted amounts are not silently rewritten.
Financial correction needs conservation, chronology, retry/reversal, recovery and
tenant-isolation tests. Changed candidates require their own CI/recovery evidence.
No new loan model or generic workflow engine is authorized.
