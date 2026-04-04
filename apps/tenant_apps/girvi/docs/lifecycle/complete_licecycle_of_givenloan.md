I'll turn the lifecycle proposal into an implementation-ready state-transition matrix with guards and reversibility rules.## GivenLoan lifecycle — implementation-ready state-transition matrix

Below is a **deterministic FSM plan** for `GivenLoan`, designed to be implementable and auditable.

---

# 1) Recommended state model

## Primary lifecycle states

### Pre-activation
- `DRAFT`
- `PENDING_APPROVAL`
- `APPROVED`
- `REJECTED`
- `CANCELLED`

### Active servicing
- `ACTIVE_CURRENT`
- `ACTIVE_OVERDUE`
- `ACTIVE_NPA`

### Operational workflow states
- `CLOSURE_PENDING`
- `RENEWAL_PENDING`
- `AUCTION_INITIATED`
- `AUCTION_IN_PROGRESS`
- `AUCTION_COMPLETE`

### Terminal states
- `CLOSED`
- `RENEWED`
- `WRITTEN_OFF`

---

# 2) State meanings

| State | Meaning |
|---|---|
| `DRAFT` | Loan exists but is still editable and incomplete |
| `PENDING_APPROVAL` | Submitted for approval review |
| `APPROVED` | Approved, locked for editing, not yet disbursed |
| `REJECTED` | Not approved; terminal, no activation happened |
| `CANCELLED` | Cancelled before approval/disbursal; terminal |
| `ACTIVE_CURRENT` | Disbursed and performing normally |
| `ACTIVE_OVERDUE` | Disbursed and overdue but not yet NPA |
| `ACTIVE_NPA` | Non-performing asset / defaulted active loan |
| `CLOSURE_PENDING` | Dues settled and operational closure/release is in progress |
| `RENEWAL_PENDING` | Renewal flow is in progress but not finalized |
| `AUCTION_INITIATED` | Recovery via auction started administratively |
| `AUCTION_IN_PROGRESS` | Auction process is ongoing |
| `AUCTION_COMPLETE` | Auction concluded; recovery amount known |
| `CLOSED` | Loan fully resolved and closed |
| `RENEWED` | Source loan ended by renewal into successor loan |
| `WRITTEN_OFF` | Loss recognized; loan terminated with unrecovered balance |

---

# 3) Exact transition matrix

## A. Origination / approval

| Transition name | Allowed source state(s) | Target state | Guard conditions | Reversible? |
|---|---|---:|---|---|
| `submit_for_approval` | `DRAFT` | `PENDING_APPROVAL` | borrower exists; at least 1 collateral item; terms valid; loan amount > 0 | Yes |
| `return_to_draft` | `PENDING_APPROVAL` | `DRAFT` | reviewer/admin permission | Yes |
| `approve_loan` | `PENDING_APPROVAL` | `APPROVED` | collateral exists; valuation complete; business validations pass | Limited |
| `reject_loan` | `PENDING_APPROVAL` | `REJECTED` | rejection reason required | Normally No |
| `cancel_loan` | `DRAFT`, `PENDING_APPROVAL` | `CANCELLED` | cancel reason required | Normally No |

> **Rule:** cancellation should **not** be allowed after `APPROVED`.

---

## B. Disbursal / activation

| Transition name | Allowed source state(s) | Target state | Guard conditions | Reversible? |
|---|---|---:|---|---|
| `disburse_loan` | `APPROVED` | `ACTIVE_CURRENT` | approval exists; no blocking custody issue; disbursal amount valid; accounting succeeds | Yes, restricted |
| `undo_disbursal` | `ACTIVE_CURRENT` | `APPROVED` | no repayments; no closure/renewal/auction started; accounting reversal allowed | Yes |

> **Rule:** once approved, loan becomes effectively **non-editable** except controlled admin corrections.

---

## C. Servicing health transitions

| Transition name | Allowed source state(s) | Target state | Guard conditions | Reversible? |
|---|---|---:|---|---|
| `mark_overdue` | `ACTIVE_CURRENT` | `ACTIVE_OVERDUE` | due date/DPD threshold breached | Yes, system-driven |
| `cure_to_current` | `ACTIVE_OVERDUE`, `ACTIVE_NPA` | `ACTIVE_CURRENT` | overdue cleared / dues regularized | Yes |
| `mark_npa` | `ACTIVE_OVERDUE` | `ACTIVE_NPA` | NPA threshold breached by rule/policy | Yes, via cure |

> These should usually be **rule-driven/system transitions**, not only manual UI actions.

---

## D. Closure path

| Transition name | Allowed source state(s) | Target state | Guard conditions | Reversible? |
|---|---|---:|---|---|
| `request_closure` | `ACTIVE_CURRENT`, `ACTIVE_OVERDUE`, `ACTIVE_NPA` | `CLOSURE_PENDING` | principal/interest/charges fully settled or closure exception approved | Yes |
| `complete_closure` | `CLOSURE_PENDING` | `CLOSED` | release document created; custody available or returned; items delivered; accounting/receipt posted | Restricted |
| `reopen_from_closure_pending` | `CLOSURE_PENDING` | previous active state | closure interrupted or dues mismatch found | Yes |
| `undo_closure` | `CLOSED` | `CLOSURE_PENDING` or prior active state | admin-only; release reversal; accounting reversal; custody restored | Rare / controlled |

### Important meaning
By your definition:

> “close” = create release doc + deliver items from custody

So operationally:

- `request_closure` = financially eligible
- `complete_closure` = actual business closure execution

---

## E. Renewal path

| Transition name | Allowed source state(s) | Target state | Guard conditions | Reversible? |
|---|---|---:|---|---|
| `request_renewal` | `ACTIVE_CURRENT`, `ACTIVE_OVERDUE`, `ACTIVE_NPA` | `RENEWAL_PENDING` | renewal policy allows; collateral sufficient; user chooses renewal path | Yes |
| `complete_renewal` | `RENEWAL_PENDING` | `RENEWED` | renewal transaction succeeds; successor loan created; source linkage recorded | Restricted |
| `cancel_renewal_request` | `RENEWAL_PENDING` | prior active state | no successor loan finalized | Yes |
| `undo_renewal` | `RENEWED` | prior active state | only if successor loan has no downstream activity and all side effects reversed | Rare / controlled |

> This is better than treating `REPLEDGED` as the permanent business status of the source loan.

---

## F. Auction / recovery path

| Transition name | Allowed source state(s) | Target state | Guard conditions | Reversible? |
|---|---|---:|---|---|
| `initiate_auction` | `ACTIVE_NPA` | `AUCTION_INITIATED` | recovery approval granted; NPA confirmed | Yes |
| `start_auction` | `AUCTION_INITIATED` | `AUCTION_IN_PROGRESS` | auction process officially started | Limited |
| `cancel_auction` | `AUCTION_INITIATED` | `ACTIVE_NPA` | auction not materially progressed | Yes |
| `complete_auction` | `AUCTION_IN_PROGRESS` | `AUCTION_COMPLETE` | sale finalized; proceeds known | No in normal flow |
| `close_after_auction` | `AUCTION_COMPLETE` | `CLOSED` | recovery fully satisfies balance | No |
| `write_off_after_auction` | `AUCTION_COMPLETE` | `WRITTEN_OFF` | residual loss remains after recovery | No |

---

## G. Loss recognition / write-off

| Transition name | Allowed source state(s) | Target state | Guard conditions | Reversible? |
|---|---|---:|---|---|
| `write_off_loan` | `ACTIVE_NPA`, `AUCTION_COMPLETE` | `WRITTEN_OFF` | approved write-off note; loss recognized in accounting | Normally No |

---

# 4) Editability matrix

| State | Editable? | Notes |
|---|---|---|
| `DRAFT` | Yes | Full edit allowed |
| `PENDING_APPROVAL` | Limited | Usually only comments/return-to-draft |
| `APPROVED` | No | Lock commercial fields |
| `ACTIVE_*` | No | Only servicing actions/payments, not core collateral/terms editing |
| `CLOSURE_PENDING` | No | Only closure execution data |
| `RENEWAL_PENDING` | No | Only renewal workflow data |
| `AUCTION_*` | No | Only recovery process updates |
| `CLOSED`, `RENEWED`, `WRITTEN_OFF`, `REJECTED`, `CANCELLED` | No | Terminal |

---

# 5) Reversibility policy

## Reversible
- `submit_for_approval`
- `return_to_draft`
- `mark_overdue`
- `cure_to_current`
- `mark_npa` via cure
- `request_closure`
- `reopen_from_closure_pending`
- `request_renewal`
- `cancel_renewal_request`
- `initiate_auction`
- `cancel_auction`

## Restricted reversible
- `approve_loan`
- `disburse_loan`
- `complete_closure`
- `complete_renewal`

## Irreversible in normal business flow
- `reject_loan`
- `cancel_loan`
- `complete_auction`
- `close_after_auction`
- `write_off_loan`
- `write_off_after_auction`

---

# 6) Guard conditions — implementation checklist

## `approve_loan`
- borrower exists
- loan has at least one collateral item
- each collateral item passes minimum validity
- valuation or policy threshold is satisfied
- amount/tenure/rate are valid

## `disburse_loan`
- state is `APPROVED`
- no missing documents/approvals
- accounting disbursal can post
- no existing disbursal marker

## `request_closure`
- loan is active
- dues are fully settled, or authorized exception exists
- no unresolved lender custody issue

## `complete_closure`
- closure requested
- release document created
- custody items returned from lender if needed
- items delivered to customer
- closure receipt/accounting completed

## `request_renewal`
- active or NPA loan allowed by policy
- renewal amount valid
- collateral sufficient
- renewal mode selected

## `complete_renewal`
- renewal preview valid
- source/successor loan transaction succeeds atomically
- linkage + audit created

## `initiate_auction`
- loan is `ACTIVE_NPA`
- business approval for auction exists
- custody/control of collateral established

## `write_off_loan`
- approved by authorized role
- unrecoverable balance determined
- loss recognized in accounting

---

# 7) Suggested implementation structure

## Enum
Use one enum for the **primary state**:

```python
class LoanLifecycleState(models.TextChoices):
    DRAFT = "Draft"
    PENDING_APPROVAL = "PendingApproval"
    APPROVED = "Approved"
    ACTIVE_CURRENT = "ActiveCurrent"
    ACTIVE_OVERDUE = "ActiveOverdue"
    ACTIVE_NPA = "ActiveNPA"
    CLOSURE_PENDING = "ClosurePending"
    RENEWAL_PENDING = "RenewalPending"
    RENEWED = "Renewed"
    AUCTION_INITIATED = "AuctionInitiated"
    AUCTION_IN_PROGRESS = "AuctionInProgress"
    AUCTION_COMPLETE = "AuctionComplete"
    CLOSED = "Closed"
    WRITTEN_OFF = "WrittenOff"
    REJECTED = "Rejected"
    CANCELLED = "Cancelled"
```

This is the most direct “ready for implementation” form.

---

# 8) Practical recommendation

If you want the **strongest deterministic model**, I recommend:

1. Replace the old flat statuses with the matrix above.
2. Treat:
   - `Release` as a document
   - `complete_closure` as the closure transition
3. Stop using `Released` as the primary end-state.
4. Replace `Disbursed` as a long-term status with:
   - `ACTIVE_CURRENT`
   - `ACTIVE_OVERDUE`
   - `ACTIVE_NPA`

---

## Final takeaway

> A loan should have exactly **one unambiguous lifecycle state** at any point, and each transition should reflect a real business event with explicit guards and reversibility policy.

---

# 9) `django-fsm` / `viewflow.fsm` transition spec

Since the current codebase already uses `viewflow.fsm` in `apps/tenant_apps/girvi/flows.py`, the cleanest implementation is to express the new lifecycle in the same style.

## Proposed enum

```python
class LoanLifecycleState(models.TextChoices):
    DRAFT = "Draft", "Draft"
    PENDING_APPROVAL = "PendingApproval", "Pending Approval"
    APPROVED = "Approved", "Approved"

    ACTIVE_CURRENT = "ActiveCurrent", "Active Current"
    ACTIVE_OVERDUE = "ActiveOverdue", "Active Overdue"
    ACTIVE_NPA = "ActiveNPA", "Active NPA"

    CLOSURE_PENDING = "ClosurePending", "Closure Pending"
    RENEWAL_PENDING = "RenewalPending", "Renewal Pending"
    AUCTION_INITIATED = "AuctionInitiated", "Auction Initiated"
    AUCTION_IN_PROGRESS = "AuctionInProgress", "Auction In Progress"
    AUCTION_COMPLETE = "AuctionComplete", "Auction Complete"

    CLOSED = "Closed", "Closed"
    RENEWED = "Renewed", "Renewed"
    WRITTEN_OFF = "WrittenOff", "Written Off"
    REJECTED = "Rejected", "Rejected"
    CANCELLED = "Cancelled", "Cancelled"
```

## Proposed flow skeleton

```python
from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from viewflow import fsm


class GivenLoanFlowV2:
    status = fsm.State(LoanLifecycleState, default=LoanLifecycleState.DRAFT)

    def __init__(self, loan, user, tenant, ip_address=None):
        self.loan = loan
        self.user = user
        self.tenant = tenant
        self.ip_address = ip_address

    @status.setter()
    def _set_status(self, value):
        self.loan.status = value

    @status.getter()
    def _get_status(self):
        return self.loan.status

    @status.on_success()
    def _after_transition(self, descriptor, source, target, **kwargs):
        with transaction.atomic():
            self.loan.save(update_fields=["status"])
            # add LoanChangeLog / audit metadata here
```

---

# 10) Transition methods

## A. Origination and approval

```python
@status.transition(source=LoanLifecycleState.DRAFT, target=LoanLifecycleState.PENDING_APPROVAL, label=_("submit_for_approval"))
def submit_for_approval(self, submitted_by):
    self._assert_can_submit_for_approval()
    self._record_meta(submitted_by=submitted_by, submitted_at=timezone.now().isoformat())


@status.transition(source=LoanLifecycleState.PENDING_APPROVAL, target=LoanLifecycleState.DRAFT, label=_("return_to_draft"))
def return_to_draft(self, returned_by, reason=""):
    self._record_meta(returned_by=returned_by, reason=reason)


@status.transition(source=LoanLifecycleState.PENDING_APPROVAL, target=LoanLifecycleState.APPROVED, label=_("approve_loan"))
def approve_loan(self, approved_by):
    self._assert_can_approve()
    self._record_meta(approved_by=approved_by, approved_at=timezone.now().isoformat())


@status.transition(source=LoanLifecycleState.PENDING_APPROVAL, target=LoanLifecycleState.REJECTED, label=_("reject_loan"))
def reject_loan(self, rejected_by, reason):
    if not reason:
        raise ValidationError("Rejection reason is required.")
    self._record_meta(rejected_by=rejected_by, reason=reason)


@status.transition(source=[LoanLifecycleState.DRAFT, LoanLifecycleState.PENDING_APPROVAL], target=LoanLifecycleState.CANCELLED, label=_("cancel_loan"))
def cancel_loan(self, cancelled_by, reason):
    if not reason:
        raise ValidationError("Cancellation reason is required.")
    self._record_meta(cancelled_by=cancelled_by, reason=reason)
```

## B. Disbursal and servicing bucket changes

```python
@status.transition(source=LoanLifecycleState.APPROVED, target=LoanLifecycleState.ACTIVE_CURRENT, label=_("disburse_loan"))
def disburse_loan(self, disbursed_by):
    self._assert_can_disburse()
    self._record_meta(disbursed_by=disbursed_by, disbursed_at=timezone.now().isoformat())


@status.transition(source=LoanLifecycleState.ACTIVE_CURRENT, target=LoanLifecycleState.APPROVED, label=_("undo_disbursal"))
def undo_disbursal(self, undone_by, reason):
    self._assert_can_undo_disbursal()
    self._record_meta(undone_by=undone_by, reason=reason)


@status.transition(source=LoanLifecycleState.ACTIVE_CURRENT, target=LoanLifecycleState.ACTIVE_OVERDUE, label=_("mark_overdue"))
def mark_overdue(self, marked_by=None):
    self._record_meta(marked_by=marked_by, marked_at=timezone.now().isoformat())


@status.transition(source=[LoanLifecycleState.ACTIVE_OVERDUE, LoanLifecycleState.ACTIVE_NPA], target=LoanLifecycleState.ACTIVE_CURRENT, label=_("cure_to_current"))
def cure_to_current(self, cured_by, note=""):
    self._record_meta(cured_by=cured_by, note=note)


@status.transition(source=LoanLifecycleState.ACTIVE_OVERDUE, target=LoanLifecycleState.ACTIVE_NPA, label=_("mark_npa"))
def mark_npa(self, marked_by, reason):
    self._record_meta(marked_by=marked_by, reason=reason)
```

## C. Closure path

```python
@status.transition(
    source=[
        LoanLifecycleState.ACTIVE_CURRENT,
        LoanLifecycleState.ACTIVE_OVERDUE,
        LoanLifecycleState.ACTIVE_NPA,
    ],
    target=LoanLifecycleState.CLOSURE_PENDING,
    label=_("request_closure"),
)
def request_closure(self, requested_by):
    self._assert_can_request_closure()
    self._record_meta(requested_by=requested_by, requested_at=timezone.now().isoformat())


@status.transition(source=LoanLifecycleState.CLOSURE_PENDING, target=LoanLifecycleState.CLOSED, label=_("complete_closure"))
def complete_closure(self, completed_by, release_id):
    self._assert_can_complete_closure()
    self._record_meta(completed_by=completed_by, release_id=release_id)


@status.transition(source=LoanLifecycleState.CLOSURE_PENDING, target=fsm.RETURN_VALUE("previous_active_state"), label=_("reopen_from_closure_pending"))
def reopen_from_closure_pending(self, reopened_by, reason):
    self._record_meta(reopened_by=reopened_by, reason=reason)
```

## D. Renewal path

```python
@status.transition(
    source=[
        LoanLifecycleState.ACTIVE_CURRENT,
        LoanLifecycleState.ACTIVE_OVERDUE,
        LoanLifecycleState.ACTIVE_NPA,
    ],
    target=LoanLifecycleState.RENEWAL_PENDING,
    label=_("request_renewal"),
)
def request_renewal(self, requested_by):
    self._assert_can_request_renewal()
    self._record_meta(requested_by=requested_by, requested_at=timezone.now().isoformat())


@status.transition(source=LoanLifecycleState.RENEWAL_PENDING, target=LoanLifecycleState.RENEWED, label=_("complete_renewal"))
def complete_renewal(self, completed_by, successor_loan_id):
    self._assert_can_complete_renewal()
    self._record_meta(completed_by=completed_by, successor_loan_id=successor_loan_id)


@status.transition(source=LoanLifecycleState.RENEWAL_PENDING, target=fsm.RETURN_VALUE("previous_active_state"), label=_("cancel_renewal_request"))
def cancel_renewal_request(self, cancelled_by, reason=""):
    self._record_meta(cancelled_by=cancelled_by, reason=reason)
```

## E. Auction and recovery path

```python
@status.transition(source=LoanLifecycleState.ACTIVE_NPA, target=LoanLifecycleState.AUCTION_INITIATED, label=_("initiate_auction"))
def initiate_auction(self, initiated_by):
    self._assert_can_initiate_auction()
    self._record_meta(initiated_by=initiated_by, initiated_at=timezone.now().isoformat())


@status.transition(source=LoanLifecycleState.AUCTION_INITIATED, target=LoanLifecycleState.AUCTION_IN_PROGRESS, label=_("start_auction"))
def start_auction(self, started_by):
    self._record_meta(started_by=started_by, started_at=timezone.now().isoformat())


@status.transition(source=LoanLifecycleState.AUCTION_INITIATED, target=LoanLifecycleState.ACTIVE_NPA, label=_("cancel_auction"))
def cancel_auction(self, cancelled_by, reason):
    self._record_meta(cancelled_by=cancelled_by, reason=reason)


@status.transition(source=LoanLifecycleState.AUCTION_IN_PROGRESS, target=LoanLifecycleState.AUCTION_COMPLETE, label=_("complete_auction"))
def complete_auction(self, completed_by, recovery_amount):
    self._record_meta(completed_by=completed_by, recovery_amount=str(recovery_amount))


@status.transition(source=LoanLifecycleState.AUCTION_COMPLETE, target=LoanLifecycleState.CLOSED, label=_("close_after_auction"))
def close_after_auction(self, completed_by):
    self._assert_recovery_clears_balance()
    self._record_meta(completed_by=completed_by)


@status.transition(source=[LoanLifecycleState.ACTIVE_NPA, LoanLifecycleState.AUCTION_COMPLETE], target=LoanLifecycleState.WRITTEN_OFF, label=_("write_off_loan"))
def write_off_loan(self, written_off_by, reason):
    self._assert_can_write_off()
    self._record_meta(written_off_by=written_off_by, reason=reason)
```

---

# 11) Guard methods that should exist in the service layer

These checks should stay deterministic and reusable in preview + execute paths:

```python
def _assert_can_submit_for_approval(self):
    if not self.loan.customer_id:
        raise ValidationError("Borrower is required.")
    if not self.loan.items.exists():
        raise ValidationError("At least one collateral item is required.")
    if self.loan.get_loan_amount <= 0:
        raise ValidationError("Loan amount must be greater than zero.")


def _assert_can_approve(self):
    self._assert_can_submit_for_approval()
    if not self.loan.series_id:
        raise ValidationError("Series is required before approval.")


def _assert_can_disburse(self):
    if self.loan.status != LoanLifecycleState.APPROVED:
        raise ValidationError("Only approved loans can be disbursed.")


def _assert_can_request_closure(self):
    if self.loan.outstanding_amount > 0 and not getattr(self.loan, "closure_exception_approved", False):
        raise ValidationError("Loan must be fully settled before closure request.")


def _assert_can_complete_closure(self):
    if not getattr(self.loan, "release", None):
        raise ValidationError("Release document must exist before closure completes.")


def _assert_can_request_renewal(self):
    if not self.loan.items.exists():
        raise ValidationError("Renewal requires valid collateral.")


def _assert_can_complete_renewal(self):
    if getattr(self.loan, "renewal", None) is None:
        raise ValidationError("Renewal record must exist before completion.")


def _assert_can_initiate_auction(self):
    if self.loan.status != LoanLifecycleState.ACTIVE_NPA:
        raise ValidationError("Only NPA loans can be sent to auction.")


def _assert_can_write_off(self):
    if self.loan.status not in {LoanLifecycleState.ACTIVE_NPA, LoanLifecycleState.AUCTION_COMPLETE}:
        raise ValidationError("Only NPA or auction-complete loans can be written off.")
```

---

# 12) Mapping from current legacy transitions to the new FSM

| Current key in `flows.py` | Proposed new transition | Why |
|---|---|---|
| `approve` | `submit_for_approval` + `approve_loan` | separates maker/checker submission from final approval |
| `disburse` | `disburse_loan` | same business meaning, better target state |
| `deliver` | `request_closure` + `complete_closure` | distinguishes financial eligibility from actual release/delivery |
| `mark_defaulted` | `mark_overdue` / `mark_npa` | separates overdue servicing from true NPA/default |
| `repledge` | `request_renewal` + `complete_renewal` | reflects renewal workflow instead of a flat terminal status |
| `mark_auctioned` | `initiate_auction` + `start_auction` + `complete_auction` | turns auction into a real process, not one jump |
| `mark_sold` | keep as recovery-side accounting event or fold into auction completion | should not stay the primary lifecycle for standard given loans |
| `undo_release` | `reopen_from_closure_pending` or restricted `undo_closure` | keeps reversal semantics explicit |

---

# 13) Recommended implementation sequence

1. Add the new `LoanLifecycleState` enum beside the existing `LoanStatus`.
2. Introduce `GivenLoanFlowV2` without removing the old `LoanFlow` yet.
3. Route **preview/execute** services to the new guards first.
4. Migrate UI actions in `transition_registry.py` to the new transition keys.
5. Add a compatibility map from old statuses to new states for existing records.
6. Remove the old flat-state flow only after tests and data migration are stable.

---

## Final implementation note

For this codebase, the best practical reading is:

- **`viewflow.fsm`** remains the FSM engine,
- **service-layer previews** enforce business guards before commit,
- **documents** like `Release` and `LoanRenewal` stay as business artifacts,
- and the **loan status** becomes a true lifecycle state instead of a mixed bucket of events and outcomes.

This is now ready to be implemented in `flows.py` and `transition_registry.py` in a controlled migration.