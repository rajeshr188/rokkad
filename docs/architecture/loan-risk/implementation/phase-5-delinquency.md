---
status: implemented
owner: loans
updated: 2026-08-11
tags: [loans, dpd, delinquency]
related: [roadmap.md, ../concepts/delinquency-dpd.md]
---

# Phase 5: DPD and delinquency

DPD is now derived from the oldest unpaid obligation whose contractual due
date is before the requested as-of date. An amount due today is due but not
overdue; it becomes DPD 1 on the following day.

The frozen product version supplies operational grace. Grace controls only
`escalation_eligible`; it never shifts the contractual date or reduces
regulatory DPD. The pure fold returns due, overdue, oldest unpaid due date,
DPD, and the `CURRENT`, `1-29`, `30-59`, `60-89`, or `90+` interpretation.

`get_pawn_loan_delinquency()` applies that fold to the active schedule and
effective-dated allocations. It also reports the existing maturity-based
`balance.is_overdue` value and an explicit variance flag. Existing notice and
auction authorization remains unchanged until its planned compatibility
cutover.

Focused tests cover due-today behavior, every bucket boundary, three-day
operational grace, partial cure, oldest-unpaid movement, and full cure.
