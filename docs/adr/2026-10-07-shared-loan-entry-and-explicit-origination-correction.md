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

## LO-01 correction profile

`recorded-origination-correction/1` is an explicit administrator-reviewed entry,
using the existing recorded-history writer. Its signed submission is distinct from
ordinary draft admission. The supported source has one to twenty native approved
payouts, each exactly reversed on the same effective business date, no other money
events, accruals, renewal, custody or funding dependencies, and a reopened draft.
The actual original date, identity and physical collateral facts must already be
correct; this profile changes agreed financial terms, not jewellery evidence.

Same-day pairs preserve a zero effective-date balance; they remain in financial
folds and exact recovery. Only validated retained pair IDs are excluded from later
servicing chronology and unrelated-reversal blockers. Different-day reversals are
outside this profile because intervening financial history requires broader review.

The new recorded snapshot becomes the current origin; earlier approvals, snapshots,
schedules, events, photos and issued copies remain. Native reissue is refused once
recorded origin evidence exists. Subsequent receipt/contract correction uses the
existing recorded-history correction commands. Exact Workspace recovery retains
the graph and files; bounded per-loan export refuses this profile until its embedded
native source IDs have a supported remapping contract. No schema migration or
permission expansion is introduced.

## LO-02 presentation and current media

Routine entry shares one template and item controller while retaining ordinary
Django bound fields and purpose-specific commands. Specialized saved-draft,
archive/import/opening and legacy POST contexts remain separate. Current paper
photos use the existing immutable media service, with actual capture time/actor;
signed review binds selected files before atomic attachment. This neither claims
original-date photos nor invents an approval. Final review/confirmation remains
LO-03. See the [implementation note](../implementation/shared-routine-loan-editor-lo02.md).

## LO-03 review and confirmation

SIMPLE owner Review loan saves one numbered draft and opens the common agreement
summary; Confirm payout uses the existing atomic approval/payout command. Save
draft remains available, and EXTENDED/owner authority do not change. Paper, saved
completed drafts and explicit correction share the summary and Record completed
payout, retaining source/history/custody differences. Original proceeds do not
assert physical cash. Preparation and final financial confirmation remain distinct.

New owner tokens add versioned actor/date/full-contract/photo-policy binding using
the existing salt and unchanged v1 input fingerprint. The existing immutable
approval JSON retains server-created combined-review proof so active retry can
identify the actual approval behind the unreversed payout. Full frozen economics
and quote identities are compared at confirmation. Issued v1 owner/historical
tokens and recorded-review structures keep their existing contracts; presentation
metadata is separate from signed paper review data. Exact recovery retains the
proof, financial graph and photos. No schema or permission expansion is added.
