# Girvi ↔ DEA Payment Integration — Detailed PR Plan

**Date**: March 23, 2026  
**Branch base**: `dea-kiss`  
**Author**: rajeshr188  
**Status**: 🚧 IN PROGRESS (PR-1/PR-2/PR-3 implemented, PR-4 underway)  

---

## 1. Problem Statement

The DEA (Double-Entry Accounting) subsystem has a complete, production-ready `PaymentVoucher` model with four registered posting rules covering every girvi cash-flow scenario:

| Rule Key | Direction | Description |
|---|---|---|
| `GIVENLOAN_PAYMENT` | PAYMENT | We disburse cash to borrower (loan creation) |
| `GIVENLOAN_RECEIPT` | RECEIPT | We receive cash from borrower (loan repayment) |
| `TAKENLOAN_RECEIPT` | RECEIPT | We receive cash from lender (taken loan disbursement) |
| `TAKENLOAN_PAYMENT` | PAYMENT | We pay cash to lender (taken loan repayment) |

**None of these rules are ever fired by the Girvi UI today.**

The girvi payment form at `/girvi/loanpayment/create/<pk>/` still writes to the legacy `LoanPayment` model. `LoanPayment.save()` attempts to post via `BusinessDoc._auto_post_to_accounting()` using voucher type `"LOAN_REPAY"` — but `LoanRepaymentRule` is **not decorated** with `@register_rule`, causing a silent `RuleNotFoundError` on every save. Every girvi payment made through the current UI produces **zero accounting entries**.

Additionally:
- Loan disbursal (cash out to borrower at `GivenLoan` creation) is never recorded in DEA.
- `TakenLoan` repayments have no UI path at all (`LoanPayment` only FK-linked to `GivenLoan`).
- `Release` events (collateral return) have zero DEA integration — `Release` does not extend `BusinessDoc`.
- Custody/repledge transfers have no accounting entries.

---

## 2. Architectural Anchor: What Already Works

The `dea` app already exposes a fully-wired endpoint:

```
/dea/loans/<source_type>/<loan_id>/payment/create/
    name: dea_create_loan_payment
    view: CreateLoanPaymentView
```

This view:
1. Resolves `GivenLoan` or `TakenLoan` from `source_type` + `loan_id` path params.
2. Calls `loan.create_payment(amount, date, method, ref, interest, principal, description, is_final, create_release, user)` — creates `PaymentVoucher` with `auto_post=False`.
3. Immediately calls `create_and_post_voucher_for_doc(doc=payment, voucher_type=payment.get_voucher_type())` — posts to ledger via the correct registered rule.
4. Sets `payment.posted = True` and saves.

The plan replaces all girvi payment recording paths to converge on this mechanism.

---

## 3. Scope

### In Scope

- Rewire girvi repayment UI to create `PaymentVoucher` instead of `LoanPayment`
- Loan disbursal `PaymentVoucher` creation at disbursal time
- TakenLoan repayment UI (new form + view)
- Release accounting entry (closing journal entry via `PaymentVoucher` or dedicated route)
- Loan detail tabs: show `PaymentVoucher` records, DEA journal entries from those vouchers
- Deprecation path for old `LoanPayment` model

### Out of Scope

- Custody/repledge accounting entries (addressed in a follow-on PR)
- Auction/default write-off accounting
- Interest accrual automation
- Multi-currency repayments
- Reversal / correction of posted `PaymentVoucher`

---

## 4. Gap Inventory

| ID | Gap | Severity | Fixed In |
|---|---|---|---|
| G-1 | Girvi repayment UI writes `LoanPayment`, not `PaymentVoucher` | 🔴 Critical | PR-1 |
| G-2 | `LoanRepaymentRule` unregistered → silent posting failure | 🔴 Critical | PR-1 (remove; rule stays for legacy) |
| G-3 | Loan disbursal has no `PaymentVoucher` → LOAN_RECEIVABLE never opened | 🔴 Critical | PR-2 |
| G-4 | `TakenLoan` has no repayment UI | 🟠 High | PR-3 |
| G-5 | `Release` has zero DEA integration | 🟠 High | PR-4 |
| G-6 | `TakenLoan` disbursal (we receive money from lender) has no `PaymentVoucher` | 🟠 High | PR-2 |
| G-7 | Loan detail "Payments" tab shows `LoanPayment` records, not `PaymentVoucher` | 🟡 Medium | PR-1 |
| G-8 | `LoanPaymentCreateForm` and girvi payment URLs are a dead end | 🟡 Medium | PR-5 |
| G-9 | `get_voucher_type()` returns `PAYMENT_OTHER` when source_content_type is null | 🟡 Medium | PR-1 (guard) |

---

## 5. PR Series

```
PR-1 ──► PR-2 ──► PR-3
              │
              └──► PR-4 ──► PR-5
```

### PR-1: Wire Girvi Repayment UI → PaymentVoucher
### PR-2: Loan Disbursal PaymentVoucher (GivenLoan + TakenLoan)
### PR-3: TakenLoan Repayment UI
### PR-4: Release Accounting Integration
### PR-5: Deprecate Old LoanPayment Model + Cleanup

---

## 6. PR-1 — Wire Girvi Repayment UI → PaymentVoucher

**Branch**: `feature/girvi-dea-pr1-repayment-rewire`  
**Depends on**: none (greenfield wiring)  
**Fixes gaps**: G-1, G-2, G-7, G-9  

### What Changes

#### 6.1 `apps/tenant_apps/girvi/views/loanpayment.py`

Replace `loan_payment_create_view` body. Instead of:

```python
# OLD (broken)
form = LoanPaymentForm(request.POST)
if form.is_valid():
    payment = form.save(commit=False)
    payment.loan = loan
    payment.save()   # ← LoanPayment.save() → LOAN_REPAY → RuleNotFoundError (silent)
```

New implementation:

```python
from apps.tenant_apps.dea.models import PaymentVoucher
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc

@login_required
def loan_payment_create_view(request, pk):
    loan = get_object_or_404(GivenLoan, pk=pk)
    form = GivenLoanRepaymentForm(request.POST or None, initial={"payment_date": timezone.now()})
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        payment = loan.create_payment(
            amount=cd["amount"],
            payment_date=cd["payment_date"],
            payment_method=cd["payment_method"],
            reference_number=cd.get("reference_number", ""),
            interest=cd.get("interest_amount"),
            principal=cd.get("principal_amount"),
            description=cd.get("description", ""),
            is_final=cd.get("is_final_payment", False),
            create_release=cd.get("create_release", False),
            created_by=request.user,
        )
        try:
            create_and_post_voucher_for_doc(
                doc=payment,
                user=request.user,
                voucher_type_input=payment.get_voucher_type(),
            )
            payment.posted = True
            payment.save(update_fields=["posted"])
            messages.success(request, f"Payment {payment.payment_id} recorded and posted.")
        except Exception as exc:
            messages.warning(request, f"Payment saved but accounting post failed: {exc}")
        return redirect("girvi:loan_detail", pk=loan.pk)
    return render(request, "girvi/payment/givenloan_repayment_form.html", {"form": form, "loan": loan})
```

#### 6.2 New Form: `GivenLoanRepaymentForm`

**File**: `apps/tenant_apps/girvi/forms.py`

```python
class GivenLoanRepaymentForm(CrispyFormMixin, forms.Form):
    amount = MoneyField(required=True, label="Total Amount")
    payment_date = forms.DateTimeField(widget=DateTimeLocalInput, required=True)
    payment_method = forms.ChoiceField(choices=PaymentMethod.choices, initial="CASH")
    reference_number = forms.CharField(max_length=100, required=False)
    interest_amount = MoneyField(required=False, label="Interest Portion")
    principal_amount = MoneyField(required=False, label="Principal Portion")
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    is_final_payment = forms.BooleanField(required=False, label="Final payment (closes loan)")
    create_release = forms.BooleanField(required=False, label="Also create Release record")
```

#### 6.3 Template: `templates/girvi/payment/givenloan_repayment_form.html`

Shows:
- Loan summary header (loan_id, borrower, outstanding balance, interest due)
- Form fields with `{% crispy form %}`
- `{% url 'dea_payment_list' %}` quick link to view all payments

#### 6.4 URL Update: `apps/tenant_apps/girvi/urls.py`

Keep existing `girvi_loanpayment_create` name intact (backward compat). Change view handler to the new function.

#### 6.5 Loan Detail Payments Tab

**File**: `apps/tenant_apps/girvi/views/loan.py` — `loan_detail_payments_tab` view

Change queryset source:

```python
# OLD
payments = loan.loan_payments.all()  # LoanPayment records

# NEW
from apps.tenant_apps.dea.models import PaymentVoucher
payments = loan.payments.select_related("reversal_of").order_by("-payment_date")  # PaymentVoucher records
```

Update `templates/girvi/loan/partials/payments_tab.html` to render `PaymentVoucher` fields:
- `payment.payment_id`, `payment.payment_date`, `payment.total_amount`, `payment.principal_amount`,
  `payment.interest_amount`, `payment.payment_method`, `payment.posted` (badge: Posted / Draft),
  `payment.direction` (RECEIPT / PAYMENT).

Add "New Payment" button → `{% url 'girvi_loanpayment_create' loan.pk %}`.

#### 6.6 Register Guard: `get_voucher_type()` Null Source (G-9)

**File**: `apps/tenant_apps/dea/models/payment.py` in `get_voucher_type()`

```python
def get_voucher_type(self) -> str:
    if not self.source_content_type_id:
        raise ValueError("PaymentVoucher.get_voucher_type(): source_content_type is null — cannot determine voucher type.")
    ...
```

Change from silent `"PAYMENT_OTHER"` fallback to explicit `ValueError` so misconfigured calls surface immediately.

### Verification

- [ ] Create GivenLoan payment through `/girvi/loanpayment/create/<pk>/` → `PaymentVoucher` created, `posted=True`
- [ ] Open DEA payment list → payment appears
- [ ] Open girvi loan detail payments tab → `PaymentVoucher` records shown with Posted badge
- [ ] Journal entries tab on loan detail shows the Dr Cash / Cr Loan_Receivable entries
- [ ] `manage.py check` 0 issues
- [ ] No `LoanPayment` records created in new flow

---

## 7. PR-2 — Loan Disbursal PaymentVoucher

**Branch**: `feature/girvi-dea-pr2-disbursal`  
**Depends on**: PR-1 (shared service pattern established)  
**Fixes gaps**: G-3, G-6  

### Domain Logic

When a `GivenLoan` transitions to status `DISBURSED`:
- We have paid out cash to the borrower.
- Accounting: **Dr Loan_Receivable (borrower account)**, **Cr Cash**
- This is `GIVENLOAN_PAYMENT` rule.

When a `TakenLoan` transitions to status `DISBURSED` (lender gives us money):
- We have received cash from the lender.
- Accounting: **Dr Cash**, **Cr Loan_Payable (lender account)**
- This is `TAKENLOAN_RECEIPT` rule.

### What Changes

#### 7.1 New Service Function: `record_loan_disbursal()`

**File**: `apps/tenant_apps/girvi/services/payment_service.py` (new)

```python
from apps.tenant_apps.dea.models import PaymentVoucher
from apps.tenant_apps.dea.services.post_doc import create_and_post_voucher_for_doc

def record_loan_disbursal(loan, user):
    """
    Creates and posts a PaymentVoucher for the loan disbursal event.
    For GivenLoan: direction=PAYMENT, type=DISBURSAL (we pay out cash)
    For TakenLoan: direction=RECEIPT, type=DISBURSAL (we receive cash)
    Idempotent: if a DISBURSAL PaymentVoucher already exists for this loan, returns it unchanged.
    """
    ct = ContentType.objects.get_for_model(loan)
    existing = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=loan.pk,
        payment_type=PaymentType.DISBURSAL,
    ).first()
    if existing:
        return existing, False  # already recorded

    if isinstance(loan, GivenLoan):
        direction = CashFlowDirection.PAYMENT
        amount = loan.get_loan_amount
        description = f"Disbursal of {loan.loan_id} to {loan.borrower}"
    else:  # TakenLoan
        direction = CashFlowDirection.RECEIPT
        amount = loan.get_loan_amount
        description = f"Receipt of {loan.loan_id} from {loan.lender}"

    payment = PaymentVoucher.objects.create(
        source_document=loan,
        direction=direction,
        payment_type=PaymentType.DISBURSAL,
        total_amount=amount,
        amount_in_base_currency=amount,
        payment_date=loan.loan_date,
        payment_method=PaymentMethod.CASH,
        description=description,
        created_by=user,
        auto_post_to_accounting=False,
    )
    create_and_post_voucher_for_doc(
        doc=payment,
        user=user,
        voucher_type_input=payment.get_voucher_type(),
    )
    payment.posted = True
    payment.save(update_fields=["posted"])
    return payment, True
```

#### 7.2 Hook into Loan Transition: `loan_transition_view`

**File**: `apps/tenant_apps/girvi/views/loan.py` — `loan_transition_view`

When `new_status == LoanStatus.DISBURSED`:

```python
from apps.tenant_apps.girvi.services.payment_service import record_loan_disbursal

if new_status == LoanStatus.DISBURSED:
    payment, created = record_loan_disbursal(loan, request.user)
    if created:
        messages.success(request, f"Disbursal entry {payment.payment_id} posted to accounting.")
    else:
        messages.info(request, "Disbursal already recorded.")
```

#### 7.3 Algorithm Summary

| Event | Loan Type | Direction | PaymentType | Rule | Accounting |
|---|---|---|---|---|---|
| Status → DISBURSED | GivenLoan | PAYMENT | DISBURSAL | `GIVENLOAN_PAYMENT` | Dr Loan_Receivable, Cr Cash |
| Status → DISBURSED | TakenLoan | RECEIPT | DISBURSAL | `TAKENLOAN_RECEIPT` | Dr Cash, Cr Loan_Payable |

#### 7.4 Idempotency

`record_loan_disbursal()` checks for an existing `PaymentVoucher(source=loan, payment_type=DISBURSAL)` before creating. The underlying `create_and_post_voucher_for_doc()` also fingerprint-checks. Double-trigger safe.

#### 7.5 `LoanDisbursementRule` Audit

**File**: `apps/tenant_apps/dea/posting/rules/loan_disbursement.py`

Confirm `@register_rule("GIVENLOAN_PAYMENT")` (or `"LOAN_DISBURSE"` — verify current key). If key mismatches `payment.get_voucher_type()`, alias-register.

### Verification

- [ ] Create `GivenLoan` → set status DISBURSED → `PaymentVoucher(direction=PAYMENT, type=DISBURSAL)` created
- [ ] Journal entry: Dr Loan_Receivable, Cr Cash for correct amount
- [ ] Transition again → idempotent, no duplicate entry
- [ ] Create `TakenLoan` → DISBURSED → `PaymentVoucher(direction=RECEIPT, type=DISBURSAL)` created
- [ ] Journal entry: Dr Cash, Cr Loan_Payable

---

## 8. PR-3 — TakenLoan Repayment UI

**Branch**: `feature/girvi-dea-pr3-takenloan-repayment`  
**Depends on**: PR-1 (established form/view pattern)  
**Fixes gaps**: G-4  

### What Changes

#### 8.1 New View: `taken_loan_payment_create_view`

**File**: `apps/tenant_apps/girvi/views/loanpayment.py`

```python
@login_required
def taken_loan_payment_create_view(request, pk):
    loan = get_object_or_404(TakenLoan, pk=pk)
    form = TakenLoanRepaymentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        cd = form.cleaned_data
        payment = loan.create_payment(
            amount=cd["amount"],
            payment_date=cd["payment_date"],
            payment_method=cd["payment_method"],
            reference_number=cd.get("reference_number", ""),
            interest=cd.get("interest_amount"),
            description=cd.get("description", ""),
            is_final=cd.get("is_final_payment", False),
            created_by=request.user,
        )
        try:
            create_and_post_voucher_for_doc(
                doc=payment,
                user=request.user,
                voucher_type_input=payment.get_voucher_type(),  # → "TAKENLOAN_PAYMENT"
            )
            payment.posted = True
            payment.save(update_fields=["posted"])
            messages.success(request, f"Payment {payment.payment_id} posted.")
        except Exception as exc:
            messages.warning(request, f"Payment saved but posting failed: {exc}")
        return redirect("girvi:takenloan_detail", pk=loan.pk)
    return render(request, "girvi/payment/takenloan_repayment_form.html", {"form": form, "loan": loan})
```

#### 8.2 New Form: `TakenLoanRepaymentForm`

Same fields as `GivenLoanRepaymentForm` but no `create_release` flag (TakenLoan has no Release concept).

```python
class TakenLoanRepaymentForm(CrispyFormMixin, forms.Form):
    amount = MoneyField(required=True)
    payment_date = forms.DateTimeField(widget=DateTimeLocalInput, required=True)
    payment_method = forms.ChoiceField(choices=PaymentMethod.choices, initial="CASH")
    reference_number = forms.CharField(max_length=100, required=False)
    interest_amount = MoneyField(required=False)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False)
    is_final_payment = forms.BooleanField(required=False)
```

#### 8.3 URL: `apps/tenant_apps/girvi/urls.py`

```python
path("takenloan/<pk>/payment/create/", views.taken_loan_payment_create_view, name="takenloan_payment_create"),
```

#### 8.4 TakenLoan Detail Template

Add "Record Payment" button to the TakenLoan detail page payments section:

```html
<a class="btn btn-primary" href="{% url 'girvi:takenloan_payment_create' loan.pk %}">
  <i class="bi bi-cash-coin"></i> Record Repayment to Lender
</a>
```

#### 8.5 Accounting Postcondition

```
TakenLoan Repayment PaymentVoucher posted:
  Dr Loan_Payable (lender subledger)   ← reduce liability
  Cr Cash                               ← cash outflow
```

### Verification

- [ ] Open TakenLoan detail → "Record Repayment" button visible
- [ ] Submit form → `PaymentVoucher(direction=PAYMENT, source=takenloan)` created and posted
- [ ] `TAKENLOAN_PAYMENT` rule fired: Dr Loan_Payable, Cr Cash
- [ ] `loan.total_paid` increases; `loan.outstanding_balance` decreases

---

## 9. PR-4 — Release Accounting Integration

**Branch**: `feature/girvi-dea-pr4-release-accounting`  
**Depends on**: PR-1  
**Fixes gaps**: G-5  

### Domain Logic

A `Release` means: the loan is fully settled, collateral is physically returned to the borrower. From an accounting perspective:

| Scenario | Accounting Entry |
|---|---|
| Loan fully paid (no balance) | No monetary entry needed; post a closing memo voucher |
| Loan partially paid (waived remainder) | Dr Loan_Receivable (write-off), Cr Bad_Debt or Cr Interest_Waived |
| Release with final payment | Final `PaymentVoucher` already closes Loan_Receivable |

The most practical first implementation:
- After `Release.create()`, compute `loan.outstanding_principal`.
- If `outstanding_principal > 0`, **create a write-off `PaymentVoucher`** (direction=RECEIPT, description="Release write-off") and post via a new `GIVENLOAN_RELEASE` rule.
- If `outstanding_principal == 0`, still create a **zero-amount closing `PaymentVoucher`** to stamp the ledger with a RELEASED event (for audit trail / report filtering).

### What Changes

#### 9.1 New Posting Rule: `GIVENLOAN_RELEASE`

**File**: `apps/tenant_apps/dea/posting/rules/givenloan_release.py`

```python
@register_rule("GIVENLOAN_RELEASE")
class GivenLoanReleaseRule(PostingRule):
    rule_version = "1.0"

    def build_posting(self, ctx: PostingContext) -> PostingBundle:
        payment: PaymentVoucher = ctx.doc
        loan: GivenLoan = payment.source_loan
        outstanding = loan.outstanding_principal or Money(0, "INR")
        lines = []
        if outstanding.amount > 0:
            # Write-off: Dr Loan_Receivable, Cr Interest_Income / Bad Debt
            lines.append(DualLedgerLine(
                debit_account="LOAN_RECEIVABLE",
                credit_account="INTEREST_INCOME",
                inr_amount=outstanding,
                narration=f"Release write-off: {loan.loan_id}",
            ))
        # Always post a customer subledger close entry
        lines.append(AccountLine(
            account=loan.borrower.account,
            amount=outstanding,
            direction=AccountDirection.CREDIT,
            narration=f"Loan {loan.loan_id} released",
        ))
        return PostingBundle(lines=lines, source=payment)
```

#### 9.2 New VoucherType Seed: Migration

**File**: `apps/tenant_apps/dea/migrations/0006_givenloan_release_vouchertype.py`

```python
def seed_release_vouchertype(apps, schema_editor):
    VoucherType = apps.get_model("dea", "VoucherType")
    VoucherType.objects.update_or_create(
        name="GIVENLOAN_RELEASE",
        defaults={"description": "Loan Release / Closing Entry", "is_system": True},
    )
```

#### 9.3 `Release.save()` Hook

**File**: `apps/tenant_apps/girvi/models/release.py`

After the existing `LoanFlow.deliver()` call, call the new service:

```python
from apps.tenant_apps.girvi.services.payment_service import record_loan_release

def save(self, *args, **kwargs):
    # existing logic: auto-generate release_id, LoanFlow.deliver()
    super().save(*args, **kwargs)
    try:
        record_loan_release(self, created_by=self.created_by)
    except Exception as exc:
        logger.error("Release accounting post failed for %s: %s", self.release_id, exc)
```

#### 9.4 New Service: `record_loan_release()`

**File**: `apps/tenant_apps/girvi/services/payment_service.py`

```python
def record_loan_release(release, created_by):
    loan = release.loan
    ct = ContentType.objects.get_for_model(loan)
    existing = PaymentVoucher.objects.filter(
        source_content_type=ct,
        source_object_id=loan.pk,
        payment_type=PaymentType.OTHER,
        description__startswith="Release:",
    ).first()
    if existing:
        return existing, False

    outstanding = loan.outstanding_principal or Money(0, "INR")
    payment = PaymentVoucher.objects.create(
        source_document=loan,
        direction=CashFlowDirection.RECEIPT,
        payment_type=PaymentType.OTHER,
        total_amount=outstanding,
        amount_in_base_currency=outstanding,
        payment_date=release.release_date,
        payment_method=PaymentMethod.CASH,
        description=f"Release: {loan.loan_id} — {release.release_id}",
        is_final_payment=True,
        created_by=created_by,
        auto_post_to_accounting=False,
    )
    create_and_post_voucher_for_doc(
        doc=payment,
        user=created_by,
        voucher_type_input="GIVENLOAN_RELEASE",
    )
    payment.posted = True
    payment.save(update_fields=["posted"])
    return payment, True
```

### Verification

- [ ] Create Release for a loan with zero outstanding → `PaymentVoucher` with `total_amount=0` created and posted
- [ ] Create Release for loan with unpaid balance → write-off entry created (Dr Loan_Receivable, Cr Interest_Income)
- [ ] `Release` model `save()` failure in accounting post does NOT roll back the release itself (try/except)
- [ ] Loan detail journal entries tab shows the GIVENLOAN_RELEASE voucher

---

## 10. PR-5 — Deprecate Old `LoanPayment` Model

**Branch**: `feature/girvi-dea-pr5-deprecate-loanpayment`  
**Depends on**: PR-1, PR-3 fully deployed and validated  
**Fixes gaps**: G-8  

### What Changes

#### 10.1 Migration: Archive Old Records

**File**: `apps/tenant_apps/girvi/migrations/XXXX_archive_loanpayments.py`

```python
def migrate_legacy_payments(apps, schema_editor):
    """
    For each LoanPayment, if no PaymentVoucher exists for the same (loan, date, amount),
    create a PaymentVoucher marked posted=False (draft) with description "Migrated from LoanPayment".
    This preserves historical data without re-posting (no double-accounting).
    """
    LoanPayment = apps.get_model("girvi", "LoanPayment")
    PaymentVoucher = apps.get_model("dea", "PaymentVoucher")
    ContentType = apps.get_model("contenttypes", "ContentType")
    GivenLoan = apps.get_model("girvi", "GivenLoan")
    ct = ContentType.objects.get_for_model(GivenLoan)

    for lp in LoanPayment.objects.all():
        PaymentVoucher.objects.get_or_create(
            source_content_type=ct,
            source_object_id=lp.loan_id,
            payment_date=lp.payment_date,
            total_amount=lp.payment_amount,
            defaults={
                "direction": "RECEIPT",
                "payment_type": "RECEIPT",
                "principal_amount": lp.principal_payment,
                "interest_amount": lp.interest_payment,
                "payment_method": "CASH",
                "description": f"Migrated from LoanPayment #{lp.pk}",
                "posted": False,
                "auto_post_to_accounting": False,
                "amount_in_base_currency": lp.payment_amount,
            }
        )
```

#### 10.2 Remove Girvi Payment Views (Old)

- Remove `loan_payment_list_view`, `loan_payment_create_view`, `loan_payment_update_view`, `loan_payment_delete_view` from `views/loanpayment.py`
- Replace with redirects or 410 Gone responses for backward compat

#### 10.3 Remove Old URLs

**File**: `apps/tenant_apps/girvi/urls.py`

Remove:
```python
path("loanpayment/", ...),
path("loanpayment/create/", ...),  # keep <pk>/ variant pointed to new view
path("loanpayment/update/<pk>/", ...),
path("loanpayment/<pk>/delete", ...),
```

#### 10.4 Remove Old Form

**File**: `apps/tenant_apps/girvi/forms.py`

Remove `LoanPaymentForm` class (after confirming no remaining usages).

#### 10.5 Keep `LoanPayment` Model (Soft Deprecation)

Do **not** drop the `LoanPayment` DB table yet. Mark the model class with `@deprecated` comment, add `class Meta: managed = False` (read-only access for historical queries). Full model drop in a later cleanup PR.

### Verification

- [ ] No import of `LoanPayment` in active views/forms after cleanup
- [ ] `manage.py check` 0 issues
- [ ] Old payment URLs redirecting or returning 410
- [ ] Historical `LoanPayment` records accessible as `PaymentVoucher(posted=False)` in DEA payment list

---

## 11. Cross-Cutting Concerns

### 11.1 Error Handling Policy

All `create_and_post_voucher_for_doc()` calls in girvi views MUST follow this pattern:

```python
try:
    create_and_post_voucher_for_doc(doc=payment, user=request.user, ...)
    payment.posted = True
    payment.save(update_fields=["posted"])
    messages.success(request, "Posted to accounting.")
except Exception as exc:
    logger.exception("Accounting post failed for %s", payment.payment_id)
    messages.warning(request, f"Payment saved (ID: {payment.payment_id}) but accounting posting failed: {exc}. Contact admin.")
```

The `PaymentVoucher` record is always committed regardless. Accounting post failure is surfaced to user as a warning (not an error) so the operator can use the DEA retry UI.

### 11.2 `auto_post_to_accounting` Convention

`PaymentVoucher.save()` hardcodes `auto_post_to_accounting = False`. This is intentional. All posting is explicit via `create_and_post_voucher_for_doc()`. Never enable auto-posting on `PaymentVoucher`.

### 11.3 Fingerprint Idempotency

`create_and_post_voucher_for_doc()` uses SHA-256 over `loan.get_economic_payload()`. If a view is triggered twice (double-submit, signal fire), the second call returns the existing voucher unchanged. Every view should still guard with UI-level double-submit protection (disabled submit button or HTMX once:).

### 11.4 `posted=False` Records (Draft Vouchers)

The DEA payment list at `/dea/payments/` will show unposted vouchers (accounting failures). These are actionable: operators can retry posting from the `PaymentVoucherDetailView`. No additional retry UI is needed in girvi for PR-1.

### 11.5 Multi-Tenant Safety

All queries use the active schema (django-tenants connection routing). No cross-schema risks. `record_loan_disbursal()` and `record_loan_release()` should be called only from within request context or schema-aware management commands.

---

## 12. Decision Log

| ID | Decision | Rationale | Alternative Rejected |
|---|---|---|---|
| D-1 | Rewrite girvi view body (not redirect to `dea_create_loan_payment`) | Keeps girvi URL namespace clean; girvi-specific form fields differ from generic DEA form | Redirect to DEA view: would expose internal DEA URLs from girvi loan detail |
| D-2 | `record_loan_disbursal()` triggered only on status transition DISBURSED (not at loan creation) | Loan creation ≠ disbursal; loans can be in Created/Approved state without payout | Auto-post on `GivenLoan.save()` would fire on every update |
| D-3 | Zero-balance `Release` skips voucher creation for now | `PaymentVoucher.clean()` enforces strictly positive amounts; avoids invalid zero-value vouchers | Forcing synthetic non-zero vouchers would distort economics |
| D-4 | Keep `LoanPayment` model (soft-deprecate, not hard-drop) in PR-5 | Historical records must remain queryable; hard drop risks data loss and migration complexity | Drop immediately: too risky |
| D-5 | New `GIVENLOAN_RELEASE` posting rule (not reuse `GIVENLOAN_RECEIPT`) | Release write-off uses **Dr SERVICES_EXPENSE, Cr LOAN_RECEIVABLE**; semantic distinction from repayment receipt | Reuse receipt rule: wrong account mapping |
| D-6 | Post failure does NOT rollback the business doc save | DEA is a write-once audit system; operator can retry post from DEA payment list | Rollback everything: causes data loss if posting engine has transient fault |

---

## 13. Open Questions (Need Resolution Before PR-5)

| Q# | Question | Impact |
|---|---|---|
| Q-5 | Should `Release` extend `BusinessDoc` in a later refactor? | Could simplify future auto-post/reversal workflows; not required for current PR-4 scope |

---

## 14. PR Tracking Checklist

```
PR-1: Wire Girvi Repayment UI → PaymentVoucher
    [x] Branch created: feature/girvi-dea-pr1-repayment-rewire
    [x] GivenLoanRepaymentForm added to forms.py
    [x] loan_payment_create_view rewritten
    [x] givenloan_repayment_form.html template created
    [x] Loan detail payments tab switched to PaymentVoucher queryset
    [x] payments_tab.html updated to show PaymentVoucher fields
    [x] get_voucher_type() null guard added
    [x] manage.py check: 0 issues
  [ ] Manual flow tested: create payment → DEA journal entries visible
  [ ] PR link:
  [ ] Merge date:

PR-2: Loan Disbursal PaymentVoucher
    [x] Branch created: feature/girvi-dea-pr2-disbursal
    [x] apps/tenant_apps/girvi/services/payment_service.py created
    [x] record_loan_disbursal() implemented with idempotency guard
    [x] loan_transition_view updated for DISBURSED status
    [x] GIVENLOAN_PAYMENT (or LOAN_DISBURSE) rule key confirmed
    [x] TakenLoan DISBURSED → TAKENLOAN_RECEIPT verified
    [x] manage.py check: 0 issues
  [ ] Manual flow tested: status → DISBURSED → PaymentVoucher in DEA
  [ ] PR link:
  [ ] Merge date:

PR-3: TakenLoan Repayment UI
    [x] Branch created: feature/girvi-dea-pr3-takenloan-repayment
    [x] TakenLoanRepaymentForm added to forms.py
    [x] taken_loan_payment_create_view added to views/loanpayment.py
    [x] URL added: takenloan/<pk>/payment/create/
    [x] TakenLoan detail template updated with payment button
    [x] TAKENLOAN_PAYMENT rule verified in registry
    [x] manage.py check: 0 issues
  [ ] PR link:
  [ ] Merge date:

PR-4: Release Accounting Integration
  [ ] Branch created: feature/girvi-dea-pr4-release-accounting
    [x] GIVENLOAN_RELEASE posting rule created + @register_rule
        [x] VoucherType seed migration created and applied
    [x] record_loan_release() service implemented
    [x] Release.save() hook added (try/except, non-blocking)
    [x] Q-2 resolved (write-off account policy: Dr SERVICES_EXPENSE, Cr LOAN_RECEIVABLE)
        [x] Zero-balance release test: skip voucher creation (positive-amount validation constraint)
    [x] Non-zero balance release test: write-off entries correct
    [x] manage.py check: 0 issues
    [x] validate.py fixed: DualLedgerLine uses debit_ledger_id/credit_ledger_id (not ledger_id)
    [x] assert_balanced() fixed: DualLedgerLine is self-balancing; AccountLine is sub-ledger (not summed)
    [x] engine.py fixed: TransactionType_DE.pk (XactTypeCode CharField PK, not .id)
    [x] engine.py fixed: django.utils.timezone (not datetime.timezone)
    [x] Manual flow validated (synthetic): LOAN=Z00004 ₹1000 → GIVENLOAN_RELEASE voucher POSTED → JE created
        LTXN: DR:Interest Paid | CR:Loans & Advances | AMT:₹1,000.00
  [ ] PR link:
  [ ] Merge date:

PR-5: Deprecate Old LoanPayment Model
  [ ] Branch created: feature/girvi-dea-pr5-deprecate-loanpayment
    [x] ReleaseForm.save() LoanPayment double-write removed (PR-4 hook handles DEA posting)
    [x] LoanPaymentForm class removed from forms.py
    [x] LoanPaymentFilter class removed from filters.py
    [x] loan_payment_list_view / update_view / delete_view removed from views/loanpayment.py
    [x] dashboard.py: LoanPayment counts replaced with PaymentVoucher counts
    [x] dea/views/payment.py: CreateLoanPaymentView removed
    [x] dea/forms.py: LoanPaymentCreateForm removed
    [x] dea/urls.py: dea_create_loan_payment URL removed
    [x] girvi/urls.py: list, bare create, update, delete URLs removed; <pk>/create/ kept
    [x] admin.py: LoanPaymentAdminForm + LoanPaymentAdmin removed; import cleaned
    [x] signals.py: LoanPayment import removed
    [x] services.py: get_interest_paid() stubbed (LoanPayment data superseded)
    [x] LoanPayment.get_update_url() fixed (no longer references deleted URL)
    [x] LoanPayment model soft-deprecated: managed=False + deprecation docstring
    [x] Migration 0013: archive legacy LoanPayment rows → draft PaymentVoucher
      - Fixed: payment_id explicitly set (save() not called in migrations)
      - Fixed: amount_in_base_currency + _currency both set (required MoneyField)
      - Result on jcl schema: 3 legacy LoanPayments → 3 draft PaymentVouchers
    [x] manage.py check: 0 issues
    [x] 12/12 tests passing
  [ ] PR link:
  [ ] Merge date:
```

---

## 15. File Change Summary

| File | Change Type | PR |
|---|---|---|
| `apps/tenant_apps/girvi/views/loanpayment.py` | Modify (rewrite create view) | PR-1 |
| `apps/tenant_apps/girvi/views/loan.py` | Modify (payments tab queryset, disbursal hook) | PR-1, PR-2 |
| `apps/tenant_apps/girvi/forms.py` | Add `GivenLoanRepaymentForm`, `TakenLoanRepaymentForm` | PR-1, PR-3 |
| `apps/tenant_apps/girvi/urls.py` | Modify (new TakenLoan payment URL) | PR-3, PR-5 |
| `apps/tenant_apps/girvi/models/release.py` | Modify (save hook) | PR-4 |
| `apps/tenant_apps/girvi/services/payment_service.py` | Create (new service module) | PR-2 |
| `apps/tenant_apps/dea/models/payment.py` | Modify (null guard in `get_voucher_type`) | PR-1 |
| `apps/tenant_apps/dea/posting/rules/givenloan_release.py` | Create (new rule) | PR-4 |
| `apps/tenant_apps/dea/migrations/0010_seed_girvi_release_vouchertype.py` | Create | PR-4 |
| `apps/tenant_apps/girvi/migrations/XXXX_archive_loanpayments.py` | Create | PR-5 |
| `templates/girvi/payment/givenloan_repayment_form.html` | Create | PR-1 |
| `templates/girvi/payment/takenloan_repayment_form.html` | Create | PR-3 |
| `templates/girvi/loan/partials/payments_tab.html` | Modify | PR-1 |
| TakenLoan detail template | Modify (add payment button) | PR-3 |

---

*Total estimated new code: ~400 lines Python, ~120 lines HTML templates, 2 migrations.*  
*All existing DEA posting rules used as-is. No DEA model schema changes required for PR-1 through PR-3.*
