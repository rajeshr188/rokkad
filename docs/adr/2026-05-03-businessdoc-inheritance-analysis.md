---
status: accepted
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# ADR: BusinessDoc Inheritance â€” Analysis and Decoupling Plan

**Date:** 2026-05-03  
**Status:** Accepted  
**Owners:** Platform Architecture, Girvi Team, DEA Team  
**Affected Apps:** `girvi`, `dea`

---

## Context

`BusinessDoc` is an abstract Django model in `dea/models/doc.py`. It was introduced
as a shared base for any model that represents a business event which generates
accounting entries (vouchers â†’ journal entries â†’ ledger/account transactions).

Several models were made to inherit it:

| Model | Location | Inherits |
|---|---|---|
| `PaymentVoucher` | `dea/models/payment.py` | `BusinessDoc` |
| `JournalEntryVoucher` | `dea/models/journal_entry.py` | `BusinessDoc` |
| `BaseLoan` (abstract) | `girvi/models/loan_refactored.py` | `BusinessDoc` |
| `Loan` (legacy) | `girvi/models/loan.py` | `BusinessDoc` |
| `LoanPayment` (legacy) | `girvi/models/loan.py` | `BusinessDoc` |

Sales (`Invoice`) and Purchase models do **not** inherit `BusinessDoc`.

### What BusinessDoc provides

```python
class BusinessDoc(models.Model):
    created_at         = DateTimeField(auto_now_add=True)
    created_by         = ForeignKey(User, related_name="%(class)s_created_by")
    updated_at         = DateTimeField(auto_now=True)
    updated_by         = ForeignKey(User)
    auto_post_to_accounting = BooleanField(default=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.auto_post_to_accounting:
            self._auto_post_to_accounting()   # calls create_and_post_voucher_for_doc

    def get_voucher_type(self) -> str: ...
    def get_economic_payload(self) -> dict: ...
```

---

## Analysis

### PaymentVoucher and JournalEntryVoucher â€” correct âœ…

These ARE the accounting event documents. They live inside the DEA boundary.
One PaymentVoucher = one cash movement = one accounting entry. Inheriting
BusinessDoc here is semantically correct and architecturally sound.

### BaseLoan / Loan / LoanPayment â€” incorrect âŒ

**A `GivenLoan` is a contract, not an accounting event.**

The accounting events on a loan lifecycle are:

| Event | Accounting Doc | DB Table |
|---|---|---|
| Loan disbursed | `PaymentVoucher(direction=PAYMENT)` | `dea_paymentvoucher` |
| Payment received | `PaymentVoucher(direction=RECEIPT)` | `dea_paymentvoucher` |
| Interest accrued | `JournalEntryVoucher` | `dea_journalentryvoucher` |

The `GivenLoan` row itself has no corresponding accounting entry.

Evidence that the auto-post is already non-functional for loans:
1. `BaseLoan.save()` explicitly sets `self.auto_post_to_accounting = False` with
   a comment: *"Loan status transitions post accounting entries explicitly via
   girvi.service_modules.payment. Prevent BusinessDoc's implicit auto-post."*
2. All posting in `girvi` goes through explicit facade calls:
   `facade.create_and_post_payment(...)`, `facade.post_payment_voucher(...)`.
3. `PaymentVoucher.get_voucher_type()` is the actual dispatch key used by
   the posting rule registry. `BaseLoan.get_voucher_type()` returns `"BASELOAN"`,
   which has no registered rule and would fail silently.

So `BaseLoan` inherits `BusinessDoc` but:
- Does not use `auto_post_to_accounting` (disabled in every save)
- Does not use `get_voucher_type()` for any real posting
- Does not use `get_economic_payload()`
- Gains only the 4 audit fields (`created_at/by`, `updated_at/by`) â€” which are
  generic enough to live on any model directly

This inheritance is the **only remaining DEA boundary violation** in the
`girvi` app that is structural (not an inline import), and is the reason
`loan.py` and `loan_refactored.py` are in the guardrail allowlist.

---

## Decision

**Remove `BusinessDoc` from `BaseLoan`, `Loan`, and `LoanPayment`.**

Apply Option A: copy the 4 audit fields + `auto_post_to_accounting` directly
onto these models (or drop `auto_post_to_accounting` entirely since it is always
False for loans).

### Why not Option B (composition)?

`GivenLoan` already has `GenericRelation("dea.PaymentVoucher", ...)`. That IS
the composition link â€” the loan â†’ payment â†’ voucher â†’ JE chain is already
correctly modelled without inheritance.

### Migration impact

The DB columns (`created_at`, `updated_at`, `created_by_id`, `updated_by_id`,
`auto_post_to_accounting`) already exist on `girvi_givenloan` and `girvi_takenloan`
tables from migration `0003`. Moving the field definitions from the inherited
abstract class to the concrete model class does not change the physical schema.
Django will generate a no-op migration (field owner change in migration state
only) or no migration at all.

`auto_post_to_accounting` can be removed from loan tables. Requires a real
`RemoveField` migration.

---

## Consequences

| After change | Benefit |
|---|---|
| `girvi/models/loan.py` and `loan_refactored.py` removed from guardrail allowlist | CI guardrail is fully clean |
| `BaseLoan.save()` no longer has dead code (`self.auto_post_to_accounting = False`) | Simpler, honest code |
| `BusinessDoc` only lives inside `dea/` | DEA boundary is fully enforced |
| `dea/models/doc.py` unchanged | PaymentVoucher/JournalEntryVoucher still work |

---

## Implementation checklist

- [x] Copy `created_at`, `created_by`, `updated_at`, `updated_by` directly to `BaseLoan`
- [x] Remove `BusinessDoc` from `BaseLoan` inheritance chain
- [x] Remove `BusinessDoc` from `Loan` and `LoanPayment` (loan.py)
- [x] Remove `auto_post_to_accounting` field from loan models + migration (`0020_remove_auto_post_to_accounting.py`)
- [x] Remove dead `self.auto_post_to_accounting = False` from `BaseLoan.save()`
- [x] Remove `loan_refactored.py` from `ALLOWLISTED_FILES`; `loan.py` kept with note (AccountTransaction/LedgerTransaction historical queries; remove when loan.py deleted Q3 2026)
- [x] Run `scripts/check_dea_boundary.py` â€” 0 violations (2026-05-03)
- [x] Run `manage.py makemigrations` â€” `0020_remove_auto_post_to_accounting.py` generated; `--check` passes after

