# GivenLoan Lifecycle — States & Transitions

> **Source of truth:** `apps/tenant_apps/girvi/flows.py` (`LoanFlow`) and
> `apps/tenant_apps/girvi/models/loan_refactored.py` (`LoanStatus`).

---

## State Diagram

```
              ┌──────────┐
              │  CREATED │ ← initial state on loan creation
              └────┬─────┘
                   │ approve
                   ▼
              ┌──────────┐
              │ APPROVED │
              └────┬─────┘
                   │ disburse ← accounting (GIVENLOAN_DISBURSAL)
                   ▼
         ┌─────────────────┐
         │   DISBURSED     │◄──────────────────────┐
         └──┬──────┬───────┘                       │
            │      │                               │ (REPLEDGED is a
            │      │ mark_defaulted                │  sub-state; repledge
            │      ▼                               │  transitions back to
            │  ┌──────────┐                        │  DISBURSED on return)
            │  │ DEFAULTED│                        │
            │  └────┬─────┘                    ┌───┴──────┐
            │       │ mark_auctioned ←acctg    │REPLEDGED │
            │       ▼                           └──────────┘
            │  ┌──────────┐
            │  │ AUCTIONED│
            │  └──────────┘
            │
            │ mark_sold ←acctg
            ▼
         ┌────────┐
         │  SOLD  │
         └────────┘

    CREATED ──cancel──► CANCELLED
    APPROVED ──cancel──► CANCELLED

    DISBURSED ──(Release form)──► RELEASED
    REPLEDGED ──(Release form)──► RELEASED

    DISBURSED ──undo_disburse──► APPROVED     (reversal; only if no repayments posted)
    RELEASED  ──undo_release──►  DISBURSED    (reversal; deletes Release record)
```

---

## States Reference

| Status | Meaning |
|---|---|
| `Created` | Loan created; not yet reviewed |
| `Approved` | Reviewed and approved for disbursement |
| `Disbursed` | Cash paid to borrower; collateral in vault |
| `Repledged` | Some/all collateral items pledged to a lender (TakenLoan) |
| `Released` | Loan repaid; collateral returned to borrower |
| `Defaulted` | Borrower failed to repay; awaiting recovery action |
| `Auctioned` | Collateral auctioned off to recover the loan |
| `Sold` | Collateral directly sold |
| `Cancelled` | Loan voided before disbursement |
| `Rejected` | Loan rejected at review (no FSM transition currently) |
| `Closed` | Legacy terminal state (not used in current FSM) |

---

## Transitions Reference

### `approve`
| | |
|---|---|
| **Source** | `CREATED` |
| **Target** | `APPROVED` |
| **Permission** | `can_approve_loan` |
| **Accounting** | None |
| **UI trigger** | "✓ Approve" button → `loan_transition_view?transition=approve` |
| **Form fields** | `approved_by` (injected from `request.user`) |
| **What happens** | Status advances; `LoanChangeLog` entry created with `approved_by` + timestamp. No voucher, no cash movement. |

---

### `disburse`
| | |
|---|---|
| **Source** | `APPROVED` |
| **Target** | `DISBURSED` |
| **Permission** | `can_disburse_loan` |
| **Accounting** | ✅ `GIVENLOAN_DISBURSAL` PaymentVoucher posted by `record_loan_disbursal()` |
| **UI trigger** | "💳 Disburse" button → `loan_transition_view?transition=disburse` |
| **Form fields** | `disbursed_by` (injected from `request.user`) |
| **What happens** | 1. `flow.disburse()` advances status. 2. View calls `record_loan_disbursal(loan, user)` which creates a `PaymentVoucher(direction=PAYMENT, payment_type=DISBURSAL)` and posts via `GivenLoanDisbursalRule`. Journal entries: `Dr LOAN_PRINCIPAL_CTRL / Cr CASH` + subledger `Dr BORROWER_LOAN_CTRL`. |
| **Idempotency** | Reference marker `DISBURSAL-GIVENLOAN-<pk>` prevents double-posting. |

---

### `deliver`  *(internal — do not call directly from UI)*
| | |
|---|---|
| **Source** | `DISBURSED`, `REPLEDGED` |
| **Target** | `RELEASED` |
| **Permission** | `can_release_loan` |
| **Accounting** | ✅ `GIVENLOAN_RELEASE` PaymentVoucher posted by `record_loan_release()` **inside `Release.save()`** |
| **UI trigger** | "📦 Release" button → `release_loan_check_custody` → `girvi_release_create` → `Release.save()` |
| **Form fields** | `created_by`, `released_by`, `release_date` (all supplied by `Release.save()`) |
| **What happens** | `Release.save()` fires `flow.deliver()` to advance status, then calls `record_loan_release()`. Journal entries: `Dr CASH / Cr LOAN_PRINCIPAL_CTRL` (principal) + `Dr CASH / Cr INTEREST_INCOME` (interest) + subledger `Cr BORROWER_LOAN_CTRL`. |
| **⚠ Important** | `deliver` is **not** in `loan_transition_view`'s `form_classes`. It must never be triggered as a standalone action — doing so would advance the status without creating the `Release` document or posting accounting. Always go through the Release create form. |
| **Custody check** | Before the Release form, `release_loan_check_custody` verifies all items are back in the vault. If any are still with lenders, items must be returned first. |
| **Idempotency** | Reference marker `RELEASE-<release.pk>` prevents double-posting. |

---

### `cancel`
| | |
|---|---|
| **Source** | `CREATED`, `APPROVED` |
| **Target** | `CANCELLED` |
| **Permission** | `can_cancel_loan` |
| **Accounting** | None |
| **UI trigger** | "✕ Cancel" button → `loan_transition_view?transition=cancel` |
| **Form fields** | `cancelled_by` (from `request.user`), `reason` (text) |
| **What happens** | Status advances to CANCELLED; reason recorded in `LoanChangeLog`. No voucher — no cash has moved yet (loan was never disbursed). |

---

### `undo_disburse`
| | |
|---|---|
| **Source** | `DISBURSED` |
| **Target** | `APPROVED` |
| **Permission** | `can_disburse_loan` |
| **Accounting** | ✅ Reverses `GIVENLOAN_DISBURSAL` via `DjangoPostingEngine.reverse_voucher()` |
| **UI trigger** | "↩ Undo Disbursal" button → `loan_transition_view?transition=undo_disburse` |
| **Form fields** | `undone_by` (from `request.user`), `reason` (text) |
| **What happens** | 1. Guard: fails if any other posted PaymentVouchers exist (repayments or release must be reversed first). 2. `flow.undo_disburse()` sets status to APPROVED. 3. `reverse_loan_disbursal(loan, user)` finds the `DISBURSAL-GIVENLOAN-<pk>` PaymentVoucher, calls `DjangoPostingEngine().reverse_voucher()` which creates mirror JEs (reversing Dr/Cr), marks the original Voucher as `REVERSED`, and sets `payment.posted = False`. All steps are atomic. |
| **Guard** | Blocked by any `PaymentVoucher(posted=True)` on the loan other than the disbursal itself. |
| **Use case** | Disbursal entered for the wrong loan; needs to be un-done before re-doing correctly. |

---

### `undo_release`
| | |
|---|---|
| **Source** | `RELEASED` |
| **Target** | `DISBURSED` |
| **Permission** | `can_release_loan` |
| **Accounting** | ✅ Reverses `GIVENLOAN_RELEASE` via `DjangoPostingEngine.reverse_voucher()` |
| **UI trigger** | "↩ Undo Release" button → `loan_transition_view?transition=undo_release` |
| **Form fields** | `undone_by` (from `request.user`), `reason` (text) |
| **What happens** | 1. `flow.undo_release()` sets status to DISBURSED. 2. `reverse_loan_release(loan, user)` finds the `RELEASE-<release.pk>` PaymentVoucher and calls `DjangoPostingEngine().reverse_voucher()`. 3. The `Release` document is deleted. All steps are atomic. The reversal JEs and the REVERSED Voucher remain in the audit log; the original Release PK is preserved in the reversal Voucher metadata. |
| **Audit trail** | `LoanChangeLog` records the `undo_release` transition with `undone_by`, timestamp, and reason. The original GIVENLOAN_RELEASE Voucher is marked `REVERSED` (not deleted). |
| **Use case** | Release entered by mistake; collateral was not actually returned, or wrong loan was released. |

---

### `mark_defaulted`
| | |
|---|---|
| **Source** | `DISBURSED` |
| **Target** | `DEFAULTED` |
| **Permission** | `can_mark_defaulted` |
| **Accounting** | None (event recorded only) |
| **UI trigger** | "⚠ Mark Defaulted" button → `loan_transition_view?transition=mark_defaulted` |
| **Form fields** | `marked_by` (from `request.user`), `reason` (text) |
| **What happens** | Status advances; reason + timestamp recorded in `LoanChangeLog`. No GL impact at this point — recovery action (auction or sale) triggers accounting. |

---

### `mark_auctioned`
| | |
|---|---|
| **Source** | `DEFAULTED` |
| **Target** | `AUCTIONED` |
| **Permission** | `can_mark_auctioned` |
| **Accounting** | ✅ Auction voucher posted by view |
| **UI trigger** | "🔨 Auction" button → `loan_transition_view?transition=mark_auctioned` |
| **Form fields** | `auctioned_by` (from `request.user`), `amount` (auction proceeds) |
| **What happens** | Status advances; view creates accounting entry for auction proceeds. Auction amount recorded in `LoanChangeLog` metadata. |

---

### `mark_sold`
| | |
|---|---|
| **Source** | `DISBURSED` |
| **Target** | `SOLD` |
| **Permission** | *(none configured — inherits default)* |
| **Accounting** | ✅ Sale voucher posted by view |
| **UI trigger** | "💰 Sell" button → `loan_transition_view?transition=mark_sold` |
| **Form fields** | `sold_by` (from `request.user`), `amount` (sale proceeds) |
| **What happens** | Status advances directly from DISBURSED (bypasses DEFAULTED). View creates accounting entry for sale proceeds. |

---

## How Transitions Are Processed

### Standard path (approve / disburse / cancel / mark_defaulted / mark_auctioned / mark_sold)

```
User clicks button
  → loan_transition_view (views/loan.py)
      → FormClass(request.POST)
      → LoanFlow(loan, user, tenant)
      → flow.<transition>(**form.cleaned_data)
          → viewflow FSM validates source state + permission
          → transition body sets _additional_data
          → _on_success_transition fires (atomic):
              → loan.save()
              → LoanChangeLog.objects.create(...)
      → if transition == "disburse":
          record_loan_disbursal(loan, user)   # posts PaymentVoucher
  → redirect to loan detail
```

### Undo paths (undo_disburse / undo_release)

```
User clicks "↩ Undo ..."
    → loan_transition_view (views/loan.py)
            → FormClass(request.POST)
            → LoanFlow(loan, user, tenant)
            → flow.undo_* (status rollback + LoanChangeLog)
            → reverse_loan_* (find original PaymentVoucher)
                    → DjangoPostingEngine.reverse_voucher(voucher.pk, user)
                            → reversal JournalEntries created
                            → original Voucher.status = REVERSED
                    → original PaymentVoucher.posted = False
            → if undo_release: delete Release document
    → redirect to loan detail
```

### Release path (deliver)

```
User clicks "📦 Release"
  → release_loan_check_custody (views/custody_views.py)
      → if items with lenders → return flow first
      → redirect to girvi_release_create
  → Release form submitted
  → Release.save()
      → flow.deliver(created_by, released_by, release_date)
          → loan.status = RELEASED
          → LoanChangeLog created
      → record_loan_release(release, created_by)
          → PaymentVoucher(direction=RECEIPT, principal_amount, interest_amount)
          → GivenLoanReleaseRule posts:
              Dr CASH / Cr LOAN_PRINCIPAL_CTRL  (principal)
              Dr CASH / Cr INTEREST_INCOME      (interest)
              AT: Cr BORROWER_LOAN_CTRL
```

---

## Permission Codenames

| Codename | Guards |
|---|---|
| `can_approve_loan` | `approve` |
| `can_disburse_loan` | `disburse` |
| `can_release_loan` | `deliver` |
| `can_cancel_loan` | `cancel` |
| `can_mark_defaulted` | `mark_defaulted` |
| `can_mark_auctioned` | `mark_auctioned` |
| `can_disburse_loan` | `undo_disburse` |
| `can_release_loan` | `undo_release` |

Permissions are checked against `Membership.role.permissions` for the user's active workspace. See `flows.py:has_permission()`.

---

## Key Files

| File | Purpose |
|---|---|
| `apps/tenant_apps/girvi/flows.py` | `LoanFlow` FSM — all transitions defined here |
| `apps/tenant_apps/girvi/models/loan_refactored.py` | `LoanStatus` enum |
| `apps/tenant_apps/girvi/views/loan.py` | `loan_transition_view` — handles all UI-driven transitions |
| `apps/tenant_apps/girvi/models/release.py` | `Release.save()` — triggers `deliver` + `record_loan_release` |
| `apps/tenant_apps/girvi/payment_service.py` | `record_loan_disbursal`, `record_loan_release` |
| `apps/tenant_apps/girvi/views/custody_views.py` | `release_loan_check_custody` — pre-release custody gate |
| `apps/tenant_apps/dea/posting/rules/givenloan_disbursal.py` | DEA rule for GIVENLOAN_DISBURSAL voucher |
| `apps/tenant_apps/dea/posting/rules/givenloan_release.py` | DEA rule for GIVENLOAN_RELEASE voucher |
| `apps/tenant_apps/girvi/forms.py` | All transition forms (`ApproveLoanForm`, `DisburseLoanForm`, etc.) |
