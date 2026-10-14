---
status: completed
owner: project
updated: 2026-10-15
tags: [loans, origination, consolidation, monitoring]
related: [../architecture/loan-origination-review-20261014.md, ../adr/2026-10-14-origination-consolidation.md]
---

# Complete ordinary loan origination consolidation

The owner authorised proceeding with the reviewed recommendations on 14 October.
Keep existing PawnLoan, snapshots, immutable financial evidence and source adapters.
No new lending product or calculation is inferred. Development and local verification
are authorised; real configuration/data changes and production release remain separate.

| Slice | Outcome | Acceptance | State |
| --- | --- | --- | --- |
| OC-01 | Ordinary existing-register reservation | Reviewed AA-through-5000 setup; interleaved direct/backlog numbers; collision/concurrency/auth/RLS | Verified locally |
| OC-02 | Common agreement capabilities and risk baseline | Factual capability selection; four-origin semantic/monitoring parity; preserved uncertainty/events | Verified locally |
| OC-03 | Ordinary correction preparation | Shared borrower correction for eligible active agreements, common correction navigation; impact/dependency guards | Verified locally |
| OC-04 | Portable borrower correction evidence | Versioned two-Party mapping, immutable source retention, runtime restore/recovery and published-profile preservation | Verified locally |
| OC-05 | Integrated ordinary origination acceptance | Mixed AA journey, current servicing/paper receipts across origins, once-only recognition, documents/monitoring | Verified locally |

Actual new products/calculations require their business rules before implementation.
The supported modern monthly agreements are the initial consolidation target.
Legacy readers retain their semantics; no silent conversion of old monetary events.

Risk parity compares balances, additional eligible interest, exposure, obligations,
DPD/maturity, current valuation/LTV, evidence coverage and alert decisions at identical
facts/policy/date. Identity changes legitimately invalidate borrower-bound reviews.
New evidence contracts require compatible web/worker readers before enabling writes.

All observed failures are resolved across the baseline/wider/affected runs; the
final 205-case confirmation and two final HTTP checks pass. Eight styled captures,
model/system/migration/import/link/whitespace checks pass. See the
[verification record](../implementation/loan-origination-consolidation-20261014.md).
Production rollout completes on 15 October under the owner's later proceed
instruction. Compatible readers and sixteen owner migrations preserve all 199
original business projections; see the
[release record](../implementation/origination-production-release-20261015.md).
Actual register/customer changes remain separate business actions.
