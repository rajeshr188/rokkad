---
status: accepted
owner: project
updated: 2026-09-23
tags: [loans, payments, portability]
---

# Collect payments on reviewed opening loans

The owner requires interest-only and partial-principal collections on JCL, JSK and
Lakshmi openings, with reduced-principal interest from the next original monthly
anniversary. Extend the existing repayment workflow, without admitting arbitrary
events through the ordinary opening guard. Preserve the existing inclusive
anniversary calendar: the next monthly charge appears the day after the anniversary.
A payment changes the base of subsequent charges, never an already-earned charge.
Keep cumulative HALF_EVEN whole-rupee rounding, original item rates, and the
reviewed first-month coverage. Fees and interest are paid before principal;
principal follows the existing highest-rate-item allocation.

Version the new event evidence as `opening-payments/1`. A payment records any
unposted interest catch-up and its receipt atomically; preserve item allocation
rows, schedule allocations and any interest beyond the frozen schedule. Subsequent
release settles only remaining debt. Newest-first reversal compensates the receipt
and its catch-up together. Reversing a principal payment removes that payment's
effect on future interest; historical as-of reads before reversal retain it.
Custody and closure remain the explicit full-release workflow even if debt is zero.

Keep existing `opening-release/1` evidence readable and reproducible. Payment-aware
export uses `loan-opening-export/2`, adding frozen repayment allocation rows;
retain v1 for histories without payments. Restore through financial commands and
compare the rebuilt graph, including item allocation evidence, before committing.
No new table, generic event API, native periodic accrual, renewal or auction support.
Validate permissions, RLS, retries, rollback, anniversary/rounding boundaries,
release/reversal and portable restoration before declaring this path ready.
