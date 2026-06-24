---
status: active
owner: dea
updated: 2026-06-24
tags: [implementation, dea, accounting, reversal, correction, lifecycle]
related:
  - ../constitution.md
  - ../domain/accounting.md
  - ../adr/2026-06-24-dea-document-voucher-journal-lifecycle.md
  - ../implementation/dea-canonical-posting-path.md
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - ../audits/dea_core_accounting_commodity_analysis.md
---

# DEA Reversal And Correction Service Contract

## Purpose

This document defines the target service contract for reversing and correcting DEA accounting effects.

It is the implementation contract for Phase 2 Task 2.5 of the DEA commodity-accounting refactor. It does not implement the service yet. The goal is to make reversal/correction semantics explicit before replacing current engine/view/facade reversal paths.

## Current State

Current reversal and correction behavior is spread across several paths:

| File / object | Current behavior | Contract status |
|---|---|---|
| `apps/tenant_apps/dea/posting/engine.py::BasePostingEngine.reverse_voucher` | Finds latest journal entry, creates reversing journal entry under the same voucher, marks voucher `REVERSED`. | Current canonical runtime helper, but should move behind a service boundary. |
| `apps/tenant_apps/dea/posting/engine.py::BasePostingEngine._reverse_journal_entry` | Creates reversing ledger/account rows by swapping ledgers and account transaction side. | Useful low-level primitive, but should not be public workflow API. |
| `apps/tenant_apps/dea/posting/engine.py::BasePostingEngine.post` | If a new voucher has changed economic payload for same source doc/type, reverses previous voucher and posts new voucher. | Current correction path; needs clearer service orchestration and status semantics. |
| `apps/tenant_apps/dea/services/post_doc.py::create_and_post_voucher_for_doc` | Creates replacement voucher with `corrected_from=prev_voucher` when payload changed. | Current source-document correction entrypoint. |
| `apps/tenant_apps/dea/views/voucher.py::reverse_voucher` | Legacy direct view reversal with `_create_reversal_journal_entry()`. | Non-canonical; replace with service call. |
| `apps/tenant_apps/dea/facades/payments.py::reverse_payment_by_marker` | Finds posted accounting voucher, calls `DjangoPostingEngine().reverse_voucher()`, then toggles `PaymentVoucher.posted=False`. | Needs service-backed state synchronization. |
| `apps/tenant_apps/dea/posting/legacy_direct_write_engine.py` | Older duplicate reversal/correction implementation. | Legacy; do not extend. |

## Decision

DEA should introduce one reversal/correction service module:

```text
apps/tenant_apps/dea/services/reversal.py
```

Target public API:

```python
reverse_posted_voucher(
    *,
    voucher,
    actor,
    reason: str,
    reversal_date=None,
    source_action: str = "manual_reversal",
)

correct_posted_document(
    *,
    source_document,
    actor,
    reason: str,
    corrected_payload=None,
    voucher_type_input=None,
)
```

The service owns workflow semantics. The posting engine may still own low-level journal materialization and line reversal primitives.

## Definitions

### Reversal

A reversal negates a posted voucher's accounting effects.

Use reversal when:

- a posted document was entered in error,
- a posted payment/receipt must be voided,
- a duplicate posted document must be neutralized,
- a source business event is cancelled after posting,
- an old posting must be neutralized before a corrected posting.

Reversal does not edit the original journal rows. It creates new opposite journal rows.

### Correction

A correction supersedes a posted economic payload with a corrected economic payload.

Correction means:

1. Reverse the original posted effects.
2. Create a new corrected source document or corrected voucher.
3. Post the corrected effects.
4. Link the corrected voucher to the original using `corrected_from`.

Correction is not an in-place update of posted accounting records.

### Amendment

An amendment changes non-economic metadata only.

Examples:

- typo in narration,
- external reference note,
- attachment update,
- internal review note.

Amendments need audit trail but no reversal or new journal entry.

## Voucher And Journal Status Semantics

| Object | State / link | Meaning |
|---|---|---|
| Original voucher | `POSTED` | Active accounting effect. |
| Original voucher after manual reversal | `REVERSED` | Its effect was negated by reversing journal entry. |
| Original voucher after correction | `REVERSED` for current compatibility; target label may become `CORRECTED` after UI/status cleanup. |
| Corrected voucher | `POSTED`, `corrected_from=original_voucher` | Active replacement accounting effect. |
| Original journal entry | `is_reversal_of=None` | Original posted effect. |
| Reversal journal entry | `is_reversal_of=original_journal_entry` | Opposite effect. |
| Commodity movement, future | `reversal_of=original_movement` or opposite movement link | Opposite metal effect. |

Current code uses `VoucherStatus.REVERSED` for previous voucher superseded by correction. This is acceptable for the MVP compatibility path, but the UI should make the difference visible through `corrected_from` and replacement links.

## Service Responsibilities

The reversal/correction service must:

- run in a tenant schema only,
- run inside `transaction.atomic()`,
- lock the target voucher before reversing/correcting,
- validate voucher status,
- validate period policy,
- create reversal journal entry with opposite ledger/account rows,
- preserve source document/voucher/journal traceability,
- record actor, timestamp, and reason,
- prevent duplicate reversal of the same active voucher,
- return a structured result object,
- eventually reverse commodity sidecar movements in the same transaction.

The service must not:

- mutate posted original journal rows,
- mutate posted original ledger/account transaction rows,
- delete posted accounting rows,
- post commodity quantity into `LedgerTransaction`,
- live in views/templates,
- depend on user-facing message strings.

## Proposed Result Objects

Use simple dataclasses or typed objects when implemented:

```python
@dataclass(frozen=True)
class ReversalResult:
    original_voucher: Voucher
    reversal_journal_entry: JournalEntry | None
    original_journal_entry: JournalEntry | None
    status_before: str
    status_after: str
    already_reversed: bool = False


@dataclass(frozen=True)
class CorrectionResult:
    original_voucher: Voucher
    corrected_voucher: Voucher
    reversal_journal_entry: JournalEntry | None
    corrected_journal_entry: JournalEntry
    original_status_after: str
```

## Proposed API Details

### `reverse_posted_voucher()`

Input:

- `voucher`: posted `Voucher` instance or id.
- `actor`: user performing reversal.
- `reason`: required non-empty reason.
- `reversal_date`: optional; default current date or current open period policy.
- `source_action`: machine-readable action, such as `manual_reversal`, `payment_void`, `correction_supersede`.

Expected behavior:

1. Lock voucher with `select_for_update()`.
2. Reject `DRAFT` vouchers.
3. If voucher is already `REVERSED`, return idempotent `already_reversed=True` result or raise based on caller policy. MVP recommendation: return idempotent result for service callers, show message in UI.
4. Reject voucher with no original journal entry unless a documented no-op reversal policy exists.
5. Resolve reversal period.
6. Create reversal journal entry linked by `is_reversal_of`.
7. Create reversed `LedgerTransaction` rows.
8. Create reversed `AccountTransaction` rows.
9. Reverse future commodity movement rows if the original voucher has commodity effects.
10. Mark voucher `REVERSED`.
11. Log audit event.
12. Return `ReversalResult`.

### `correct_posted_document()`

Input:

- `source_document`: business document or source event.
- `actor`: user performing correction.
- `reason`: required non-empty reason.
- `corrected_payload`: optional domain-specific payload if correction creates/updates a corrected document.
- `voucher_type_input`: optional override.

Expected behavior:

1. Lock source document/event when practical.
2. Find latest active posted voucher for source document/type.
3. Compute corrected economic fingerprint.
4. If fingerprint unchanged, return existing voucher/journal entry as idempotent no-op.
5. Reverse previous active voucher through `reverse_posted_voucher(source_action="correction_supersede")`.
6. Create corrected voucher with `corrected_from=original_voucher`.
7. Post corrected voucher through canonical posting path.
8. Return `CorrectionResult`.

The existing `create_and_post_voucher_for_doc()` currently performs part of this behavior. Future implementation can either call the new correction service from `post_doc.py` or move the correction orchestration into `services/reversal.py` while keeping `post_doc.py` as a facade.

## Period Policy

Reversal period handling must be explicit.

MVP policy:

- If original voucher period is open, reversal may use original voucher date/period.
- If original voucher period is closed or locked, reversal must use a current open period and preserve `reverses_original_period` metadata in audit payload or future fields.
- Never mutate closed-period journal entries in place.
- Never bypass `AccountingPeriod.can_modify_transactions()` for new reversal entries.

Needs implementation decision:

- Whether the current schema needs an explicit reversal date field on the reversal journal entry or whether `posted_at` plus `period` is sufficient for MVP.

## Idempotency Rules

Reversal idempotency:

- Reversing an already reversed voucher should not create another reversal journal entry.
- A voucher should have at most one active reversal journal entry for a given original journal entry.
- Service should detect `voucher.journal_entries.filter(is_reversal_of=original_je).exists()`.

Correction idempotency:

- Correcting with unchanged economic payload should return existing posted voucher.
- Correcting with changed economic payload should create one replacement voucher.
- Retrying the same correction should return the replacement voucher, not create another replacement.

Suggested future keys:

- reversal dedupe key: `reversal:{voucher_id}:{original_je_id}:{source_action}`
- correction dedupe key: existing economic fingerprint plus `corrected_from`

## Audit Requirements

Each reversal/correction should record:

- actor,
- timestamp,
- reason,
- source action,
- original voucher id,
- original journal entry id,
- reversal journal entry id,
- corrected voucher id when applicable,
- period used,
- whether original period was closed/locked,
- source document reference,
- future commodity movement ids when applicable.

Current `AccountingAuditEvent.EventType.VOUCHER_REVERSED` exists and should be used by the service implementation.

## Future Commodity Sidecar Rules

When commodity accounting is introduced:

- `CommodityMovement` rows are immutable after posting.
- Reversal creates opposite movement rows, not updates.
- Rate-fixing exposure changes are reversed through offset exposure/fixing rows.
- Commodity reversal must happen in the same transaction as financial reversal when a voucher has both effects.
- Financial valuation reversals remain monetary `JournalEntry` effects; metal quantity reversals remain commodity movement effects.

The service should be designed to call a future commodity reversal adapter:

```python
reverse_commodity_effects_for_voucher(
    voucher=original_voucher,
    actor=actor,
    reason=reason,
    source_action=source_action,
)
```

## Error Handling

Use domain exceptions rather than raw view messages:

```python
class ReversalError(Exception): ...
class VoucherNotPostedError(ReversalError): ...
class VoucherAlreadyReversedError(ReversalError): ...
class ReversalPeriodError(ReversalError): ...
class MissingOriginalJournalEntryError(ReversalError): ...
```

Views should translate these exceptions into messages. Services/facades should let callers decide whether to surface, retry, or fail closed.

## Tests Required For Implementation

| Test area | Required assertions |
|---|---|
| Manual reversal | Posted voucher reverses once, creates one reversal journal entry, marks voucher reversed. |
| Reversal idempotency | Reversing same voucher twice does not create duplicate reversal journal entries. |
| Reversal of draft | Draft voucher cannot be reversed. |
| Missing journal entry | Posted voucher without original journal entry fails clearly. |
| Period open | Open-period reversal posts into valid period. |
| Period closed | Closed original period uses current open period or fails according to explicit policy. |
| Account lines | AccountTransaction side is flipped correctly. |
| Ledger lines | LedgerTransaction debit/credit ledgers are swapped correctly. |
| Source links | Reversal preserves voucher/source-document/journal traceability. |
| Payment facade | `reverse_payment_by_marker()` uses service and synchronizes `PaymentVoucher.posted`. |
| View wrapper | `views/voucher.py::reverse_voucher` delegates to service and contains no materialization logic. |
| Commodity future | Commodity movement reversal tests once commodity models exist. |

## Migration / Refactor Steps

1. Add characterization tests for current engine reversal behavior.
2. Implement `apps/tenant_apps/dea/services/reversal.py` with `reverse_posted_voucher()`.
3. Route `DjangoPostingEngine.reverse_voucher()` through the new service or make it a compatibility wrapper.
4. Route `apps/tenant_apps/dea/facades/payments.py::reverse_payment_by_marker()` through the new service.
5. Route `apps/tenant_apps/dea/views/voucher.py::reverse_voucher()` through the new service.
6. Add idempotency guard against duplicate reversal journal entries.
7. Add audit logging for reversal and correction events.
8. Extract correction orchestration from `BasePostingEngine.post()` / `create_and_post_voucher_for_doc()` only after parity tests pass.
9. Delete direct reversal helper code from `views/voucher.py`.
10. Add future commodity reversal adapter when commodity models are introduced.

## Non-Goals

- Do not introduce commodity models in this task.
- Do not change database schema in this task.
- Do not rewrite posting engine in this task.
- Do not remove current reversal helpers until tests and service implementation exist.

## Next Task

After this contract, the next safe implementation slice is characterization tests for current reversal behavior, then a small `services/reversal.py` implementation that preserves current behavior while adding idempotency and a clean API.
