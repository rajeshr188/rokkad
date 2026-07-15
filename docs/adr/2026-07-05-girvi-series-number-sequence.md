---
status: accepted
owner: girvi
updated: 2026-07-05
tags: [adr, girvi, numbering, sequence, license, series]
related: [../apps/girvi/models.md, ../apps/girvi/workflows.md, ../plans/girvi-number-sequence-migration-plan.md]
---

# ADR: Girvi Series-Scoped Number Sequences

Date: 2026-07-05
Status: Accepted

## Summary

Girvi should keep the domain relationship `License -> Series -> Loan/Release`, but document number allocation should move from scan-based loan/release ID generation to locked sequence rows scoped by `Series` and `document_kind`.

The accepted target is:

```text
License
  -> Series
      -> GirviNumberSequence(document_kind=GIVEN_LOAN)
      -> GirviNumberSequence(document_kind=TAKEN_LOAN)
      -> GirviNumberSequence(document_kind=GIVEN_LOAN_RELEASE)
      -> GirviNumberSequence(document_kind=TAKEN_LOAN_SETTLEMENT)
      -> GivenLoan / TakenLoan / Release / settlement documents
```

## Context

Current Girvi numbering derives the next loan ID by locking a `Series`, scanning existing `GivenLoan` and `TakenLoan` rows for that series, parsing numeric suffixes, and returning max plus one.

This works for low volume, but it makes existing documents the source of truth for the next number and leaves future numbering rules hard to express. DEA voucher numbering already uses a better pattern: a locked sequence row (`VoucherNumberSequence`) stores the allocation state and increments atomically.

Girvi needs separate numbering channels for:

- Given loans
- Taken loans
- Given-loan releases
- Taken-loan settlement/collateral-return documents, if/when represented as first-class documents

## Decision

1. Keep `License -> Series -> Loan/Release` as the business/compliance relationship.
2. Treat `Series` as the business/register/control bucket, not the long-term owner of number allocation state.
3. Introduce a sequence-row concept under `Series` with one row per `document_kind`.
4. Move long-term numbering fields such as `prefix`, `width`, and `next_number` to the sequence row.
5. Keep existing `Series.prefix` and `Series.max_limit` temporarily as compatibility fields during migration.
6. Allocation should lock the sequence row, format the number, increment `next_number`, and save the target document in one transaction.
7. Preview should not consume a number.
8. Manual legacy IDs are allowed during migration/import, but generated IDs should advance from the highest existing numeric suffix plus one.
9. Deleting a saved draft should not rewind by default. Admin-only rewind may be allowed only for the last unused draft number with no side effects.

## Target Responsibilities

`Series` owns:

- License/register grouping
- Operational activation
- Guardrail thresholds
- Deactivation rule and status
- Reporting grouping

`GirviNumberSequence` owns:

- `document_kind`
- `prefix`
- `width`
- `next_number`
- allocation/preview behavior
- sequence edit audit metadata

## Document Kinds

Initial target kinds:

- `GIVEN_LOAN`
- `TAKEN_LOAN`
- `GIVEN_LOAN_RELEASE`
- `TAKEN_LOAN_SETTLEMENT`

Use `TAKEN_LOAN_SETTLEMENT` instead of `TAKEN_LOAN_RELEASE` unless the business later defines a true release document for taken loans.

## Rationale

This preserves Girvi's license and series reporting while improving allocation safety. It also supports future numbering rules such as different prefixes per document kind, annual reset, branch/counter-specific sequences, manual legacy ranges, and audit-friendly sequence adjustments.

## Consequences

Positive:

- Safer concurrent creation.
- Clearer sequence auditability.
- No need to scan and parse all existing loans for every allocation.
- Multiple document numbering channels can exist under one series.

Costs:

- Requires a tenant migration.
- Requires a backfill/sync step from existing loans and releases.
- Requires compatibility handling while old `Series.prefix` and `Series.max_limit` still exist.
- Requires UI/admin controls for guarded sequence edits.

## Migration Direction

Implement through the phased plan in [../plans/girvi-number-sequence-migration-plan.md](../plans/girvi-number-sequence-migration-plan.md).
