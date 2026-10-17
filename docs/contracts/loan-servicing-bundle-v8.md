---
status: active
owner: loans
updated: 2026-10-17
tags: [loans, portability, corrections, legacy]
related: [loan-servicing-bundle-v7.md, loan-agreement-correction-v1.md]
---

# Loan servicing bundle version 8

`loan-servicing-bundle/8` extends the version-7 agreement correction graph to
retained `loan-opening-review/2` aggregate collection checkpoints and unserviced
native policy-1 original agreements. Published
versions 1-7 keep their meanings. Version 7 continues to carry supported shared
monthly checkpoint and native agreement corrections; an aggregate checkpoint
correction must export as version 8, and cannot be relabelled as version 7.
The same requirement applies to corrected native policy-1 snapshots; their
correction evidence explicitly retains `policy_version: 1`. Source validation and
the database guard reject pre-correction charges/payments. Later supported
servicing is retained without permitting an independent correction over it.

Version 8 uses the same fixed row inventory, required `agreement_revision`, Party
mapping, underlying financial profile and source-local reference/hash handling
as version 7. It adds no loan type, financial origin, payment or rounding rule.

Aggregate corrections retain the original-anniversary inclusive calendar,
original-principal interest basis, aggregate HALF_EVEN whole-rupee rounding and
first-month-paid premise. Original source rows, dates, item mappings, physical
evidence and accepted import remain immutable. The corrected complete checkpoint
passes the ordinary opening validator; unavailable earlier transactions stay
unavailable. Explicit remaining obligations keep their reviewed source identities
and dates. New interest recognition, principal reductions or future obligations
must not be inferred from changing a rate.

The append-only correction retains its original opening, preceding event/hash,
before/after amounts, reviewer, reason, supporting reference and request key.
Current readers resolve the chain; the financial fold contributes only its
before/after difference. Restore remaps local identities and recalculates local
predecessor hashes, while the immutable source bundle preserves original claims.

Native policy-1 corrections retain the captured policy and genuine original
approval, append compensation and a corrected snapshot, and require original
principal/rates/proceeds to reconcile with retained fees and actual advance
periods. Their full-period interest uses the legacy calculator; their rolling
calendar is not promoted to the policy-2 original-anniversary calendar. The
corrected original cash facts do not create a new payout or refund.

Loans migration 0092 and data_portability migration 0031 are required. Both
downgrade paths reject retained new evidence that requires compatible readers.
Deploy compatible web, worker, scheduled and recovery readers before enabling
these writes. A code deployment does not authorize a production data correction.
