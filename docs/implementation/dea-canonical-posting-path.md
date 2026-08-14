---
status: active
owner: dea
updated: 2026-06-24
tags: [implementation, dea, accounting, posting, lifecycle]
related:
  - ../constitution.md
  - ../domain/accounting.md
  - ../adr/2026-06-24-dea-document-voucher-journal-lifecycle.md
  - ../roadmaps/dea_commodity_accounting_refactor_plan.md
  - ../audits/dea_core_accounting_commodity_analysis.md
---

# DEA Canonical Posting Path

## Purpose

This document defines the canonical DEA posting path for financial accounting effects.

It is the implementation contract for Phase 2 Task 2.4 of the DEA commodity-accounting refactor. The goal is to make one posting route authoritative before any large refactor of vouchers, commodity sidecars, business-event UI, or legacy view helpers.

## Decision

All accounting effects must flow through the posting command/engine path:

```text
Business document or explicit accounting voucher
  -> create_and_post_voucher_for_doc() or PostVoucherCommand
    -> DjangoPostingEngine.post()
      -> registered PostingRule.build_posting()
      -> PostingBundle validation
      -> sync_voucher_lines_from_bundle()
      -> materialize_journal_from_voucher_lines()
      -> Voucher status/fingerprint update
```

Direct view-level creation of `JournalEntry`, `LedgerTransaction`, or `AccountTransaction` is legacy and must not be extended.

## Canonical Components

| Component | File | Role |
|---|---|---|
| Document posting service | `apps/tenant_apps/dea/services/post_doc.py::create_and_post_voucher_for_doc` | Main service for posting source documents. It resolves voucher type, computes economic fingerprint, creates draft voucher, calls command, and returns voucher/journal entry. |
| Command boundary | `apps/tenant_apps/dea/posting/commands.py::PostVoucherCommand` | Thin command entrypoint for posting an existing voucher through the engine. |
| Posting engine | `apps/tenant_apps/dea/posting/engine.py::DjangoPostingEngine` | Authoritative posting executor. Locks voucher, validates period, computes fingerprint, applies idempotency/correction, runs posting rule, materializes effects, and updates voucher status. |
| Posting rules | `apps/tenant_apps/dea/posting/rules/*` | Convert source document/business facts into `PostingBundle` financial lines. |
| Posting validators | `apps/tenant_apps/dea/posting/validate.py` | Validate posting bundle shape, currency fields, and financial balance. |
| Voucher-line synchronization | `apps/tenant_apps/dea/services/materialize_journal.py::sync_voucher_lines_from_bundle` | Converts rule-generated posting bundles into canonical `VoucherLine` rows while voucher is still draft. |
| Journal materialization | `apps/tenant_apps/dea/services/materialize_journal.py::materialize_journal_from_voucher_lines` | Creates `JournalEntry`, `LedgerTransaction`, and `AccountTransaction` rows from voucher lines. |
| Reversal helper | `apps/tenant_apps/dea/posting/engine.py::BasePostingEngine.reverse_voucher` | Current canonical reversal executor until a dedicated reversal/correction service is introduced. |

## Allowed Entrypoints

### Source-document posting

Use this for business documents such as payment, expense, sales invoice, purchase invoice, depreciation, prepaid amortization, and future business-event documents:

```python
create_and_post_voucher_for_doc(
    doc=source_document,
    user=user,
    voucher_type_input=source_document.get_voucher_type(),
    engine=DjangoPostingEngine(),
)
```

This path is currently used by:

- `apps/tenant_apps/dea/facades/journals.py`
- `apps/tenant_apps/dea/facades/payments.py`
- `apps/tenant_apps/dea/views/expense.py`
- `apps/tenant_apps/dea/views/journal_entry_voucher.py`
- `apps/tenant_apps/dea/views/payment.py`
- `apps/tenant_apps/dea/services/depreciation.py`
- `apps/tenant_apps/dea/services/prepaid.py`
- `apps/tenant_apps/dea/models/doc.py::BusinessDoc._auto_post_to_accounting()` (legacy-risk path because save failures are swallowed)

### Existing-voucher posting

Use this for a draft `Voucher` that already exists and has either:

- a linked source document and registered posting rule, or
- draft voucher lines that can be materialized.

```python
PostVoucherCommand(DjangoPostingEngine()).execute(voucher, user)
```

Direct use of `DjangoPostingEngine().post(PostingContext(...))` is acceptable inside tests or low-level services, but application code should prefer the command/service boundary.

### Reversal

Current allowed reversal path:

```python
DjangoPostingEngine().reverse_voucher(voucher_id, user)
```

This is temporary. Phase 2 Task 2.5 should introduce a dedicated reversal/correction service contract and eventually route reversals through that service.

## Legacy Or Non-Canonical Paths

| File / object | Current behavior | Status | Required direction |
|---|---|---|---|
| `apps/tenant_apps/dea/views/voucher.py::post_voucher` | Performs view-level validation, calls `_create_journal_entry()`, and marks voucher posted. | Legacy | Replace body with command/service call after characterization tests. |
| `apps/tenant_apps/dea/views/voucher.py::reverse_voucher` | Performs view-level reversal using `_create_reversal_journal_entry()`. | Legacy | Replace with canonical reversal service/engine call. |
| `apps/tenant_apps/dea/views/voucher.py::_create_journal_entry` | Directly creates journal/transaction rows from view helper logic. | Legacy | Delete after view route is migrated and tests prove parity. |
| `apps/tenant_apps/dea/views/voucher.py::_create_reversal_journal_entry` | Directly creates reversing rows from view helper logic. | Legacy | Delete after reversal service is canonical. |
| `apps/tenant_apps/dea/posting/legacy_direct_write_engine.py` | Older duplicate implementation of posting/reversal behavior. | Legacy | Keep until no runtime/import callers; delete after tests and import audit. |
| `apps/tenant_apps/dea/models/doc.py::BusinessDoc.save()` | Auto-posts after save and logs/swallow failures. | Risky compatibility path | Disable/remove for meaningful runtime docs after explicit posting workflows exist. |
| `apps/tenant_apps/dea/models/payment.py::PaymentVoucher.posted` | Separate boolean state overlaps with `Voucher.status`. | Compatibility state | Reconcile in a later lifecycle cleanup so posted state is read from accounting voucher status. |

## Required Behavior

Canonical posting must:

- Run in a tenant schema, not the public schema.
- Lock the voucher row before posting.
- Validate accounting period openness inside the posting path.
- Use stable economic fingerprint payloads.
- Return existing effects for duplicate posts.
- Reverse previous effects before corrected reposting.
- Validate financial debit/credit balance before materialization.
- Create immutable `JournalEntry`, `LedgerTransaction`, and `AccountTransaction` rows.
- Update `Voucher.fingerprint`, `Voucher.last_posted_at`, and `Voucher.status` only after successful materialization.
- Fail atomically if posting, materialization, settlement, or required future sidecar effects fail.

Future commodity posting must extend this path by creating commodity sidecar effects inside the same atomic posting command. Commodity quantity must not be materialized into `LedgerTransaction`.

## Current Gaps

1. `views/voucher.py` still exposes direct materialization helpers.
2. `BusinessDoc.save()` still contains implicit auto-posting with swallowed failures.
3. Reversal and correction are still engine methods, not a dedicated service contract.
4. `PaymentVoucher.posted` still duplicates accounting state.
5. The direct manual voucher UI may not exercise the same validations as the canonical engine path.
6. `legacy_direct_write_engine.py` still exists and should be import-audited before removal.

## Refactor Plan

### Step 1: Characterize Current Voucher View Behavior

Add tests around:

- Draft manual voucher post route.
- Posted voucher reverse route.
- Permission expectations.
- Period-lock behavior.
- User-facing messages/redirects.
- Journal/ledger/account rows created by route.

These tests should document current behavior before replacing internals.

### Step 2: Route `post_voucher` Through Command

Replace direct view materialization with:

```python
PostVoucherCommand(DjangoPostingEngine()).execute(voucher, request.user)
```

The view should handle only:

- request method/permission,
- loading voucher,
- calling command,
- translating domain errors into messages,
- redirecting.

Posting logic must not remain in the view.

### Step 3: Route `reverse_voucher` Through Canonical Reversal

Temporarily route to:

```python
DjangoPostingEngine().reverse_voucher(voucher.pk, request.user)
```

Then replace with the Phase 2 Task 2.5 reversal/correction service once introduced.

### Step 4: Delete Legacy Helpers

After tests pass and no callers remain, delete:

- `_calculate_totals()`
- `_create_journal_entry()`
- `_create_reversal_journal_entry()`

If any helper still has behavior not covered by the engine, move that behavior into a service or posting rule first.

### Step 5: Import Guard

Add an architecture/import test that prevents runtime code from importing:

- `apps.tenant_apps.dea.posting.legacy_direct_write_engine`

Allow it only in explicit archive/compatibility tests until deletion.

## Tests Required Before Code Refactor

| Test area | Required assertions |
|---|---|
| Voucher post route | Route posts a draft voucher through command/engine and creates one journal entry. |
| Voucher duplicate post | Posted voucher route does not duplicate journal entries. |
| Voucher reverse route | Route creates reversal through canonical reversal path and marks voucher reversed. |
| Period lock | Closed/locked period blocks route through engine error. |
| Permission | Non-accountant users cannot post/reverse if policy requires accountant/admin. |
| Error handling | Posting errors show user-facing message and do not create partial rows. |
| Import guard | Runtime code does not import legacy direct-write engine. |

## Non-Goals

- Do not introduce commodity models in this step.
- Do not redesign voucher UI in this step.
- Do not remove `BusinessDoc.save()` auto-posting until explicit replacement workflows are covered.
- Do not remove legacy direct-write engine until import audit and tests prove it is unused.

## Next Task

Proceed to Phase 2 Task 2.5: define the reversal/correction service contract. That contract should specify the replacement API for `DjangoPostingEngine().reverse_voucher()` and the future commodity movement reversal rules.
