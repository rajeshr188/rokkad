---
status: active
owner: loans
updated: 2026-10-16
tags: [loans, architecture, monitoring, delivery]
related: [../architecture/loans-architecture-followup-20261016.md]
---

# Loans architecture hardening

The owner accepts the follow-up recommendations and authorizes implementation in
the recommended order. Production deployment and actual business policy/data
changes remain separate from preparing and verifying the software.

| Slice | Scope | Status |
|---|---|---|
| LA-01 | Distinguish admission compatibility references from current monitoring; characterize classification/alert rules | Implemented locally |
| LA-02 | Immutable scheduled-policy replacement/cancellation and licence-override retirement, compatible resolution/recovery | Implemented locally |
| LA-03 | Source-bound policy impact review and active-portfolio readiness | Implemented locally |
| LA-04 | Reuse signed batch review for explicit cohort/future-capture choice; early action capabilities | Implemented locally; assurance remains optional |
| LA-05 | Complete alert pagination/counts and actionable monitoring filters; explain DPD trigger semantics | Implemented locally |
| LA-06 | Worker measurement/assignment diagnostics, followed by evidence-gated scheduling/reuse/pool work | Diagnostics and bounded measurement delivered; scheduling/reuse/pool changes remain evidence-gated |

Preserve one PawnLoan, immutable original agreements/events/issued copies,
canonical financial calculations, source-bound reviews, retry safety, forced RLS,
and published portable meanings. Do not manufacture missing reference limits,
prices, appraisals, transactions or source attestations. Unsupported connected
financial corrections remain held. Each slice records affected tests and any
release compatibility requirements before the next dependent slice starts.

The worker work follows FW-004: measure first, then justify indexed scheduling,
reuse and pool sizing with parity/race/isolation gates. The shelved large load
programme is not resumed automatically. No arbitrary new agreement profile is
selected without a concrete business need.

The [implementation and acceptance record](../implementation/loans-architecture-hardening-20261016.md)
identifies the frozen combined candidate, verification and coordinated release
requirements. A separate active session's represented-position coverage changes
are preserved. Per the owner, acceptance runs against an isolated source snapshot
rather than requiring that session to stop editing the shared checkout.
