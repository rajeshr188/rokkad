---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# GivenLoan Status & Transition Contract

Date: 2026-04-04

A concise, canonical reference for the `GivenLoan` lifecycle.

---

## 1) Key distinction: status vs transition vs document

These terms are related but **not interchangeable**:

| Term | Meaning | Example |
|---|---|---|
| **Status** | The current state stored on the loan | `Created`, `Approved`, `Disbursed`, `Released` |
| **Transition** | The legal state-change action in `LoanFlow` | `approve`, `disburse`, `deliver`, `undo_release` |
| **Business document** | A record created as part of a workflow | `Release` |

### Important release terminology

- **`deliver`** = the internal FSM transition key
- **`Released`** = the resulting loan status
- **`Release`** = the business document created during the workflow

So in UI/business terms:

> â€œRelease a loanâ€ means: create `Release` document + execute `deliver` transition + post release accounting.

---

## 2) Canonical lifecycle path

```text
Created --approve--> Approved --disburse--> Disbursed --deliver--> Released
   |                       |                    |
   +--cancel-------------> Cancelled           +--mark_defaulted--> Defaulted --mark_auctioned--> Auctioned
                                               +--mark_sold-------> Sold
                                               +--repledge--------> Repledged --undo_repledge--> Disbursed
                                               +--undo_disburse---> Approved

Released --undo_release--> Disbursed
```

---

## 3) Transition contract table

| Transition key | Business label | From | To | Execution mode | Notes |
|---|---|---|---|---|---|
| `approve` | Approve Loan | `Created` | `Approved` | `generic-transition` | Review/approval only |
| `disburse` | Disburse Funds | `Approved` | `Disbursed` | `transition-with-accounting` | Posts disbursal accounting |
| `deliver` | Release to Customer | `Disbursed` | `Released` | `release-flow` | Uses `ReleaseLifecycleService` |
| `cancel` | Cancel Loan | `Created`, `Approved` | `Cancelled` | `generic-transition` | Pre-disbursal cancellation |
| `mark_defaulted` | Mark Defaulted | `Disbursed` | `Defaulted` | `generic-transition` | Recovery workflow marker |
| `mark_auctioned` | Record Auction | `Defaulted` | `Auctioned` | `warning-transition` | Recovery completion path |
| `mark_sold` | Record Sale | `Disbursed` | `Sold` | `warning-transition` | Sale event path |
| `undo_disburse` | Undo Disbursal | `Disbursed` | `Approved` | `reversal-transition` | Reverses disbursal |
| `undo_release` | Undo Release | `Released` | `Disbursed` | `reversal-transition` | Reverses release |
| `repledge` | Mark Repledged | `Disbursed` | `Repledged` | `renewal-flow` | Used by renewal/repledge workflow |
| `undo_repledge` | Undo Repledge | `Repledged` | `Disbursed` | `reversal-transition` | Cancels renewal linkage |

---

## 4) Source of truth in code

- Legal state transitions: `apps/tenant_apps/girvi/flows.py`
- Canonical transition contract + aliases + UI metadata: `apps/tenant_apps/girvi/transition_registry.py`
- Transition execution commands: `apps/tenant_apps/girvi/transitions/commands.py`
- Multi-step release workflow: `apps/tenant_apps/girvi/service_modules/release_lifecycle.py`
- Renewal/repledge workflow: `apps/tenant_apps/girvi/service_modules/renewal.py`

---

## 5) Practical rules for future changes

1. Keep **internal keys stable** (`approve`, `deliver`, `mark_sold`, etc.).
2. Treat **UI labels** as display-only; do not use them as the contract.
3. Route **release** through `ReleaseLifecycleService`, not direct model writes.
4. Route **renewal/repledge** through `LoanRenewalService`.
5. If a new transition is added, update both:
   - `LoanFlow` in `flows.py`
   - `TRANSITION_REGISTRY` / `TRANSITION_STATE_REGISTRY` in `transition_registry.py`

---

## Short takeaway

> Use the transition key for system logic, the status for current state, and the business document name for workflow artifacts. Keeping those three concepts separate prevents ambiguity.

