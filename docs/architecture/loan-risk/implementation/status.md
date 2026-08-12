---
status: active
owner: loans
updated: 2026-08-11
tags: [loans, risk, status]
related: [../README.md, roadmap.md]
---

# Loan Risk Architecture Status

## Current state

- Architecture analysis: complete and preserved in the master plan.
- Focused concept documents: drafted.
- Core architecture: accepted in
  `docs/adr/2026-08-11-loans-product-obligation-and-risk-architecture.md`.
- Four repayment products and RBI-aligned standard defaults: accepted.
- Execution roadmap with per-phase invariants, migrations, tests, and acceptance
  criteria: complete.
- Phase 0 implementation: complete. The current-behavior/conformance baseline,
  four-product fixtures, workspace scoping, event/DEA reconciliation, and
  golden characterization tests are established.
- Runtime and schema changes: not started; Phase 0 intentionally makes none.
- Phase 1 implementation: complete. Product catalog/version models, immutable
  contract selection, tenant-scoped draft and renewal wiring, the idempotent
  four-product seed, legacy-only backfill, and the required PawnLoan reference
  are implemented.
- Phase 2 implementation: complete. The versioned, pure schedule engine covers
  both bullet products, flexible partial payment, EMI, equal principal,
  mixed-rate tranches, calendar clamping, residue, and fingerprints without
  performing writes.
- Phase 3 implementation: complete. Immutable schedule-version, obligation,
  and allocation models are added. Disbursal persists schedules idempotently;
  ordinary repayments allocate interest then principal across obligations
  oldest-first, and generic event reversal appends exact inverse allocations.
  Full release, renewal settlement/opening, and auction recovery/reversal now
  participate. Installment schedule supersession and concurrency coverage remain open.
  Allocation now locks active obligation rows and an independent reconciliation
  fold reports scheduled, allocated, remaining, and integrity findings. The
  supersession design must also represent early settlement so unearned future
  interest is not misreported as remaining debt.
  Append-only schedule-change evidence now terminates schedules on release,
  renewal settlement, and auction recovery, and reactivates them on reversal.
  Reconciliation therefore reports zero remaining debt after valid early
  closure without inventing payment of unearned future interest. Installment
  extra-principal regeneration now keeps the EMI (or equal-principal component),
  shortens tenure, preserves prior obligations, and falls back to the prior
  schedule when the prepayment is reversed. Row locks and source/order
  uniqueness protect concurrent allocation and duplicate requests.
- Phase 4 implementation: complete. The canonical read-only exposure selector
  separates recorded balances, actual-outstanding projected interest, due,
  overdue, accounting receivable, maturity payoff, and product-aware LTV basis.
  The loan detail labels recorded and projected values explicitly.
- Phase 5 implementation: complete. A pure obligation fold derives contractual
  due, overdue, oldest unpaid due date, regulatory DPD, bucket, cure, and
  operational escalation after the frozen product grace period. A tenant-safe
  selector exposes legacy/new overdue variance without changing lifecycle,
  notice, or auction authority.
- Phase 6 implementation: complete at the valuation foundation boundary.
  Immutable effective-dated appraisals, legacy appraisal backfill, historical
  rate/appraisal resolution, custody-aware item valuation, product-aware LTV,
  headroom, blockers, and full shortfall are available without switching
  release or renewal consumers. Freshness classification belongs to Phase 7.
- Phase 7 implementation: complete. Immutable effective-dated monitoring
  policies support workspace defaults and license overrides with non-overlap
  validation. The pure deterministic assessment composes maturity, DPD,
  valuation, LTV, and reconciliation variance into explainable flags,
  performance, severity, action hints, and a source fingerprint without side
  effects or lifecycle changes.
- Phase 8 implementation: complete. One typed current risk projection per loan
  stores filterable assessment facts plus source/assessment fingerprints and
  explicit current, stale, or error health. Refresh calculates unlocked,
  verifies source stability while holding the loan/snapshot lock, never
  publishes changed input, and supports tenant-scoped rebuild diagnostics.
- Phase 9 implementation: complete. Immutable risk events are appended in the
  snapshot publication transaction and deduplicated by deterministic trigger.
  Initial assessment, maturity, delinquency, LTV, valuation, performance,
  severity, policy, assessment failure, and recovery transitions are captured
  in both deterioration and cure directions without rewriting history.
- Phase 10 implementation: complete at the application boundary. Explicit-
  tenant bounded `skip_locked` reassessment, commit-time source invalidation,
  retry/error diagnostics, daily time-boundary selection, filtered paginated
  snapshot reads, and SQL concentration summaries are implemented. Pilot
  1,000/10,000-loan timings remain an environment rollout measurement rather
  than a correctness blocker.
- Phase 11 implementation: code-complete and awaiting acceptance. Immutable
  KFS/schedule issues, detail-level contract/risk facts, and a read-only DEA
  aggregate receivable reconciliation facade are implemented. Existing
  workflow authority remains unchanged. Four-product browser/document/
  accounting walkthroughs, parity review, and explicit Owner acceptance remain
  required by the final gate. Migrations through `0048` were applied to all
  seven configured development schemas on 2026-08-12; the follow-up migration
  plan was empty.
- Migrations: complete for configured development schemas. Product seeding is
  deliberately separate and remains an explicit per-tenant setup action.
- Workflow authority: unchanged pending acceptance and cutover approval.

## Locked defaults

- Bullet principal and interest are due at maturity; consumption bullet tenor
  is capped at 12 months under the applicable RBI profile.
- Periodic interest is due monthly; principal is due at maturity.
- Flexible partial-payment allows voluntary reductions with residue due at
  maturity and no partial collateral release.
- Installment supports EMI and equal principal; extra principal keeps payment
  unchanged and shortens tenure.
- Three-day grace affects charges/escalation only; exact due dates drive DPD.
- Product, compliance, calculation, monitoring, and issued-contract versions
  remain frozen and identifiable.

## Review order

1. Review and explicitly activate approved product versions; the seed leaves
   every version in draft status.
2. Run the Phase 11 four-product browser/document/accounting acceptance gate.
3. Review Loans/DEA parity and record explicit Owner cutover acceptance.

Record each approved decision as a dated ADR under `docs/adr/`. Update this
status after every review or implementation phase.
