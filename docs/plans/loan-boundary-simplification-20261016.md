---
status: completed
owner: loans
updated: 2026-10-16
tags: [loans, architecture, origination, monitoring]
related: [../architecture/loan-origination-monitoring-review-20261016.md]
---

# Loan origination and monitoring simplification

The owner accepted the [review](../architecture/loan-origination-monitoring-review-20261016.md)
and authorized implementation in its recommended order on 16 October. Keep one
PawnLoan domain, immutable financial evidence and existing Workspace boundaries.
Use ordinary services/selectors and compatibility readers. No deployment or live
loan/policy correction is part of this local implementation instruction.

| Slice | Scope | Status |
|---|---|---|
| LS-01 | Characterize admission/financial reads; make live valuation evidence time explicit, including scheduled evidence becoming applicable | Deployed in combined Loans release |
| LS-02 | Consolidate completed-payout review around explicit action purpose; preserve prior approval evidence and successful retries | Deployed in combined Loans release |
| LS-03 | Promote existing shared financial reads; keep old storage decoding inside compatibility adapters | Deployed in combined Loans release |
| LS-04 | Separate current monitoring inputs from original decision evidence; preserve existing methods/formulas | Deployed in combined Loans release |
| LS-05 | Consistent risk/evidence/freshness presentation and capture expectations | Deployed in combined Loans release |
| LS-06 | Measure invalidation and worker contention; change revision/locking mechanics only where measurements warrant it | Deployed in combined Loans release |

The shared financial/collateral correction implementation is committed in
7681aac0 and is now deployed with LS-01 through LS-06 after separate owner
authorization. See the [combined release record](../implementation/loan-boundary-release-20261016.md). Preserve it and the deployed Party-merge fix.
Review exported meanings, original documents, correction lineage and compatible
readers before any new persisted calculation or portable contract change.

## LS-01 acceptance

- Live valuation excludes future-effective quotes and appraisals within today.
- Evidence effective exactly at the captured assessment instant is eligible.
- Dated read-only reports retain explicitly documented day-end restatement.
- A saved assessment expires when relevant scheduled evidence becomes applicable;
  the normal worker can select it without requiring another source write.
- An assessment crossing that boundary before commit is discarded for retry.
- New calculation version makes older saved projections stale without changing
  original agreements or financial events.
- Existing direct/paper/imported continuation, anniversary, correction and
  tenant-isolation checks remain green; monitoring adds no financial postings.

Each slice records the affected checks and release requirements. Passing local
tests does not establish production rollout or real-book acceptance.

LS-01's final 58-case affected selection passes after a wider 193-case run found
one timestamp-parity fixture failure. That comparison now uses one explicit
cutoff and passes in the final affected module. The selections overlap and are
not a combined unique count. Django/model/import/link/whitespace checks pass.
See the [verification record](../implementation/loan-boundary-ls01-20261016.md).

## LS-02 acceptance

- Unpaid drafts with/without retained approval share the same two-step review.
- Actual agreement facts retain identity, numbering and original approval bytes;
  no new historical approval is created.
- Changed/withdrawn quote evidence is explicitly acknowledged; changes after
  preview reject confirmation rather than silently selecting another command.
- Original cash/deductions and supported calculations reconcile. Stale, foreign,
  unconfirmed and duplicate submissions preserve existing financial safeguards.
- Existing recorded/native signed POSTs, source licence mapping, exact recovery,
  corrections and normal direct lending remain supported under existing authority.
- See the [implementation record](../implementation/loan-boundary-ls02-20261016.md).

LS-02 passes the wider 193-case regression, then 68 final affected checks and one
additional restricted-role case. The wider/final selections overlap. Exact recovery,
ordinary origination, old signed POSTs, current risk timing and four desktop/phone
states pass. No schema or production changes.

## LS-03 acceptance

- Exposure, delinquency and live/saved monitoring consume the supported financial
  reader; risk no longer imports a private exposure helper.
- Original/checkpoint principal, recorded/projected/collectible interest, frozen
  rounding, due/overdue obligations and source integrity retain their meanings.
- Opening source lineage, grace and terminal-position decoding stay behind the
  reader. Standalone DPD does not acquire an interest-projection requirement.
- Prepared results reject a different loan, date or Workspace. Financial previews
  add no posting, book attestation, policy, history or persisted balance.
- Four real admission paths, old profiles, corrected schedules, closed imports,
  servicing, documents and portability retain their supported results.
- See the [implementation record](../implementation/loan-boundary-ls03-20261016.md).

All 305 affected cases pass (504.810 seconds), including four real admission
paths, restricted-role isolation, corrections, documents and portable/exact
recovery. Django/model/import/link/whitespace checks pass; the exact isolated test
database is removed and absence verified. No schema, profile or production change.
LS-04 current-monitoring input separation is verified locally below.

## LS-04 acceptance

- Existing current methods, saved-method compatibility, saved precision and known
  reference-limit formulas preserve monetary results for supported loans.
- Current collateral observation does not require original approval or financial
  projection. Explicit methods can operate without a saved disbursal policy;
  preserve-unknown method remains unavailable, never silently reassigned.
- Missing financial support still prevents a complete risk assessment. Usable
  observations do not certify paper books or invent interest terms/history.
- Saved lending/recorded reference limits remain distinct from current risk
  thresholds. Unknown reference means unknown headroom, not an invented limit.
- V11 records precision/reference provenance and makes older projections stale.
  Snapshot temporal/source/Workspace guards and compatible recovery remain intact.
- See the [implementation record](../implementation/loan-boundary-ls04-20261016.md).

All 269 affected cases pass (285.082 seconds), including legacy observation,
three methods, reference limits, original evidence preservation, corrections,
restricted-role isolation, documents and portable/exact recovery. The initial
Rates-normalization fixture expectations are corrected in the final run.
Django/model/import/link/whitespace checks pass; the exact test database is removed.
No schema, published profile or production change.

## LS-05 acceptance

- Loan detail labels live calculations separately from saved assessment freshness;
  failed full financial projection can retain an independent current observation.
- One disclosure distinguishes advisory cause/severity, financial support,
  valuation, transaction coverage and future recording practice across loan detail
  and work queues. Unknown evidence is never described as healthy.
- Ordinary capture remains an assumption. Existing signed review choices can
  establish per-loan Rokkad-only capture independently of entry origin; paper or
  correction activity can suspend that claim until another review.
- Portfolio/dashboard share guarded monetary and coverage eligibility. Four
  completeness indicators distinguish refresh, financial, valuation and book
  problems. Aggregate GETs do not calculate portfolio risk or post events.
- Existing financial formulas, V11, authority, profile/recovery, review signatures
  and source history retain their meanings. Desktop/phone layouts are checked.
- See the [implementation record](../implementation/loan-boundary-ls05-20261016.md).

The wider 311-case regression passes (330.190 seconds), followed by 203 final
affected checks (136.479 seconds), including ten desktop/phone states. Selections
overlap. Django/model/import/link/whitespace checks pass; the exact isolated test
database is removed and absence verified. No schema, profile, posting, V11 or
production change. LS-06 measured invalidation/worker review is verified below.

## LS-06 acceptance

- Repeatable restricted-role PostgreSQL characterization measures invalidation at
  1/100/2,500 rows, small-loan worker claim duration and real receipt/reversal cost.
- Actual lock observation establishes same-loan waiting, unrelated-loan NOWAIT
  availability and skip-locked competitor behavior. Bounded workload timings are
  not production or launch-capacity acceptance.
- Existing atomic invalidation, worker claims, fingerprints, source applicability,
  errors, scheduled expiry and V11 remain unchanged. A separate-lock/CURRENT-only
  invalidation trial shows no useful improvement at 2,500 rows and is removed.
- A policy/worker deadlock is reproduced on the original code and corrected by
  FOR NO KEY UPDATE on the policy Workspace lock in service and database guard.
  Writer serialization, lifecycle conflicts, immutable evidence and overlap/scope
  checks remain. Both late rate/policy races and competing amendments pass.
- Migration 0086 changes only the existing guard function's lock mode and reverses
  exactly; no-op 0087 joins the graph. The 0086 branch excludes undeployed financial
  corrections. Both application and guard changes are required for the fix.
- All **277 final affected cases pass** (758.874 seconds), including populated
  historical upgrades. Django/model/import/link/whitespace checks pass; the exact
  isolated database is removed and absence checked. No production changes.
- See the [decision](../adr/2026-10-16-measured-monitoring-invalidation.md) and
  [measurements/verification](../implementation/loan-boundary-ls06-20261016.md).

All six slices are now deployed in the separately authorized combined release.
Matching V11 readers, the guard migration, financial-correction compatibility and
existing Party merges are verified. The local acceptance chronology above records
checks before release; current production evidence is in the
[combined release record](../implementation/loan-boundary-release-20261016.md).
