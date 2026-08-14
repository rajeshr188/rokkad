---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Command + Preview + Result Pattern in Girvi

This note explains why the `Command` + `Preview` + `Result` dataclass pattern is a strong fit for Girvi and shows the real loan-creation flow already in the codebase.

---

## Real Example: Loan Creation

### Files involved

- `apps/tenant_apps/girvi/views/loan.py`
- `apps/tenant_apps/girvi/service_modules/creation.py`
- `apps/tenant_apps/girvi/tests/test_loan_creation_service.py`

### The dataclasses

In `service_modules/creation.py` the loan-create workflow is modeled with three explicit contracts:

```python
@dataclass
class LoanCreateCommand:
    borrower: object
    series: object
    loan_date: object
    tenure: int
    interest_type: str
    created_by: object
    loan_id: str = ""
    initial_items: list[LoanItemCreateInput] = dc_field(default_factory=list)

@dataclass
class LoanCreatePreview:
    is_valid: bool
    expected_loan_id: str = ""
    borrower_credit_limit: object | None = None
    borrower_current_balance: object | None = None
    borrower_available_credit: object | None = None
    initial_item_count: int = 0
    initial_item_total: object | None = None
    warnings: list[str] = dc_field(default_factory=list)
    errors: list[str] = dc_field(default_factory=list)

@dataclass
class LoanCreateResult:
    success: bool
    message: str
    loan: object | None = None
    errors: list[str] = dc_field(default_factory=list)
```

---

## How the flow works in practice

### 1) The view builds a `Command`

`views/loan.py` converts form data into a structured service input:

```python
def _build_loan_create_command(form, user, item_formset=None):
    return LoanCreateCommand(
        borrower=form.cleaned_data["borrower"],
        series=form.cleaned_data["series"],
        loan_date=form.cleaned_data["loan_date"],
        tenure=form.cleaned_data["tenure"],
        interest_type=form.cleaned_data["interest_type"],
        created_by=user,
        loan_id=form.cleaned_data.get("loan_id") or "",
        initial_items=_extract_initial_item_inputs(item_formset),
    )
```

### 2) The view asks for a `Preview` before saving

The same module uses:

```python
creation_preview = LoanCreationService.preview(
    _build_loan_create_command(form, request.user, item_formset)
)
```

This preview gives the UI a safe read-only summary such as:

- expected next loan ID
- borrower credit details
- initial item count
- initial item total
- warnings/errors before commit

That is very useful in Girvi because loan creation is not just one row insert; it involves borrower state, series rules, dates, and optional initial pledged items.

### 3) The view executes and receives a `Result`

When the POST is valid, the view does:

```python
result = LoanCreationService.execute(
    _build_loan_create_command(form, request.user, item_formset)
)
```

And then handles one predictable output shape:

```python
if result.success:
    messages.success(request, result.message)
    return _loan_detail_redirect_response(result.loan.id)

form.add_error(None, result.message)
```

---

## Why this pattern is a strong fit for Girvi

Girvi workflows are multi-step business operations, not simple CRUD. Loan creation, renewal, release, split, and merge all benefit from a clearer contract.

### 1) Clear input boundary
A `Command` keeps the service independent from `request.POST`, forms, and template concerns.

**Benefit:** the service receives normalized business input instead of raw web-layer data.

### 2) Safe preview-before-commit flow
A `Preview` supports review screens, HTMX updates, warnings, and pre-save calculations without writing to the database.

**Benefit:** users can see loan ID, totals, and warnings before anything is committed.

### 3) Stable output contract
A `Result` gives the caller one predictable object to inspect.

**Benefit:** views no longer need ad-hoc tuples, dicts, exceptions, and side-effect guessing.

### 4) Better tests
`tests/test_loan_creation_service.py` can directly construct `LoanCreateCommand` values and assert on `preview` / `execute` behavior.

**Benefit:** business rules are tested without going through the whole HTTP stack every time.

### 5) Easier reuse across UI/API flows
The same service contract can be used from:

- Django forms/views
- HTMX preview endpoints
- future DRF/API endpoints
- background jobs or imports

**Benefit:** one workflow implementation, multiple entry points.

---

## Rule of thumb for future Girvi services

Use the pattern when the workflow has **all or most** of these characteristics:

- multiple inputs
- validation or normalization
- preview/review UI
- warnings or non-fatal issues
- transaction + side effects
- success/failure reporting back to a caller

Good candidates in Girvi include:

- loan creation
- renewal
- release
- split/merge
- bulk operations

For simple read-only queries, prefer `selectors.py` instead of service dataclasses.

---

## Pattern review: Renewal and Release

### Renewal flow review

**Current files:**

- `apps/tenant_apps/girvi/service_modules/renewal.py`
- `apps/tenant_apps/girvi/views/loan.py`

Renewal already follows the pattern very well:

- `LoanRenewalCommand` captures the workflow input (`source_loan_id`, payment splits, mode, notes, actor).
- `LoanRenewalPreview` calculates and exposes review data before commit:
  - outstanding principal
  - interest due
  - collateral value
  - new principal
  - validation errors
- `LoanRenewalResult` returns a stable post-execution outcome with `success`, `message`, `new_loan_id`, and warnings.

This is a strong fit because renewal is a classic Girvi workflow:

- it has multiple inputs
- it requires business-rule validation
- it benefits from a review step before changes are written
- it triggers several side effects inside one transaction

**Why it works well here:**

1. The view can ask for a preview without mutating state.
2. The renewal rules stay centralized in one service.
3. The caller receives a predictable result instead of decoding multiple side effects.

**Small improvement opportunity:**

- `LoanRenewalResult` could eventually include the actual `new_loan` object, not just `new_loan_id`, if callers need richer follow-up handling.

### Release flow review

**Current files:**

- `apps/tenant_apps/girvi/service_modules/release_lifecycle.py`
- `apps/tenant_apps/girvi/views/release.py`
- `apps/tenant_apps/girvi/service_modules/bulk_release.py`

Release currently uses a **service-first / command-style write orchestration**, but it does **not yet implement the full dataclass trio**.

Current strengths:

- release logic is no longer hidden in model side effects
- `ReleaseLifecycleService.create_release()` centralizes validation, transition execution, DB write, and accounting entry creation
- bulk release already benefits from having a dedicated orchestration service boundary

So release is in a **good architectural direction**, but compared with loan creation and renewal it is only a **partial fit** today.

**What is missing for the full pattern:**

- `ReleaseCreateCommand`
- `ReleaseCreatePreview`
- `ReleaseCreateResult`

### Why release would benefit from the full pattern

A release is not just â€œcreate one rowâ€. It often needs to answer:

- can this loan be released in the current status?
- who is receiving the release?
- what dues or constraints still apply?
- what will be posted to accounting?
- what warnings should the user see before commit?

A `Preview` object would make this especially useful for:

- release confirmation screens
- bulk release review pages
- API responses that need explainable validation feedback

A `Result` object would give consistent handling for:

- success/failure
- created release object or ID
- warnings when accounting succeeds/fails partially

### Recommendation

- **Renewal:** keep the current `Command -> Preview -> Result` structure; it is a strong example to reuse.
- **Release:** consider upgrading from `create_release(...)` to a full pattern-based contract when you next touch the release UX or bulk-release flows.

A likely future shape would be:

```python
ReleaseCreateCommand
ReleaseCreatePreview
ReleaseCreateResult
ReleaseLifecycleService.preview(command)
ReleaseLifecycleService.execute(command)
```

## Short takeaway

> In Girvi, `Command -> Preview -> Result` works well because the domain needs structured inputs, safe previews, and predictable outputs for complex financial/lifecycle workflows.

