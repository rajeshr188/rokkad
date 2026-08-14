---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# DEA â€” Phased Execution Blueprint
**Branch:** `dea-kiss`  
**Authored:** 2026-05-06  
**Ground truth:** Every item maps to a real file or a confirmed gap in this repo.

---

## How to read this document

Each item carries:
- **File path** â€” exact file to create or change.
- **What** â€” the concrete action, not a description.
- **Why it matters** â€” the risk avoided or capability unlocked.
- **Acceptance criteria** â€” how you know it is done.

Items within a phase are ordered by dependency (upstream first).  
Do not begin Phase 2 until all Phase 1 correctness items are green.

---

## Phase 1 â€” Correctness & Safety (days 1â€“30)

Goal: eliminate the live correctness risks in posting, numbering, period scoping, and
the voucher-line gap before building anything new on top.

---

### [x] 1.1 Fix race-prone voucher numbering â€” done in 8b7fec5

**File:** `apps/tenant_apps/dea/services/voucher_numbering.py`

**What:**  
`generate_date_based_number` counts existing vouchers with `LIKE` pattern â€”
this is racy under any concurrent request.  Replace with a `select_for_update`
sequence row keyed on `(voucher_type, date)`, identical to `LedgerCodeSequence` in
`models/numbering.py`.  The existing `VoucherNumberSequence` model in
`models/voucher_numbering.py` can be the backing table; just route all number
generation through `select_for_update().get_or_create`.

**Why:** Two concurrent loan disbursals on the same day produce duplicate
`voucher_no`; downstream uniqueness constraint will hard-fail mid-transaction.

**Acceptance:** Run 20 concurrent voucher creates in a test; zero duplicate numbers,
zero `IntegrityError`.

---

### [x] 1.2 Harden tenant context boundaries (django-tenants aware) â€” done in 8b7fec5

**Files:**  
- `apps/tenant_apps/dea/models/period.py`  
- `apps/tenant_apps/dea/posting/engine.py`  
- `apps/tenant_apps/dea/services/post_doc.py`  
- `apps/tenant_apps/dea/management/commands/` (tenant loops)

**What:**  
Because this project already uses schema isolation via django-tenants, do not make
workspace FK retrofit a blocker for Phase 1. Instead, harden tenant context where
schema isolation can be bypassed operationally:
- Ensure all DEA critical entry points assert active tenant schema before work starts
    (posting, period close, accrual triggers, management commands).
- Add explicit tenant iteration + schema switching in scheduled/CLI jobs.
- Add defensive assertions in `close_period` / `lock_period` / `unlock_period` so
    operations fail fast if tenant context is missing or inconsistent.
- Add tenant-safe logging context (schema_name + tenant id) for posting/close paths.

**Why:** With django-tenants, the primary risk is no longer row-level leakage inside
tenant schema queries; it is wrong schema context in jobs/signals/integrations.

**Acceptance:**  
- Two tenants can have identical period dates/codes in separate schemas with no conflict.  
- Running DEA management jobs without tenant context fails safely.  
- Running jobs with explicit tenant iteration only mutates that tenant's schema.

---

### 1.3 Make the posting engine write period on the JournalEntry

**File:** `apps/tenant_apps/dea/posting/engine.py` â†’ `_write_journal_entry`

**What:**  
`JournalEntry.objects.create` in `_write_journal_entry` does not pass `period`.
The `save()` override auto-assigns it, but that lookup fires an extra query and can
silently assign the wrong period if `voucher_date` is absent.  Pass `period` explicitly:

```python
period = AccountingPeriod.objects.get_period_for_date(
    ctx.voucher.voucher_date
)
if not period:
    raise PostingError(f"No open period for {ctx.voucher.voucher_date}")
je = JournalEntry.objects.create(
    voucher=ctx.voucher,
    posted_by_id=ctx.user_id,
    period=period,
)
```

**Why:** Removes the auto-assign fallback path, which silently posts to whatever period
happens to be open at save time â€” incorrect when backfilling old dates.

**Acceptance:** Post a voucher dated in a closed prior period â†’ `PostingError` raised.
Post a current-date voucher â†’ JE has correct period FK.

---

### 1.4 Canonicalize the VoucherLine model

**File:** `apps/tenant_apps/dea/models/voucher.py` (add), `forms_vouchers.py` (update)

**What:**  
Currently `_get_line_items()` returns an empty list (confirmed in `VOUCHER_TODO.md`).
Add a proper `VoucherLine` model:

```python
class VoucherLine(models.Model):
    voucher    = models.ForeignKey(Voucher, on_delete=models.CASCADE, related_name='lines')
    ledger     = models.ForeignKey('Ledger', on_delete=models.PROTECT)
    account    = models.ForeignKey('Account', null=True, blank=True, on_delete=models.PROTECT)
    side       = models.CharField(max_length=2, choices=[('Dr','Debit'),('Cr','Credit')])
    amount     = MoneyField(max_digits=14, decimal_places=2, default_currency='INR')
    narration  = models.CharField(max_length=255, blank=True)
    tax_code   = models.CharField(max_length=20, blank=True)  # GST/TDS ref
    class Meta:
        ordering = ['id']
```

Update `posting/engine.py` â†’ `_write_journal_entry` to derive `PostingBundle` from
`voucher.lines.all()` when the rule returns an empty bundle (manual vouchers).  
Update `forms_vouchers.py` to use an inline formset for `VoucherLine`.

**Why:** Without this model, manual journal entries have no line-item storage. The
`_get_line_items()` stub silently produces empty postings.

**Acceptance:** Create a manual journal voucher with 2 lines (Dr Cash, Cr Equity);
post it; verify `LedgerTransaction` rows exist for both sides.

#### 1.4.A VoucherLine contract (exact fields)

```python
class VoucherLine(models.Model):
    class LineSide(models.TextChoices):
        DR = "Dr", "Debit"
        CR = "Cr", "Credit"

    voucher = models.ForeignKey(
        "Voucher",
        on_delete=models.CASCADE,
        related_name="lines",
    )
    line_no = models.PositiveIntegerField(help_text="1-based sequence within voucher")
    side = models.CharField(max_length=2, choices=LineSide.choices)

    ledger = models.ForeignKey("Ledger", on_delete=models.PROTECT, related_name="voucher_lines")
    account = models.ForeignKey(
        "Account",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="voucher_lines",
        help_text="Optional party/subledger attribution",
    )

    amount = MoneyField(max_digits=14, decimal_places=2, default_currency="INR")
    amount_base = MoneyField(
        max_digits=14,
        decimal_places=2,
        default_currency="INR",
        null=True,
        blank=True,
        help_text="Base-currency amount for reporting and balancing checks",
    )
    exchange_rate = models.DecimalField(max_digits=12, decimal_places=6, default=1)

    tax_code = models.CharField(max_length=20, blank=True)
    narration = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["line_no", "id"]
        constraints = [
            models.UniqueConstraint(fields=["voucher", "line_no"], name="uniq_voucher_line_no"),
            models.CheckConstraint(condition=models.Q(amount__gt=0), name="voucherline_amount_positive"),
        ]
        indexes = [
            models.Index(fields=["voucher", "side"]),
            models.Index(fields=["ledger", "side"]),
            models.Index(fields=["account", "side"]),
        ]
```

Validation rules:
- Voucher in `POSTED` or `REVERSED` status cannot add/edit/delete lines.
- Per currency and per base currency: total Dr must equal total Cr.
- At least one Dr and one Cr line is mandatory.

#### 1.4.B Posting materialization service (new)

**File to create:** `apps/tenant_apps/dea/services/materialize_journal.py`

```python
@transaction.atomic
def materialize_journal_from_voucher_lines(*, voucher, posted_by, period=None):
    """
    Source of truth: voucher.lines.
    Creates JournalEntry + LedgerTransaction + AccountTransaction.
    """
```

Required steps:
1. Lock voucher row and related voucher lines (`select_for_update`) to avoid concurrent post.
2. Validate balanced totals (Dr == Cr) by currency and by base currency.
3. Resolve or validate period (from voucher date) and create `JournalEntry`.
4. Build `LedgerTransaction` rows by pairing Dr lines with Cr lines using a deterministic greedy split algorithm.
5. Build `AccountTransaction` rows from every voucher line that has `account` set.
6. Mark voucher status `POSTED` and persist posting metadata.

#### 1.4.C Deterministic pairing algorithm (for dual-leg `LedgerTransaction`)

Your `LedgerTransaction` model stores one debit ledger and one credit ledger per row.
`VoucherLine` is single-sided, so posting must pair lines:

```python
def pair_lines(dr_lines, cr_lines):
    i = j = 0
    while i < len(dr_lines) and j < len(cr_lines):
        dr = dr_lines[i]
        cr = cr_lines[j]
        amt = min(dr.remaining, cr.remaining)

        yield LedgerTransaction(
            ledgerno_dr=dr.ledger,
            ledgerno=cr.ledger,
            amount=amt,
            amount_base=min(dr.remaining_base, cr.remaining_base),
        )

        dr.remaining -= amt
        cr.remaining -= amt
        if dr.remaining == 0:
            i += 1
        if cr.remaining == 0:
            j += 1
```

Determinism requirement:
- Sort debit and credit lines by `(line_no, id)` before pairing.
- This ensures identical voucher lines always materialize identical ledger transactions.

#### 1.4.D AccountTransaction generation rule

For each `VoucherLine` where `account is not null`:
- Create one `AccountTransaction` row.
- `XactTypeCode` derives from `side` (`Dr`/`Cr`).
- `ledgerno` comes from `VoucherLine.ledger`.
- `amount` uses `VoucherLine.amount` in line currency.

This keeps subledger attribution independent from dual-leg pairing splits.

#### 1.4.E Engine integration cut-over

**File:** `apps/tenant_apps/dea/posting/engine.py`

Cut-over sequence:
1. For manual voucher and JournalEntryVoucher paths, require `voucher.lines.exists()`.
2. Replace direct bundle-to-transaction write path with:
   - rule computes/populates `VoucherLine` rows (or they already exist from UI)
   - call `materialize_journal_from_voucher_lines(...)`
3. Keep existing `PostingBundle` support temporarily for backward compatibility,
   but convert bundle output into `VoucherLine` first and only then materialize JE.

Acceptance add-on:
- Reposting same draft voucher with unchanged lines must produce identical transaction set.
- Any line change before posting must change fingerprint and posting result predictably.

---

### [x] 1.5 Idempotency key uniqueness at DB level â€” done in e45883a

**File:** `apps/tenant_apps/dea/models/voucher.py`

**What:**  
Add a DB-level unique constraint on `fingerprint` per `(doc_content_type, doc_object_id)`:

```python
constraints = [
    # existing
    models.UniqueConstraint(
        fields=['doc_content_type', 'doc_object_id'],
        condition=models.Q(status='POSTED'),
        name='unique_posted_voucher_per_doc',
    ),
    # new
    models.UniqueConstraint(
        fields=['fingerprint'],
        condition=models.Q(status__in=['POSTED','CORRECTED']),
        name='unique_fingerprint_active',
    ),
]
```

**Why:** Application-level idempotency check in `engine.py` has a TOCTOU window.
DB constraint is the last line of defence.

**Acceptance:** Attempt to insert two posted vouchers with the same fingerprint â†’
`IntegrityError` at DB level, not silently admitted.

---

### [x] 1.6 Remove `print()` calls from hot paths â€” done in e45883a

**File:** `apps/tenant_apps/dea/models/ledger.py` â†’ `calculate_balance`

**What:** Delete the two `print(...)` lines inside `calculate_balance`. Replace with
`logger.debug(...)`.

**Why:** `print()` writes to stdout on every balance calculation; blocks WSGI thread
and leaks internal data in logs.

**Acceptance:** No `print` calls remain in `models/ledger.py`.

---

### [x] 1.7 Fix period navigation and remove stale workspace assumptions â€” done in e45883a

**File:** `apps/tenant_apps/dea/models/period.py`

**What:**  
Both methods reference `self.workspace` even though it is not active. Remove stale
references and keep period navigation schema-local:

```python
def get_next_period(self):
    query = AccountingPeriod.objects.filter(start_date__gt=self.end_date)
    return query.order_by('start_date').first()
```

Mirror for `get_previous_period`.

**Why:** Current code can crash with `AttributeError` and also implies a
multi-tenant filter model that does not match django-tenants schema isolation.

**Acceptance:** `get_errors` on `period.py` returns zero errors; navigation tests pass.

---

### [x] 1.8 Wire DEA period-close to interest accrual catch-up â€” done in 8b7fec5

**File:** `apps/tenant_apps/dea/views/period.py` (close action handler)  
**Ref:** `/memories/repo/girvi-interest-accrual-notes.md` â€” "DEA period-close UI in
`views/period.py` is still not wired to call `InterestAccrualService` directly."

**What:**  
In the period-close view (before calling `period.close_period()`), call:

```python
from apps.tenant_apps.girvi.service_modules.accrual import InterestAccrualService
InterestAccrualService(
    tenant=request.tenant,
    as_of_date=period.end_date,
    post_to_accounting=True,
).execute()
```

Wrap in a try/except so accrual failure surfaces as a user-visible warning but does
not block close if admin force-closes.

**Why:** If accruals are not caught up before close, the P&L for the period is wrong
and retained earnings carry-forward is understated.

**Acceptance:** Close a period that has open loans with unposted accruals â†’ accruals
auto-post first, then period closes with correct retained-earnings total.

---

### [x] 1.9 Prevent period close with unposted DRAFT vouchers â€” done in 8b7fec5

**File:** `apps/tenant_apps/dea/models/period.py` â†’ `close_period`

**What:**  
Add a pre-close guard at the start of `close_period`:

```python
unposted = Voucher.objects.filter(
    voucher_date__gte=self.start_date,
    voucher_date__lte=self.end_date,
    status=VoucherStatus.DRAFT,
)
if unposted.exists():
    raise ValidationError(
        f"{unposted.count()} unposted draft vouchers exist in this period. "
        "Post or delete them before closing."
    )
```

**Why:** Closing with orphaned drafts silently understates/overstates the period P&L.

**Acceptance:** Attempt period close with one DRAFT voucher in range â†’ `ValidationError`
naming the count; close succeeds after the draft is posted.

---

### Phase 1 Checkpoint

Before moving to Phase 2, verify:

| Check | Command / Test |
|---|---|
| No duplicate voucher numbers under concurrency | `python manage.py test dea.tests.test_numbering` |
| Tenant context isolation (schema) | `python manage.py test dea.tests.test_period_isolation` |
| VoucherLine â†’ JE materialization | `python manage.py test dea.tests.test_voucher_line_posting` |
| Period close with draft guard | `python manage.py test dea.tests.test_period_close` |
| No `print()` in hot paths | `grep -rn "print(" apps/tenant_apps/dea/models/` |

---

## Phase 2 â€” Accounting Completeness (days 31â€“60)

Goal: make the system usable by an accountant end-to-end for a full business month.

---

### [x] 2.1 Pre-close checklist workflow â€” done in 4f5ecff

**Files to create:**  
- `apps/tenant_apps/dea/services/pre_close.py`  
- `apps/tenant_apps/dea/views/period.py` (update close action)  
- `templates/dea/period/pre_close_checklist.html`

**What:**  
Build a `PreCloseChecklist` service that returns a structured list of checks with
pass/fail/warning status before close is allowed:

```python
class PreCloseChecklist:
    checks = [
        UnpostedVouchersCheck,       # from 1.9
        UnaccrueInterestCheck,       # calls InterestAccrualService.dry_run()
        UnreconciledBankItemsCheck,  # count from bank reconciliation (Phase 2.4)
        DepreciationPostedCheck,     # check depreciation journal for period
        PrepaidExpiredCheck,         # check prepaid schedules expiring in period
        BalanceSheetTrialCheck,      # Assets == Liabilities + Equity
    ]

    def run(self, period, tenant) -> list[CheckResult]:
        ...
```

The close view renders this checklist; user must acknowledge warnings before
proceeding. Fatal checks block close entirely.

**Acceptance:** A period-close page shows a checklist with green/amber/red items
before the user can submit the close.

---

### [x] 2.2 Depreciation engine â€” done in c9b6cbc

**Files to create:**  
- `apps/tenant_apps/dea/models/asset.py` (`FixedAsset`, `DepreciationSchedule`)  
- `apps/tenant_apps/dea/services/depreciation.py`  
- `apps/tenant_apps/dea/posting/rules/depreciation.py`

**What:**  
Minimum viable depreciation:

```python
class FixedAsset(BusinessDoc):
    name            = CharField(max_length=200)
    purchase_date   = DateField()
    cost            = MoneyField(...)
    salvage_value   = MoneyField(...)
    useful_life_months = PositiveIntegerField()
    method          = CharField(choices=['SLM', 'WDV'])
    ledger          = ForeignKey(Ledger, ...)          # asset GL ledger
    acc_dep_ledger  = ForeignKey(Ledger, ...)          # accumulated depreciation ledger
    dep_exp_ledger  = ForeignKey(Ledger, ...)          # depreciation expense ledger
```

`DepreciationService.post_for_period(asset, period)` calculates monthly charge
and fires `create_and_post_voucher_for_doc`.

Posting rule: `DR Depreciation Expense / CR Accumulated Depreciation`.

Pre-close checklist (2.1) calls `DepreciationService.get_unposted_for_period`
to surface missing depreciation.

**Acceptance:** Create a fixed asset; run depreciation for 3 periods;
GL shows accumulated depreciation growing by the correct SLM amount each period.

---

### [x] 2.3 Prepaid expense scheduler â€” done in 3d1542f

**Files to create:**  
- `apps/tenant_apps/dea/models/prepaid.py` (`PrepaidExpense`, `PrepaidScheduleLine`)  
- `apps/tenant_apps/dea/services/prepaid.py`

**What:**  
```python
class PrepaidExpense(BusinessDoc):
    name          = CharField(max_length=200)
    start_date    = DateField()
    end_date      = DateField()
    total_amount  = MoneyField(...)
    prepaid_ledger = ForeignKey(Ledger, ...)    # asset (prepaid A/c)
    expense_ledger = ForeignKey(Ledger, ...)    # expense A/c
```

`PrepaidService.post_for_period(prepaid, period)`:  
Calculates the proportion for this period and posts:
`DR Expense Ledger / CR Prepaid Ledger`.

**Acceptance:** Create a 12-month prepaid insurance; run for month 1; verify prepaid
ledger decreases by 1/12 and expense increases by 1/12.

---

### [x] 2.4 Bank reconciliation subsystem â€” done in 0d360d9

**Files to create:**  
- `apps/tenant_apps/dea/models/bank.py` (`BankAccount`, `BankStatementLine`, `ReconciliationMatch`)  
- `apps/tenant_apps/dea/services/reconciliation.py`  
- `apps/tenant_apps/dea/views/reconciliation.py`  
- `templates/dea/reconciliation/`

**What:**  
`BankStatementLine`: imported CSV row from the bank (date, description, amount, running balance).  
`ReconciliationMatch`: M2M between `BankStatementLine` and `LedgerTransaction`.

`ReconciliationService`:
- `auto_match(bank_account, period)` â€” matches by date + amount with configurable
  tolerance.
- `get_unmatched_bank_lines(bank_account, period)` â€” unmatched = potential missing vouchers.
- `get_unmatched_gl_lines(ledger, period)` â€” GL entries not matched to any bank line.

UI: side-by-side bank vs GL, drag-to-match, mark-reconciled, create-missing-voucher
from unmatched bank line.

**Acceptance:** Import a bank CSV; auto-match finds 80%+ matches by date+amount;
unmatched items appear in exception list; mark-reconciled flag persists.

---

### [x] 2.5 Complete financial reports â€” done in 0d312f7

**Files to update:** `apps/tenant_apps/dea/views/reports.py` + templates under
`templates/dea/reports/`

Each report must:
- Accept `period` or `(start_date, end_date)` as input.
- Use `LedgerStatement` snapshots for closed periods (not live transaction re-sums).
- Drill down: clicking a line item opens the GL account history filtered to that period.

#### 2.5.1 Trial Balance
Already partially implemented. Add:
- Comparative column (prior period).
- Export to CSV/Excel.
- Highlight out-of-balance rows in red.

#### 2.5.2 Profit & Loss
```
Revenue
  Operating Revenue         (ledgers where is_operating_revenue=True)
  Other Income
Gross Profit
Cost of Goods Sold          (ledgers where is_direct_expense=True)
Gross Margin
Operating Expenses          (ledgers where is_operating_expense=True)
Operating Profit
Finance Costs               (interest expense ledgers)
Net Profit Before Tax
Tax Provision
Net Profit After Tax
```
Source: `Ledger.is_operating_revenue`, `is_direct_expense`, `is_operating_expense`
flags already in `models/ledger.py`.

#### 2.5.3 Balance Sheet
```
Assets
  Current Assets            (is_current_asset=True, AccountType=Asset)
  Fixed Assets              (is_current_asset=False)
  Accumulated Depreciation  (new from 2.2)
Liabilities
  Current Liabilities       (is_current_liability=True, AccountType=Liability)
  Long-term Liabilities
Equity
  Capital + Retained Earnings
```

#### 2.5.4 Cash Flow Statement (indirect method)
- Start with Net Profit.
- Adjustments: +/- non-cash items (depreciation, accruals).
- Working capital changes: AR, AP, inventory.
- Investing: fixed asset purchases.
- Financing: loan proceeds / repayments.

#### 2.5.5 AR Aging (per Account)
Already has summary; add per-invoice detail:
`Account â†’ SalesInvoiceVoucher â†’ outstanding_amount, days_outstanding, bucket (0-30/31-60/61-90/90+)`.

#### 2.5.6 AP Aging (per Account)
Mirror of AR for creditors.

**Acceptance:** All six reports render for a closed period; BS balances (Assets == L+E);
P&L net profit matches retained earnings delta between periods.

---

### [x] 2.6 Inline VoucherLine formset in the voucher create/edit view â€” done in 77e27d0

**File:** `apps/tenant_apps/dea/views/voucher.py`, `templates/dea/vouchers/voucher_form.html`

**What:**  
The create/edit view must use a `VoucherLineFormSet` (inline formset for `VoucherLine`).
Add a running debit/credit subtotal with JS validation that forces balance (Dr = Cr)
before the POST is accepted.  
Add "+ Add Line" / "Delete Line" AJAX buttons.

**Why:** Without this, users cannot enter manual journal entries from the UI.

**Acceptance:** Open `/dea/vouchers/create/`; add 3 lines; the balance indicator shows
green when Dr == Cr; submit creates a voucher with 3 `VoucherLine` rows and a correct JE.

---

### [x] 2.7 AR/AP settlement workflow â€” done in 3d40a55

**File:** `apps/tenant_apps/dea/models/payment.py`, `apps/tenant_apps/dea/services/settlement.py`

**What:**  
When a `PaymentVoucher` is posted against a `SalesInvoiceVoucher`, currently
`is_fully_paid` is not reliably updated. Build a `SettlementService`:

```python
class SettlementService:
    def settle(self, payment: PaymentVoucher) -> None:
        invoice = payment.source_document
        invoice.received_amount += payment.total_amount
        if invoice.received_amount >= invoice.total_amount:
            invoice.is_fully_paid = True
        invoice.save(update_fields=['received_amount', 'is_fully_paid'])
```

Call from `posting/rules/sales_invoice.py` and `givenloan_receipt.py` after JE creation.

**Acceptance:** Post two partial payments totalling the invoice amount;
`SalesInvoiceVoucher.is_fully_paid` becomes `True` after the second payment.

---

### [x] 2.8 Posting rule integration for automatic settlement â€” done in 2bdb544

**Files:** `apps/tenant_apps/dea/posting/engine.py` (modified), `apps/tenant_apps/dea/test_settlement_integration.py` (new)

**What:**  
Integrate `SettlementService` into the posting engine to automatically settle invoices when payments are posted.
After `JournalEntry` materialization in `BasePostingEngine.post()`, check if the voucher's business document is a `PaymentVoucher`.
If so, call `SettlementService().settle(payment_voucher)` to update invoice state:
- `SalesInvoiceVoucher.received_amount` += payment amount
- `PurchaseInvoiceVoucher.paid_amount` += payment amount
- Set `is_fully_paid = True` when payment >= invoice total

Settlement failures are logged as warnings but do not block posting (JournalEntry always created).

**Why:** Without this integration, the AR/AP settlement service exists but is never called,
and invoices remain marked unpaid even after full payment posting.

**Acceptance:** Post a `PaymentVoucher` against a `SalesInvoiceVoucher` for the full invoice amount;
verify `is_fully_paid` becomes `True` and `received_amount` is updated.

---

### Phase 2 Checkpoint

| Check | How |
|---|---|
| BS balances for a closed test period | Manual + automated assertion in test |
| P&L net profit matches RE delta | Automated test using two periods |
| Depreciation posts and accumulates | `test_depreciation_service.py` |
| Bank reconciliation: import + auto-match | `test_reconciliation.py` (9 smoke tests) |
| Manual JE via formset, JE materializes | Selenium or manual smoke |
| AR settlement marks invoice paid | `test_settlement.py` + `test_settlement_integration.py` |
| Payment posting triggers automatic settlement | `test_settlement_integration.py` (5 E2E tests) |

---

## Phase 3 â€” Hardening (days 61â€“90)

Goal: make the system audit-safe, operationally resilient, and maintainable at scale.

---

### 3.1 Immutable audit event log

**File:** `apps/tenant_apps/dea/models/audit.py` (create)

**What:**  
```python
class AccountingAuditEvent(models.Model):
    class EventType(models.TextChoices):
        VOUCHER_CREATED  = 'VOUCHER_CREATED'
        VOUCHER_POSTED   = 'VOUCHER_POSTED'
        VOUCHER_REVERSED = 'VOUCHER_REVERSED'
        PERIOD_CLOSED    = 'PERIOD_CLOSED'
        PERIOD_LOCKED    = 'PERIOD_LOCKED'
        PERIOD_UNLOCKED  = 'PERIOD_UNLOCKED'
        LEDGER_CREATED   = 'LEDGER_CREATED'
        OPENING_BAL_SET  = 'OPENING_BAL_SET'

    event_type  = CharField(max_length=40, choices=EventType.choices)
    actor       = ForeignKey(User, on_delete=PROTECT)
    tenant      = ForeignKey(Tenant, on_delete=PROTECT)
    object_id   = PositiveIntegerField()
    object_type = ForeignKey(ContentType, on_delete=PROTECT)
    payload_before = JSONField(null=True)
    payload_after  = JSONField()
    ip_address  = GenericIPAddressField(null=True)
    occurred_at = DateTimeField(auto_now_add=True)

    class Meta:
        # Never delete audit rows
        default_permissions = ('view',)
```

Hook into `posting/engine.py`, `period.py` `close_period`/`lock_period`/`unlock_period`.

**Why:** Without this, "who posted what and when" is answered only by scanning
`JournalEntry.posted_by` â€” no before/after state, no reason, no IP.

**Acceptance:** Post a voucher; verify `AccountingAuditEvent` row exists with
correct `payload_after`; attempt to delete the audit row â†’ `PermissionDenied`.

---

### 3.2 Approval matrix for high-risk actions

**Files:**  
- `apps/tenant_apps/dea/models/approval.py`  
- `apps/tenant_apps/dea/services/approval.py`  
- Update `posting/engine.py` to check approval status before posting

**What:**  
Define `ApprovalPolicy`:

```python
class ApprovalPolicy(models.Model):
    voucher_type = ForeignKey(VoucherType, on_delete=CASCADE)
    min_amount   = MoneyField(...)          # threshold triggering approval
    approver_role = CharField(max_length=50) # e.g. 'accounting_manager'
    tenant        = ForeignKey(Tenant, ...)
```

`ApprovalRequest`: state machine `PENDING â†’ APPROVED / REJECTED` with `approver`,
`reason`, `approved_at`.

Posting engine checks: if `ApprovalPolicy` exists for this voucher type + amount range
and no `APPROVED` `ApprovalRequest` exists, raise `ApprovalRequiredError` (not
`PostingError`) so the view can redirect to approval request screen.

**Acceptance:** Create approval policy for JVs > â‚¹1L; try to post such a JV â†’
approval screen; approve it; post completes.

---

### 3.3 Role-based access control

**File:** `apps/tenant_apps/dea/apps.py` + permission checks in all views

**What:**  
Define accounting roles via Django groups:

| Role | Permissions |
|---|---|
| `accounting_viewer` | view all DEA objects |
| `accounting_clerk` | create/edit DRAFT vouchers |
| `accountant` | + post, reverse, manage accounts |
| `accounting_manager` | + close period, approve JVs, set opening balances |
| `accounting_admin` | + lock/unlock period, edit COA |

Use `@permission_required` or CBV `permission_required` on every view.  
Management command `python manage.py setup_accounting_roles` creates the groups.

**Acceptance:** Log in as `accounting_viewer`; confirm POST to `/dea/vouchers/create/`
returns 403; log in as `accountant`; confirm it returns 200.

---

### 3.4 Foreign currency revaluation

**File:** `apps/tenant_apps/dea/services/revaluation.py`  
**File:** `apps/tenant_apps/dea/posting/rules/revaluation.py`

**What:**  
At period end, for all ledgers with non-INR balances, calculate the unrealised
forex gain/loss using the period-end `ExchangeRate`:

```
DR/CR  Foreign Currency Ledger  (revaluation delta)
CR/DR  Forex Revaluation Gain/Loss A/c
```

Include in pre-close checklist (2.1) as a required action when open forex balances exist.

**Acceptance:** Create a USD ledger balance; set a new USD/INR rate; run revaluation;
verify revaluation GL entry posts to `Forex Revaluation Gain/Loss`.

---

### 3.5 Recurring voucher engine

**File:** `apps/tenant_apps/dea/models/recurring.py`, `services/recurring.py`

**What:**  
```python
class RecurringVoucherTemplate(models.Model):
    voucher_type    = ForeignKey(VoucherType, ...)
    frequency       = CharField(choices=['MONTHLY','QUARTERLY','ANNUALLY'])
    next_due_date   = DateField()
    active          = BooleanField(default=True)
    lines           = # snapshot of VoucherLine data as JSON
```

`RecurringVoucherService.run_due(as_of_date, tenant)`:
- Finds templates due â‰¤ as_of_date.
- Creates a DRAFT voucher from the template lines.
- Advances `next_due_date`.

Integrate with the management command scheduler or Celery.

**Acceptance:** Create a monthly rent template; run service for next 3 months;
3 DRAFT vouchers created with correct dates.

---

### 3.6 Performance: materialise ledger balances

**File:** `apps/tenant_apps/dea/models/ledger.py` + new `LedgerBalance` model
(already referenced in `opening_balance.py` imports but may not be fully wired)

**What:**  
Replace `calculate_balance` (which re-sums all transactions every call) with a
`LedgerBalance` snapshot updated by a post-JE signal:

```python
@receiver(post_save, sender=LedgerTransaction)
def refresh_ledger_balance(sender, instance, **kwargs):
    LedgerBalance.objects.update_or_create(
        ledger=instance.ledgerno_dr,
        currency=instance.amount_currency,
        defaults={'balance': ...}
    )
    LedgerBalance.objects.update_or_create(
        ledger=instance.ledgerno,
        ...
    )
```

Similarly for `AccountBalance` from `AccountTransaction`.

**Why:** Trial balance and dashboard currently aggregate every transaction on every
page load. At 100k+ transactions this becomes unacceptably slow.

**Acceptance:** With 50k transactions in test DB, trial balance renders in < 200ms.

---

### 3.7 Suspense account and exception handling

**File:** `apps/tenant_apps/dea/models/ledger.py` (add suspense ledger seed)  
**File:** `apps/tenant_apps/dea/posting/engine.py` (error recovery path)

**What:**  
When posting fails a balance assertion but the business event must be recorded
(e.g. partial import from legacy system), post the imbalance to a `Suspense` ledger
instead of raising an uncaught exception. Log to `AccountingAuditEvent`.

A `Suspense` dashboard widget shows total suspense balance â€” anything non-zero
is a required investigation item.

**Acceptance:** Force an imbalanced bundle through the engine in test mode;
suspense ledger receives the difference; audit event is recorded.

---

### 3.8 API contracts for external integrations

**File:** `apps/tenant_apps/dea/api/` (create package)

**What:**  
Minimum DRF or Ninja endpoints for:

| Endpoint | Purpose |
|---|---|
| `GET /api/dea/trial-balance/?period=N` | Programmatic trial balance |
| `GET /api/dea/ledger/{id}/transactions/` | Ledger transaction history |
| `POST /api/dea/vouchers/` | Create + post a voucher from external system |
| `GET /api/dea/periods/current/` | Current open period metadata |

All endpoints: tenant-scoped, token-authenticated, rate-limited.

**Acceptance:** Postman collection covering all four endpoints passes with a
valid tenant API token; invalid token returns 401.

---

### Phase 3 Checkpoint

| Check | How |
|---|---|
| Audit event for every post/reverse/close | Check `AccountingAuditEvent` count in tests |
| Approval blocks high-value JVs | `test_approval_matrix.py` |
| RBAC: viewer cannot post | Permission tests |
| Revaluation posts correctly | `test_revaluation.py` |
| Trial balance < 200ms at 50k txns | `locust` or `pytest-benchmark` |

---

## Dependency map

```
Phase 1 (correctness)
â”‚
â”œâ”€â”€ 1.1 Numbering         â† no dep
â”œâ”€â”€ 1.2 Tenant context    â† no dep
â”œâ”€â”€ 1.3 Period in engine  â† needs 1.2
â”œâ”€â”€ 1.4 VoucherLine       â† no dep
â”œâ”€â”€ 1.5 Fingerprint DB    â† no dep
â”œâ”€â”€ 1.6 Remove print()    â† no dep
â”œâ”€â”€ 1.7 Period nav guard  â† no dep
â”œâ”€â”€ 1.8 Accrual wiring    â† needs 1.3
â””â”€â”€ 1.9 Draft guard       â† no dep

Phase 2 (completeness)
â”‚
â”œâ”€â”€ 2.1 Pre-close checklist  â† needs 1.8, 1.9
â”œâ”€â”€ 2.2 Depreciation         â† needs 1.4 (VoucherLine)
â”œâ”€â”€ 2.3 Prepaid              â† needs 1.4
â”œâ”€â”€ 2.4 Bank reconciliation  â† needs 1.4
â”œâ”€â”€ 2.5 Financial reports    â† needs 1.3, 2.2
â”œâ”€â”€ 2.6 VoucherLine formset  â† needs 1.4
â””â”€â”€ 2.7 AR/AP settlement     â† needs 1.4

Phase 3 (hardening)
â”‚
â”œâ”€â”€ 3.1 Audit log            â† needs Phase 2 complete
â”œâ”€â”€ 3.2 Approval matrix      â† needs 3.1
â”œâ”€â”€ 3.3 RBAC                 â† needs 3.1
â”œâ”€â”€ 3.4 Revaluation          â† needs 2.5
â”œâ”€â”€ 3.5 Recurring vouchers   â† needs 2.6
â”œâ”€â”€ 3.6 Balance snapshots    â† needs Phase 2 complete
â””â”€â”€ 3.7 Suspense             â† needs 3.1
```

---

## Items explicitly deferred (not in this 90-day window)

| Item | Reason |
|---|---|
| Inventory / COGS tracking | Requires product catalogue model; Phase 4 |
| Multi-currency cash flow statement | Indirect method requires revaluation first (Phase 3.4) |
| Budget vs actual | Needs a budget model; Phase 4 |
| External bank feed integration | Third-party API; Phase 4 |
| Tally / QuickBooks import | Data migration tool; Phase 4 |
| Predictive analytics / forecasting | Requires 6+ months of historical data; Phase 5 |

---

*This document should be updated after each completed item. Mark `[x]` and record the
commit hash next to it.*

