---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# GivenLoan Posting Orchestration Plan

## Purpose

Document a focused plan to centralize all `GivenLoan` posting payload construction and DEA voucher/rule selection in one Girvi service.

This plan should make loan accounting flows:
- consistent across repayment, release, auction and sale transitions
- easier to review and test
- simpler to migrate to the future event-driven model

## Background

Current state:
- `apps/tenant_apps/girvi/service_modules/payment.py` contains multiple loan posting helpers.
- `apps/tenant_apps/girvi/service_modules/release_lifecycle.py` and transition commands call those helpers directly.
- `record_loan_release`, `record_loan_auction`, `record_loan_sale`, and repayment posting are handled in separate paths.
- DEA posting rules already exist for `GIVENLOAN_RELEASE`, `GIVENLOAN_AUCTION`, and `GIVENLOAN_SOLD`.

Problem:
- loan accounting behavior is scattered across multiple modules.
- rule selection and payload normalization are duplicated or implicit.
- this increases regression risk when adding new lifecycle transitions or loan events.

## Goal

Create a single Girvi loan posting orchestrator with a small, explicit API for `GivenLoan` events.

That orchestrator should:
1. accept loan domain context and event intent
2. normalize payment payloads for DEA
3. choose the correct voucher type and marker
4. call DEA facade methods consistently
5. provide a single integration point for all current and future `GivenLoan` posting flows

## Scope

### In scope
- `GivenLoan` repayment receipts
- `GivenLoan` release settlement receipts
- `GivenLoan` auction recovery receipts
- `GivenLoan` collateral sale recovery receipts
- `GivenLoan` disbursal/recovery if applicable
- idempotency marker construction
- voucher type selection and classification

### Out of scope for this document
- `TakenLoan` posting
- event bus implementation
- non-loan DEA posting rules

## Recommended location

`apps/tenant_apps/girvi/service_modules/loan_posting.py`

This new module should house posting-specific orchestration only.
Other Girvi lifecycle services should delegate to it.

## Desired API

Example service class:

```python
class GivenLoanPostingService:
    def post_repayment(self, loan: GivenLoan, payment_payload, user):
        ...

    def post_release(self, release: Release, user):
        ...

    def post_auction_recovery(self, loan: GivenLoan, amount, user):
        ...

    def post_sale_recovery(self, loan: GivenLoan, amount, user):
        ...
```

Example payload contract for `post_repayment`:
- `principal_amount`
- `interest_amount`
- `total_amount`
- `payment_date`
- `payment_method`
- `reference_number`
- `is_final_payment`

## Implementation steps

1. Create `apps/tenant_apps/girvi/service_modules/loan_posting.py`.

2. Implement the posting orchestrator with these helper methods:
   - `_build_payment_marker(...)`
   - `_choose_voucher_type(...)`
   - `_normalize_money_payload(...)`
   - `_create_and_post_payment(...)`

3. Keep the service lean: do not include loan lifecycle transition logic.
   - business transitions remain in `release_lifecycle.py` / command handlers
   - this service only handles the accounting side of `GivenLoan` events

4. Refactor existing helpers to delegate to the new service:
   - `record_loan_release` â†’ `GivenLoanPostingService.post_release`
   - `record_loan_auction` â†’ `GivenLoanPostingService.post_auction_recovery`
   - `record_loan_sale` â†’ `GivenLoanPostingService.post_sale_recovery`
   - repayment flow in `loanpayment.py` â†’ `GivenLoanPostingService.post_repayment`

   Note: `post_release()` must pass `create_release=True` so DEA classifies the payment as `GIVENLOAN_RELEASE`, while `post_repayment()` leaves `create_release=False` and remains a generic loan receipt.

5. Update transition commands in `apps/tenant_apps/girvi/transitions/commands.py` to import and call the service instead of low-level helpers.

6. Keep the existing DEA facade unchanged. The service should call:
   - `create_and_post_payment(...)`
   - `post_payment_voucher(...)`

7. Add a compatibility faÃ§ade in `apps/tenant_apps/girvi/service_modules/__init__.py` if necessary,
   to avoid a large import churn in tests/views during the first refactor.

## Rule selection matrix

| Action | Voucher type | create_release | DEA helper |
|---|---|---|---|
| GivenLoan repayment | `GIVENLOAN_RECEIPT` | False | `post_repayment` |
| GivenLoan release | `GIVENLOAN_RELEASE` | True | `post_release` |
| GivenLoan auction | `GIVENLOAN_AUCTION` | False | `post_auction_recovery` |
| GivenLoan sale | `GIVENLOAN_SOLD` | False | `post_sale_recovery` |

> `create_release=True` is the distinguishing signal for release receipts. Without it, a release payment would be classified as a generic `GIVENLOAN_RECEIPT`.

## Service dependency map

This section shows how Girvi posting flows connect the user-facing lifecycle actions to the shared posting orchestrator.

```text
views/loanpayment.py
    â””â”€> GivenLoanPostingService.post_repayment()

release_lifecycle.py
    â””â”€> payment.record_loan_release()
           â””â”€> loan_posting.GivenLoanPostingService.post_release()

bulk_release.py
    â””â”€> ReleaseLifecycleService
           â””â”€> payment.record_loan_release()
                  â””â”€> loan_posting.GivenLoanPostingService.post_release()

payment.py
    â””â”€> wrapper faÃ§ade around loan_posting service
```

### Why this map matters

- `payment.py` is the integration boundary for Girvi loan accounting semantics.
- `loan_posting.py` is the central service that normalizes payloads and selects DEA voucher types.
- `release_lifecycle.py` and `bulk_release.py` are workflow orchestrators that own loan state changes, not accounting details.

## Why `GivenLoan` should not inherit `BusinessDoc`

A `GivenLoan` is a loan contract, not an accounting event.

- `BusinessDoc` is a DEA abstraction for documents that directly produce vouchers and journal entries.
- For loans, the accounting events are separate DEA documents: `PaymentVoucher`, `VoucherLine`, and `JournalEntry`.
- The `GivenLoan` row is the source business contract; it owns a `GenericRelation` to `PaymentVoucher` but does not itself represent the posted ledger entry.
- Keeping `GivenLoan` outside `BusinessDoc` preserves the Girvi/DEA boundary and avoids dead inheritance behavior such as disabled `auto_post_to_accounting`.

This is why the future design should centralize posting in a dedicated service rather than rely on model inheritance.

## DB architecture: GivenLoan â†’ DEA accounting documents

### Loan model relations

- `GivenLoan` remains the business object in `apps/tenant_apps/girvi`.
- It is linked to DEA payments through a `GenericRelation` on `PaymentVoucher`.
- `PaymentVoucher` is the source accounting document for loan cash flows.

### Posting flow

1. `GivenLoan` lifecycle action occurs (repayment, release, auction, sale).
2. Girvi posting orchestrator creates or reuses a `PaymentVoucher`.
3. The DEA facade posts the `PaymentVoucher` using the posting engine.
4. Posting engine uses the voucher type to select the correct rule.
5. The rule produces or materializes one or more `VoucherLine` rows.
6. The engine materializes a `JournalEntry` and `LedgerTransaction` rows from those lines.

### Why this topology handles edits safely

- `GivenLoan` edits do not directly alter accounting entries. Changes to loan state are separate from posted vouchers.
- Posted `PaymentVoucher` entries are immutable in the ledger path once they are posted.
- Edits to loan state that require accounting correction are handled by posting reversal vouchers or new correction vouchers, not by mutating the original posted lines.
- This preserves auditability and keeps the contract table decoupled from the journal tables.

### Practical edit behavior

- If a repayment is changed after posting, the system should create a reversal payment voucher or a correcting voucher.
- The original `JournalEntry` remains as historical accounting evidence.
- The loan can still be updated to reflect the corrected balance, while the DEA posting service handles the accounting correction separately.

## Idempotency strategy

Use deterministic markers for each event type:
- release: `RELEASE-{release.pk}`
- auction: `AUCTION-{loan.pk}`
- sale: `SOLD-{loan.pk}`
- repayment: `REPAYMENT-{loan.pk}-{payment_id}` or `REPAYMENT-{reference_number}`

Markers should be enforced by the DEA facade by searching existing `PaymentVoucher`
for the same `source_document` and `reference_number` before creating a new payment.

## Testing checklist

- `GivenLoanPostingService.post_repayment` selects `GIVENLOAN_RECEIPT` and posts correctly.
- `GivenLoanPostingService.post_release` selects `GIVENLOAN_RELEASE` and posts correctly.
- `GivenLoanPostingService.post_auction_recovery` selects `GIVENLOAN_AUCTION`.
- `GivenLoanPostingService.post_sale_recovery` selects `GIVENLOAN_SOLD`.
- Existing `ReleaseLifecycleService` tests are updated to patch the new service.
- Transition command tests patch `GivenLoanPostingService` instead of service module helpers.
- Idempotent re-posting returns an existing `PaymentVoucher` instead of creating duplicates.

## Migration path to event-driven posting

Once the service is central, the next step is to split:
1. `GivenLoanPostingService` becomes a transaction boundary for event emission.
2. Girvi lifecycle writes loan state and publishes a loan event.
3. a DEA consumer consumes the loan event and invokes the same service interface or an adapter.

This means the service should be designed with a clear runtime boundary and a pure payload contract.

## Next steps

1. [x] Implement `apps/tenant_apps/girvi/service_modules/loan_posting.py` with the defined API.
2. [x] Refactor `apps/tenant_apps/girvi/service_modules/payment.py` to delegate release/auction/sale methods into the new service.
3. [x] Update `apps/tenant_apps/girvi/views/loanpayment.py` to use `GivenLoanPostingService.post_repayment()`.
4. [ ] Run and extend tests to cover idempotent posting, release accounting, and fallback for fake loan objects.
   - Existing transition command tests now patch `GivenLoanPostingService`.
   - Existing release lifecycle tests still patch the payment helper boundary.
   - A dedicated `GivenLoanPostingService` regression suite should be added for explicit idempotency and fake loan fallback coverage.
5. [ ] Once stable, revise the service into a clean event-driven adapter boundary.

## Stage 1 and Stage 2 Patch Plan

### Stage 1: Posting boundary cleanup

1. Create a new adapter module:
   - File: `apps/tenant_apps/girvi/service_modules/posting_adapter.py`
   - Export a thin Girvi-to-DEA adapter API containing:
     - `create_and_post_voucher_for_doc(...)`
     - `post_payment_voucher(...)`
     - `reverse_payment_by_marker(...)`
     - `has_other_posted_payments(...)`
   - Internally import from `apps.tenant_apps.dea.facade`.

2. Refactor `apps/tenant_apps/girvi/service_modules/loan_posting.py`:
   - Keep `GivenLoanPostingService` as the single orchestrator.
   - Replace direct DEA facade imports with adapter imports from `posting_adapter.py`.
   - Add helper methods for:
     - `_normalize_money(...)`
     - `_build_payment_marker(...)`
     - `_choose_voucher_type(...)`
     - `_create_and_post_payment(...)`
   - Preserve the public methods:
     - `post_repayment(...)`
     - `post_release(...)`
     - `post_auction_recovery(...)`
     - `post_sale_recovery(...)`
   - Ensure `post_repayment` supports loan-like objects by validating `loan.create_payment` and falling back to existing voucher creation semantics.
   - Ensure `post_release` creates `RELEASE-{release.pk}` marker and returns `(payment, created)` or `(None, False)` when no receipt is needed.

3. Refactor `apps/tenant_apps/girvi/service_modules/payment.py`:
   - Keep `record_loan_disbursal(...)` unchanged.
   - Replace the legacy internal `_record_givenloan_recovery_payment(...)` helper by delegating auction/sale posting through `GivenLoanPostingService` only.
   - Keep `record_loan_release(...)` as a single-line delegation to `GivenLoanPostingService().post_release(...)`.
   - Keep `record_loan_auction(...)` and `record_loan_sale(...)` delegations to `GivenLoanPostingService`.
   - Keep reverse methods unchanged.
   - Keep `create_and_post_voucher_for_doc = create_and_post_payment` as the compatibility alias.

4. Add compatibility exports:
   - File: `apps/tenant_apps/girvi/service_modules/__init__.py`
   - Export `GivenLoanPostingService` and the existing `payment` faÃ§ade symbols used by legacy imports.
   - This keeps import churn low while new code migrates to the service boundary.

5. Update any one-off call sites as part of Stage 1 only if they already reference the new service:
   - `apps/tenant_apps/girvi/views/loanpayment.py` should already call `GivenLoanPostingService.post_repayment`.
   - No further workflow refactor is needed in Stage 1.

### Stage 2: Workflow / command separation

1. Refactor transition command posting boundaries in `apps/tenant_apps/girvi/transitions/commands.py`:
   - Keep `MarkAuctionedTransitionCommand` and `MarkSoldTransitionCommand` as state-transition commands.
   - Extract the accounting post-step into a named helper method inside the module, e.g. `_post_recovery_payment(...)`.
   - Have the command execute state transition first, then call `GivenLoanPostingService().post_auction_recovery(...)` or `post_sale_recovery(...)`.
   - Keep the atomic block that includes both transition and posting, but separate the domain transition code from the posting invocation for clarity.
   - Example intended migration:
     - `transition_method(**payload_kwargs)` updates loan status.
     - If loan reaches the expected final status, call the service.
     - Build the user-facing success message from the returned `(payment, created)` tuple.

2. Consider a dedicated orchestration helper for transition posting:
   - File: `apps/tenant_apps/girvi/service_modules/transition_posting.py` (optional)
   - Expose:
     - `post_auction_recovery_for_transition(loan, amount, user)`
     - `post_sale_recovery_for_transition(loan, amount, user)`
   - This keeps `commands.py` focused on transition semantics and makes reuse easier if any other module later needs the same post-transition behavior.
   - If added, update `commands.py` to import from `transition_posting.py` instead of calling `GivenLoanPostingService` directly.

3. Keep `apps/tenant_apps/girvi/service_modules/release_lifecycle.py` focused on workflow:
   - Leave the existing `record_loan_release(release, created_by=...)` call in place.
   - Do not add additional DEA posting logic into lifecycle decisions.
   - If needed, rename local variables to clarify that release lifecycle is a workflow step and the payment returned is an accounting artifact.

4. Update unit tests to match the new boundary:
   - Add or update `apps/tenant_apps/girvi/tests/test_loan_posting_service.py` to cover:
     - `post_repayment` chooses `GIVENLOAN_RECEIPT` and uses the adapter.
     - `post_release` returns `(None, False)` when outstanding is zero.
     - `post_auction_recovery` and `post_sale_recovery` return idempotent results.
     - marker reuse and fake loan fallback semantics.
   - Update existing `apps/tenant_apps/girvi/tests/test_transitions.py` or equivalent to patch `apps.tenant_apps.girvi.transitions.commands.GivenLoanPostingService` (or the new transition posting helper), not legacy `payment` helpers.
   - Update release lifecycle tests to patch `record_loan_release` when verifying workflow only.

### Precise edits by file

- `apps/tenant_apps/girvi/service_modules/posting_adapter.py`
  - Create new file with adapter wrapper implementation and exports.
- `apps/tenant_apps/girvi/service_modules/loan_posting.py`
  - Replace DEA facade imports with adapter imports.
  - Add helper methods for marker, voucher type, normalization, and posting.
- `apps/tenant_apps/girvi/service_modules/payment.py`
  - Remove internal recovery helper duplication.
  - Keep disbursal and reverse helpers unchanged.
  - Delegate release/auction/sale creation to `GivenLoanPostingService`.
- `apps/tenant_apps/girvi/service_modules/__init__.py`
  - Add compatibility exports for `GivenLoanPostingService` and old payment helpers.
- `apps/tenant_apps/girvi/transitions/commands.py`
  - Refactor `MarkAuctionedTransitionCommand.execute` and `MarkSoldTransitionCommand.execute` to use the new service boundary cleanly.
- `apps/tenant_apps/girvi/tests/test_loan_posting_service.py`
  - Add dedicated service-level regression coverage.

## References

- `apps/tenant_apps/girvi/service_modules/payment.py`
- `apps/tenant_apps/girvi/service_modules/release_lifecycle.py`
- `apps/tenant_apps/girvi/transitions/commands.py`
- `apps/tenant_apps/dea/facade.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_release.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_auction.py`
- `apps/tenant_apps/dea/posting/rules/givenloan_sold.py`
- `apps/tenant_apps/girvi/docs/loan/REPAYMENT_RELEASE_EVENT_MATRIX.md`

