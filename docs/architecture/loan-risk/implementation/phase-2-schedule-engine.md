---
status: complete
owner: loans
updated: 2026-08-11
tags: [loans, schedules, obligations, products]
related: [roadmap.md, status.md, phase-0-conformance.md]
---

# Phase 2 Deterministic Repayment Schedule Engine

Phase 2 produces a pure preview from frozen contract values. It creates no
database row, loan event, outbox record, voucher, or journal entry. Persistence
and payment allocation remain Phase 3 responsibilities.

## Calendar and rounding contract

- Due dates are calculated from the original disbursal date for every sequence,
  so 31 January clamps to 29 February 2028 and recovers to 31 March.
- Money uses the supplied currency quantum and half-up rounding.
- Principal components always reconcile exactly to original principal.
- EMI and equal-principal residue is absorbed by the final principal component.
- The schedule reports its interest rounding adjustment explicitly.
- A SHA-256 fingerprint covers the version, dates, principal, interest,
  adjustment, and every scheduled component.

## Strategies

- Single-payment bullet: all principal and simple contractual interest mature
  together.
- Periodic-interest bullet: interest is due on each monthly anniversary and
  principal on the final anniversary.
- Flexible partial-payment: its initial contractual schedule matures principal
  and interest together; voluntary payments will create allocations and any
  permitted future rescheduling in Phase 3.
- EMI: level rounded payments until the final residue-adjusted payment.
- Equal principal: equal rounded principal components with declining interest.

Mixed collateral interest is calculated from explicit principal/rate tranches.
Those tranches must reconcile exactly to aggregate principal. Legacy unspecified
contracts cannot generate a new schedule because their terms were never known.

## Verified examples

The golden INR 120,000, 1%-monthly, 12-month examples reconcile as follows:

- bullet total interest: INR 14,400;
- periodic bullet: INR 1,200 monthly interest;
- EMI first payment: INR 10,661.85 with final principal residue adjustment; and
- equal-principal payments decline from INR 11,200 to INR 10,100.

Tests also cover zero interest, mixed-rate tranches, leap-year clamping,
non-negative balances, exact principal reconciliation, invalid legacy inputs,
and deterministic fingerprints.
