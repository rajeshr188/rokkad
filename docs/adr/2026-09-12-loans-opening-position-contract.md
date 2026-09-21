---
status: proposed
owner: project
updated: 2026-09-12
tags: [loans, portability, opening-position]
---

# Explicit migration opening with original billing terms

The owner authorized the opening-position contract review, suggested skipping very
old loans with incomplete collateral, and explicitly selected preservation of
existing billing dates and agreed interest rules for retained active loans.
The [contract](../contracts/loan-opening-position-mvp.md) records those constraints
and the proposed implementation. It does not claim a released opening importer or
approval of real financial balances, a specific disputed formula, or final skips.

Propose a distinct Loans-owned immutable migration opening rather than fabricated
disbursal/approval/repayment/accrual history. It records approved cutover balances,
per-item remaining principal/custody, remaining due obligations and original-period
interest continuation. Missing origination history is declared; post-cutover
servicing still uses canonical evidence and domain commands. Preserve original
loan/due dates. A partial billing period needs explicit already-recognized/covered
amounts and its original basis; cutover must not reset the month or double charge it.

Do not silently adopt current declining-principal/item-rounding calculations when
the source agreement differs. A reviewed named rule is required, with unsupported
loans held for review. No arbitrary formula engine is proposed. The strict existing
`loan-history/1` contract remains unchanged and cannot certify an opening as complete.

The reversible collateral exclusion proposal is implemented as an opt-in source
preview annotation under the [offline-preview decision](2026-09-12-offline-legacy-dump-preview.md).
It preserves every source row and keeps each skipped loan's child graph together.
Actual selection acceptance remains part of a future concrete financial preview.
Missing collateral and old age are not treated as interchangeable facts.

The [offline opening review format](../contracts/loan-opening-review-v1.md) is now
implemented as a bounded validation-only slice. Loans owns pure financial/date
reconciliation; data portability generates candidates from the selected dump and
writes local reports. Missing financial values remain null. Document reconciliation
never grants import readiness or authenticates edited source claims.

Following the owner's instruction to proceed, the event/read foundation is now
implemented and accepted within this otherwise proposed operational design:
`MIGRATION_OPENING` uses the existing immutable, forced-RLS `PawnLoanEvent`, with
a conditional unique constraint and frozen `loan-opening-evidence/1` review/item
mapping. Balance/tranche readers recognize the cutover, reject mixed origins and
keep imported amounts separate from new lending. No new evidence table is needed.
The generic event writer and native interest/financial-action guards reject opening
loans; the test fixtures are not an import command. Migration 0010 is exercised only
in the test database. Source authentication, authorization/idempotent commit,
accrual continuation, remaining obligations, servicing, correction and export must
be integrated and tested before operational activation. The review descriptor's
calendar checks do not themselves implement the owner's legacy collection rule.

The subsequent accepted [continuation decision](2026-09-12-opening-collection-continuation.md)
implements an explicit v2 checkpoint, collection exposure projection and reviewed
remaining-obligation persistence. It preserves original dates/grace and cumulative
rounding without activating financial posting or approving source balances. Version
1 remains unchanged. The broader operational design above remains proposed until
servicing, correction, export and actual import integration satisfy its gates.
