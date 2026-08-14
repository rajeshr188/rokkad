---
status: accepted
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# Girvi Flows Architecture: Clarifying the Role Within DEA

## Current State

Your DEA architecture has three layers:
1. **Business Docs** (immutable in terms of accounting): GivenLoan, TakenLoan, SalesInvoiceVoucher, etc. â€” mutable, subject to updates/corrections
2. **Vouchers** (lifecycle-driven): DRAFT â†’ POSTED â†’ CORRECTED/REVERSED â€” represent the intent to post to GL
3. **Journal Entries** (immutable once posted): one entry per voucher, maps to ledgers and accounts; reversible only via new reversal entry

The Girvi **LoanFlow** currently defines state transitions on the Loan business doc (CREATED â†’ APPROVED â†’ DISBURSED â†’ RELEASED, etc.), but it's **ambiguous and incomplete** about how those transitions map to voucher lifecycle.

---

## The Ambiguity

### Problem 1: When Do Vouchers Get Created?
- Does APPROVED â†’ DISBURSED automatically create a `LOAN_DISBURSE` voucher?
- Does DISBURSED â†’ RELEASED automatically create a `GIVENLOAN_RELEASE` voucher?
- Or are vouchers created manually by the user, independent of loan status?

**Current state: Unclear. The flow has transition methods that do `pass` (commented out).**

### Problem 2: What's the Direction of Authority?
- **Option A (Doc-driven)**: Loan status drives voucher creation. Status changes â†’ auto-create/post voucher.
- **Option B (Voucher-driven)**: Voucher posting drives loan status. User posts voucher â†’ auto-update loan status.
- **Option C (Decoupled)**: Loan status is independent of vouchers. User manually updates both.

**Current state: Decoupled, but no explicit contract.**

### Problem 3: Reversal Semantics
- If a loan is RELEASED and you want to "unreleased" it, do you:
  - Reverse the release voucher (creates a new reversing JE)?
  - Change the loan status back (but GL entries remain)?
  - Both?

**Current state: No reversal transitions defined.**

### Problem 4: Which Transitions Are Accounting-Relevant?
Not all loan status changes create vouchers:
- CREATED â†’ APPROVED (approval decision, no GL impact)
- APPROVED â†’ DISBURSED (cash goes out, creates voucher and JE)
- DISBURSED â†’ RELEASED (collateral released, may create voucher)
- DISBURSED â†’ DEFAULTED (event recorded, no GL impact... or maybe it does?)
- DEFAULTED â†’ AUCTIONED (event recorded, no GL impact)

**Current state: No annotation distinguishing accounting vs. non-accounting transitions.**

---

## Proposed Architecture

### Layer 1: Business Doc (Loan) â€” **Mutable, Version-Tracked**

**Role:** Represent the evolving business contract and operational state of a loan.

**Responsibility:**
- Maintain loan attributes (principal, rate, borrower, etc.) â€” can change pre-disbursement, or via amendments
- Track operational state (approval, disbursement, release, default, etc.)
- Store business logic for calculations (interest accrual, collateral valuation, etc.)

**Loan Status Transitions (BusinessDoc-level):**
```
CREATED â†’ APPROVED              [Decision: loan is approved]
APPROVED â†’ DISBURSED            [Event: cash disbursed to borrower]
DISBURSED â†’ RELEASED            [Event: collateral released to borrower]
DISBURSED â†’ DEFAULTED           [Event: loan marked as in default]
DEFAULTED â†’ AUCTIONED           [Event: collateral auctioned]
CREATED, APPROVED â†’ CANCELLED   [Cancel: loan never disbursed]
```

**Key principle:** Status is **informational** at this layer. It does NOT enforce voucher creation, nor is it directly driven by voucher status.

---

### Layer 2: Voucher + JournalEntry â€” **Immutable Once Posted**

**Role:** Record the accounting intent and GL impact of business events.

**Responsibility:**
- Create one Voucher per accounting event (e.g., LOAN_DISBURSE, GIVENLOAN_RECEIPT, etc.)
- Post to ledgers via JournalEntry (immutable, reversible only via new reversing entry)
- Enforce period locks and balance validation

**Voucher Lifecycle:**
```
DRAFT â†’ POSTED              [User submits for posting]
POSTED â†’ REVERSED           [User reverses via reversing voucher]
POSTED â†’ CORRECTED          [User corrects via correcting voucher]
```

**Key principle:** Vouchers are **independent** of loan status. A loan can be DISBURSED without a corresponding POSTED LOAN_DISBURSE voucher (draft or missing). A POSTED voucher can exist for a CANCELLED loan (historical record).

---

### Layer 3: Flow Transitions â€” **Liaison Between Doc and Voucher**

**Role:** Define which business doc status transitions trigger which voucher creations, and validate the accounting contract.

**Pattern:**

```
@status.transition(...)
def approve(self, approved_by):
    """Approve a loan [NON-ACCOUNTING]"""
    self.loan.approved_by = approved_by
    self.loan.approved_at = timezone.now()
    # No voucher creation here

@status.transition(...)
def disburse(self, disbursed_by):
    """Disburse a loan [ACCOUNTING]"""
    self.loan.disbursed_by = disbursed_by
    self.loan.disbursed_at = timezone.now()
    
    # **Trigger voucher creation** (but do NOT post it automatically)
    self._create_voucher(
        voucher_type='LOAN_DISBURSE',
        narration=f"Disbursement of {self.loan.principal_amount}",
        business_doc=self.loan,
    )
    # Flow returns control to user to review & post the voucher
    
    # Note: Do NOT set self.loan.status here. 
    # Status is set only after voucher is successfully posted.

@status.transition(...)
def release(self, released_by):
    """Release collateral [ACCOUNTING]"""
    # Similar: create GIVENLOAN_RELEASE voucher, wait for posting
    ...
```

---

## Recommended Changes to `flows.py`

### 1. **Annotate Transitions as Accounting vs. Non-Accounting**

```python
class LoanFlow(object):
    # ... existing code ...
    
    TRANSITION_ACCOUNTING_IMPACT = {
        'approve': False,           # Decision only, no GL
        'disburse': True,           # Creates LOAN_DISBURSE voucher â†’ JE
        'deliver': True,            # Creates GIVENLOAN_RELEASE voucher â†’ JE
        'cancel': False,            # Cancellation (loan never posted)
        'mark_defaulted': False,    # Event only (optional: could trigger GL memo entry)
        'mark_auctioned': True,     # Could trigger COLLATERAL_AUCTION voucher
        'mark_sold': True,          # Could trigger LOAN_SOLD voucher
    }
    
    def has_accounting_impact(self, transition_name):
        return self.TRANSITION_ACCOUNTING_IMPACT.get(transition_name, False)
```

### 2. **Separate Loan Status Updates from Voucher Triggers**

```python
@status.transition(
    source=LoanStatus.APPROVED,
    target=LoanStatus.DISBURSED,
    label=_("disburse"),
    permission=...,
)
def disburse(self, disbursed_by):
    """
    Disburse an approved loan.
    
    This transition:
    1. Updates loan status to DISBURSED
    2. Records disbursement metadata
    3. **Triggers creation of a LOAN_DISBURSE voucher (in DRAFT state)**
    4. Does NOT post the voucher (user must review & submit separately)
    """
    self.loan.disbursed_by = disbursed_by
    self.loan.disbursed_at = timezone.now()
    
    # Trigger voucher creation
    from apps.tenant_apps.dea.models import Voucher, VoucherType, BusinessDoc
    
    disburse_type = VoucherType.objects.get(name='LOAN_DISBURSE')
    
    Voucher.objects.create(
        voucher_no=self._generate_voucher_number('DISBURSE'),
        voucher_type=disburse_type,
        voucher_date=timezone.now().date(),
        status='DRAFT',  # Not posted yet
        created_by=self.user,
        business_doc=self.loan,  # Link to loan
        narration=f"Disbursement of â‚¹{self.loan.principal_amount} to {self.loan.borrower}",
    )
    
    # The flow itself does NOT post the voucher.
    # User must manually post it, which updates GL and triggers `posting_rule_engine`.
```

### 3. **Define Voucher â† â†’ Loan Status Sync Rules**

Document in a `VOUCHER_STATUS_CONTRACTS.md` or similar:

| Loan Status | Voucher Type | Voucher Status | Rule |
|---|---|---|---|
| APPROVED | (none) | (none) | No voucher created |
| DISBURSED | LOAN_DISBURSE | DRAFT | Created by disburse(); user must post |
| DISBURSED | LOAN_DISBURSE | POSTED | Flow completed; GL updated; loan can proceed |
| RELEASED | GIVENLOAN_RELEASE | POSTED | Collateral released GL entries applied |
| CANCELLED | â€” | â€” | Vouchers remain (history) but no new vouchers |
| DEFAULTED | â€” | â€” | No automatic voucher; optional memo entry |

### 4. **Add Reversal Transitions** (if needed)

```python
@status.transition(
    source=LoanStatus.RELEASED,
    target=LoanStatus.DISBURSED,
    label=_("unreleased"),
    permission=...,
)
def unreleased(self, reversed_by, reason):
    """
    Reverse the release of collateral (e.g., if released by mistake).
    
    This creates a REVERSAL voucher that reverses the original GIVENLOAN_RELEASE JE.
    """
    original_release_voucher = Voucher.objects.filter(
        business_doc_content_type=ContentType.objects.get_for_model(self.loan),
        business_doc_object_id=self.loan.id,
        voucher_type__name='GIVENLOAN_RELEASE',
        status='POSTED'
    ).first()
    
    if not original_release_voucher:
        raise ValidationError("No GIVENLOAN_RELEASE voucher found to reverse")
    
    # Create reversing voucher
    reversal_voucher = Voucher.objects.create(
        voucher_no=self._generate_voucher_number('REVERSAL'),
        voucher_type=VoucherType.objects.get(name='REVERSAL'),
        status='DRAFT',
        created_by=self.user,
        business_doc=self.loan,
        corrected_from=original_release_voucher,
        narration=reason,
    )
    
    self.loan.released_reversed_at = timezone.now()
    self._additional_data = {'reversal_reason': reason, 'reversal_voucher_id': reversal_voucher.id}
```

---

## Summary: Flow's Role in DEA

| Layer | Owner | Mutable | Lifecycle | When Used |
|---|---|---|---|---|
| **Loan (BusinessDoc)** | Girvi | Yes (pre-disbursal) | Custom (CREATED â†’ APPROVED â†’ ...) | Operational: track approvals, releases, defaults |
| **Voucher** | DEA | No (post-POSTED) | DRAFT â†’ POSTED â†’ REVERSED | Accounting: immutable GL records |
| **JournalEntry** | DEA | No | Posted (immutable) | Ledger: balance calculations |
| **Flows** | Girvi | Trigger-only | Liaison | Bridge: map doc transitions â†’ voucher creation |

**Flows are the liaison only.** They should:
1. Update loan status âœ“
2. Create vouchers (in DRAFT) âœ“
3. Delegate posting to user action
4. Not enforce bidirectional sync (user is responsible for posting the voucher before expecting GL impact)

---

## Action Items

1. **Clarify permission model:** Can a user change loan status without posting the resulting voucher? (Recommend: Yes, with a "dangling voucher" warning.)
2. **Implement voucher trigger:** Add `_create_voucher(...)` helper to LoanFlow.
3. **Add voucher contract table:** Document which transitions expect which vouchers.
4. **Codify non-accounting transitions:** Mark some as "info only" (no voucher needed).
5. **Test roundtrips:** Ensure loan status + voucher status + JE status stay consistent.

