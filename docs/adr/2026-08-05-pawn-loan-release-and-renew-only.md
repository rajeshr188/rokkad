---
status: accepted
owner: project
updated: 2026-08-05
tags: [adr, loans, collateral, release, renewal, accounting, custody]
related: [2026-07-15-loans-rewrite-domain-and-cutover-architecture.md, 2026-08-05-pawn-loan-collateral-tranche-economics.md, ../plans/loans-rewrite-roadmap.md, ../domain/accounting.md, ../constitution.md]
supersedes: [2026-07-15 partial-release decision, 2026-08-05 collateral-tranche decision 11 partial-release clause]
---

# ADR: PawnLoan Release And Renew Only

## Context

The first Loans implementation allowed selected collateral to be returned while
the same PawnLoan stayed active. It calculated a minimum settlement from fees,
interest, and the principal reduction required to keep retained collateral
within LTV. The business does not use progressive collateral redemption under
one continuing contract.

Keeping that capability would make an active loan's ticket, collateral,
principal tranches, interest schedule, custody, Party history, customer portal,
notices, accounting explanation, and reversal dependencies change meaning over
time. The actual business operation closes the old contract and issues a newly
numbered loan for retained and optional additional collateral.

## Decision

1. PawnLoan supports three distinct actions:
   - partial repayment reduces dues and returns no collateral;
   - full release settles the complete loan, returns every remaining item, and
     closes it;
   - release and renew closes the source loan, returns selected items, transfers
     retained items, accepts optional additional collateral, and activates a
     newly numbered successor loan.
2. New partial collateral releases under the same active loan are prohibited at
   both HTTP and service boundaries.
3. Release and renew creates fresh item allocation, metal-rate, valuation/LTV,
   fee, advance-interest, approval, and opening evidence. It does not mutate or
   reinterpret the source loan's contract.
4. Source settlement and successor opening remain separate immutable business
   events. DEA may post their net cash consequence while retaining both gross
   facts and source links.
5. Retained collateral has explicit old-item to successor-item lineage. Removed
   collateral is returned to the customer. Additional collateral originates on
   the successor. Custody history records each category independently.
6. Full release and release-and-renew corrections use strict newest-first,
   administrator-only compensating reversals. Posted records are never edited.
7. Existing development partial-release documents remain historical,
   read-only, reportable, and reversible. No migration deletes or rewrites
   their immutable evidence. They do not authorize new partial releases.
8. The `is_full_release` compatibility field and historical partial status may
   remain until a later cleanup proves that no retained data depends on them.

## Consequences

- An active PawnLoan always describes one current contract whose collateral,
  principal allocations, rates, valuation, and ticket agree.
- Party history becomes an explicit source-to-successor timeline instead of one
  contract with changing collateral membership.
- The renewal workflow must be upgraded before it can fully replace partial
  release: its current implementation transfers every old item and cannot add
  collateral.
- Full-release settlement, numbering, documents, DEA posting, custody history,
  and reversal infrastructure remain valid.
- Partial-release retained-LTV calculations and mixed-custody states are removed
  from new operations, UI, and acceptance criteria.
- Auction recovery remains a separate collateral-disposal workflow and still
  requires immutable item-principal allocation evidence.

## Superseded Decisions

- The partial-release rules in the July 2026 Loans architecture ADR no longer
  apply to new PawnLoans.
- Decision 11 of the collateral-tranche ADR remains authoritative for general
  repayment allocation, but its selected-item partial-release clause is
  superseded by this ADR.

## Rejected Alternatives

- Keep partial release as an advanced option: rejected because an unused
  operational path still expands every balance, custody, document, portal,
  reporting, and reversal invariant.
- Model release and renew as an in-place edit: rejected because the business
  issues a new loan contract and number.
- Delete historical partial-release evidence: rejected because immutable source
  documents and accounting links must remain auditable.
