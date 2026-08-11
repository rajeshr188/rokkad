---
status: proposed
owner: loans
updated: 2026-08-10
tags: [loans, appraisal, collateral, valuation, ltv, overdue, risk]
related:
  - ../domain/loans-mixed-metal-origination.md
  - ../domain/loans-regulatory-setup-and-policy.md
  - ../adr/2026-08-09-loans-effective-dated-calculation-policy.md
  - loans-rewrite-roadmap.md
  - ../implementation/pawn-loan-interest-calculation.md
---

# Pawn Collateral Risk And Appraisal — Future Work

This document records future work only. It does not change current overdue,
notice, auction, accrual, valuation, or accounting behavior.

## Problem

PawnLoan currently freezes origination valuation evidence at approval. It can
derive contractual overdue from the maturity date and recorded balance, but it
does not continuously compare current collateral market value with the full
amount economically due as of today.

The future operator surface must distinguish:

- **Maturity overdue:** the contractual due date has passed and an amount
  remains due.
- **Collateral shortfall:** current eligible collateral value is below the
  chosen exposure threshold.
- **LTV margin breach:** current exposure divided by current collateral market
  value exceeds the applicable monitoring LTV limit.
- **Attention required:** a presentation-level union of maturity overdue,
  shortfall, stale/missing valuation, and other blocking risk signals.

Do not silently redefine the existing `balance.is_overdue` flag. Notices and
auction eligibility currently depend on its contractual meaning. Any change to
those authorities requires an explicit domain/ADR decision.

## Separate Appraiser Workflow

Future appraisal must be evidence, not an editable number on the loan:

1. An authorized operator requests appraisal for one or more collateral items.
2. A separately authorized appraiser records inspection time, method, item
   condition, gross/net weight observations, purity evidence, market inputs,
   appraised value, notes, and supporting photographs/documents.
3. Submission creates an immutable appraisal version linked to the collateral
   item, appraiser, workspace, and source request.
4. Review/approval is performed by a different authorized user when maker-
   checker policy is enabled.
5. Rejection or supersession appends evidence; it never edits or deletes a
   submitted appraisal.
6. Current valuation selectors choose the latest eligible approved appraisal
   as of the requested date and expose its age and provenance.
7. Stale, missing, rejected, or disputed appraisals produce explicit status;
   they must not silently fall back to an invented value.

Open policy decisions include appraiser roles, maker-checker requirements,
expiry/staleness intervals, whether each metal/item class requires appraisal,
and whether market-rate valuation may be used when an appraisal is stale.

## Proposed Current Exposure

The risk calculation needs a read-only `as_of_date` exposure projection:

```text
current exposure
  = outstanding principal
  + finalized unpaid interest
  + previewed but unfinalized interest due through as_of_date
  + outstanding eligible fees (if policy says fees participate)
```

The calculation must reuse the canonical event fold and accrual-preview rules.
It must not create accrual events, vouchers, outboxes, or journal entries merely
to render a dashboard. The output must separate recorded amounts from previewed
amounts so reports do not misrepresent projected interest as posted accounting.
The current implementation details and limitations are documented in
[PawnLoan Interest Calculation Internals](../implementation/pawn-loan-interest-calculation.md).

## Proposed Current Collateral Value

For each in-scope collateral item, resolve one explicit monitoring method:

- calculated metal value from the latest eligible Rates facade buying rate,
  net weight, and purity;
- latest eligible approved appraisal; or
- lower of calculated metal value and appraisal.

Aggregate only collateral still legally and physically securing the loan.
Return the rate/appraisal timestamp, age, source, and missing/stale state with
the value. The monitoring policy may differ from the origination snapshot, but
it must be effective-dated and identified in every result.

Suggested derived measures:

```text
current LTV       = current exposure / current collateral value
coverage surplus  = current collateral value - current exposure
LTV headroom      = current collateral value * monitoring LTV - current exposure
margin breach     = LTV headroom < 0
shortfall         = coverage surplus < 0
```

An LTV margin breach occurs before a full market-value shortfall when the
monitoring limit is below 100 percent. Both should remain visible.

## Efficient Portfolio Projection

Do not call the existing per-loan balance and accrual services in an N+1 loop.
Build a tenant-scoped batch selector that:

1. loads active loans, policy snapshots, collateral tranches, relevant events,
   repayments, and finalized accrual evidence in bounded queries;
2. obtains one rate snapshot per required metal/currency/purity and records a
   rate watermark;
3. folds balances and previews pending interest through one shared pure
   calculation boundary;
4. values each item and aggregates loan-level exposure and coverage in memory;
5. returns immutable read models for filtering and export.

For large portfolios, maintain a rebuildable **risk projection** keyed by loan
and as-of date. Refresh affected rows when a rate is published, a loan event is
recorded/reversed, an appraisal is approved, collateral custody changes, or the
business date advances. The projection is a cache/read model only: commands,
notices, and auctions must recalculate and freeze current evidence before acting.

## Alerts And Filtering

The future worklist should support independent filters for:

- maturity overdue;
- LTV margin breach;
- full collateral shortfall;
- appraisal/rate missing or stale;
- days past maturity;
- current LTV and headroom bands;
- valuation and exposure as-of timestamps.

Alerts should be idempotent per loan plus valuation/rate/exposure fingerprint.
A later rate recovery should resolve the current projection without deleting
historical alert evidence. Customer notices and recovery authority require a
separate policy decision; an internal shortfall alert must not automatically
become an overdue or auction notice.

## Acceptance Questions Before Implementation

1. Does “amount due” include unfinalized partial-period interest and fees?
2. Is the breach threshold 100% market coverage, the frozen origination LTV,
   or a separately configurable monitoring LTV?
3. Does a margin breach make a loan legally overdue, or only operationally at
   risk until notice/cure rules are satisfied?
4. Which custody states continue securing the loan?
5. How old may a rate or appraisal be before the result becomes unknown/stale?
6. What borrower notice, cure period, additional-collateral, repayment, and
   auction rights follow each signal?
7. How frequently must the portfolio projection refresh, and what portfolio
   size must it support?
