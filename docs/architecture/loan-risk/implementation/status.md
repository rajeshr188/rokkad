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
- Implementation: not started and not authorized.
- Migrations/backfill: not started.
- Workflow changes: not started.

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

1. Execute Phase 0 regulatory/current-behavior characterization.
2. Review its conformance matrix and interest-timing findings.
3. Authorize Phase 1 ProductVersion implementation only after Phase 0 passes.

Record each approved decision as a dated ADR under `docs/adr/`. Update this
status after every review or implementation phase.
