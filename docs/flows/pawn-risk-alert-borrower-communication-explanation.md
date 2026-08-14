The borrower communication workflow is a controlled bridge between an internal risk warning and an external customer message.

The essential rule is:

> A risk alert suggests that communication may be needed. A staff-approved borrower notice authorizes what will actually be sent.

## Overall flow

```text
Scheduled risk reassessment
          │
          ▼
Current LoanRiskSnapshot
          │
          │ detects a material change
          ▼
Immutable LoanRiskEvent
          │
          ▼
Open LoanRiskAlert
          │
          │ staff reviews the situation
          ▼
Communication eligibility check
          │
     ┌────┴─────┐
     │          │
  Blocked     Eligible
     │          │
     ▼          ▼
Show reason   Preview exact message
                │
                ▼
          Staff confirmation
                │
                ▼
       Immutable PawnLoanNotice
                │
                ▼
       Notify v2 event and job
                │
          ┌─────┴─────┐
          │           │
       Delivered     Failed
          │           │
          ▼           ▼
      Evidence     Review/retry
```

## 1. Risk reassessment discovers a change

Assume loan `PL-00020` was 18 days overdue yesterday and is 31 days overdue today.

The scheduled reassessment recalculates:

- Recorded exposure.
- Contractual obligations.
- Days past due.
- Collateral value and LTV.
- Maturity proximity.
- Monitoring severity.

It refreshes the persisted snapshot:

```text
Loan: PL-00020
DPD: 31
DPD bucket: DPD_30_59
Severity: HIGH
Status: CURRENT
```

Because the loan crossed from `DPD_1_29` into `DPD_30_59`, the system records an immutable event:

```text
LoanRiskEvent
Event type: DPD_BUCKET_CHANGED
Old value: DPD_1_29
New value: DPD_30_59
Assessment date: 2026-08-14
```

This event answers: **what changed and when?**

## 2. An internal alert is opened

The event creates a `LoanRiskAlert`:

```text
Alert: Worsening delinquency
Loan: PL-00020
Severity: HIGH
Status: OPEN
Recommended action:
Review overdue obligations and begin approved collection follow-up.
```

The alert appears in the Risk Portfolio.

It is internal staff work. Nothing has been sent to the borrower.

That distinction matters because staff may discover:

- A repayment was received but not allocated.
- A schedule is incorrect.
- The customer already made a payment today.
- The borrower has disputed the amount.
- The loan is under an exceptional recovery arrangement.

## 3. Staff opens the alert

For eligible alerts, staff sees a **Create borrower notice** action.

Initially eligible:

| Risk alert | Proposed borrower notice |
|---|---|
| Worsening DPD | Overdue notice |
| Approaching maturity | Repayment reminder |
| Past maturity | Overdue or maturity notice |
| Confirmed LTV breach | Collateral coverage notice |

Not eligible:

| Internal alert | Why communication is blocked |
|---|---|
| Assessment failure | Internal calculation/setup failure |
| Missing valuation rate | Borrower did not cause the setup problem |
| Missing appraisal | Internal evidence problem |
| Accounting variance | Requires internal reconciliation |
| Missing monitoring policy | Configuration problem |

## 4. Eligibility is rechecked

The system must not trust the alert merely because it was valid when created. It rechecks the current state when staff begins communication.

For example:

```text
✓ Alert remains OPEN
✓ Loan remains ACTIVE
✓ Latest snapshot remains CURRENT
✓ Loan is still overdue
✓ Risk event belongs to this loan and workspace
✓ Borrower has an active Party record
```

If the borrower paid after the morning reassessment, the communication action should fail closed:

```text
This alert no longer supports an overdue notice.
Refresh the risk assessment before communicating.
```

No notice or delivery job is created.

## 5. Available channels are calculated

The system should show only usable channels.

Example:

```text
Borrower: Raj Kumar
Email: raj@example.com
Phone: +919876543210
Preferred locale: hi
```

Channel assessment:

| Channel | Contact | Consent | Provider | Result |
|---|---:|---:|---:|---|
| Email | Available | Allowed | Configured | Available |
| SMS | Available | Allowed | Configured | Available |
| WhatsApp | Available | Missing consent | Configured | Blocked |

The staff member cannot override missing consent merely by selecting the channel.

A channel can be blocked because:

- Contact information is missing or invalid.
- The borrower opted out.
- Required consent is absent.
- The workspace provider is not configured.
- An approved template is unavailable.
- The provider integration is unhealthy.
- The channel is not permitted for that notice category.

## 6. Staff selects the communication

The form should show:

- Notice category.
- Channel.
- Language.
- Recipient snapshot.
- Schedule.
- Source alert.
- Current financial basis.

Example:

```text
Notice: Overdue notice
Channel: SMS
Language: Hindi
Recipient: +919876543210
Send: Immediately
Risk event: DPD bucket changed to DPD_30_59
Financial as of: 2026-08-14
```

The system chooses an approved template based on:

```text
Notice category + channel + locale + workspace
```

For example:

```text
Template: Pawn loan overdue SMS
Version: 3
Locale: hi
Status: ACTIVE
```

Staff should not type an arbitrary free-form collection message in v1.

## 7. Exact content is previewed

Before confirmation, staff sees the exact message that will become immutable evidence.

Example preview:

> Dear Raj Kumar, pawn loan PL-00020 is overdue by 31 days. Total amount due as of 14 August 2026 is INR 24,850. Please contact JCL Finance at 011-XXXXXXX.

The preview must display its financial components:

```text
Principal outstanding: INR 20,000
Interest outstanding: INR 4,500
Fees outstanding: INR 350
Total due: INR 24,850
Assessment date: 2026-08-14
```

It must also display:

- Recipient address.
- Channel.
- Template and version.
- Scheduled time.
- Source risk event.
- Consent decision.
- Provider readiness.

The operator confirms something explicit, such as:

> I confirm the borrower, channel, amounts, template, and schedule shown above.

## 8. PawnLoanNotice is created

After confirmation, Loans creates an immutable communication intent.

Conceptually:

```text
PawnLoanNotice
Loan: PL-00020
Source alert: Alert #44
Source risk event: Event #102
Notice kind: OVERDUE_NOTICE
Channel: SMS
Template: overdue-sms v3
Recipient: +919876543210
Financial as of: 2026-08-14
Scheduled for: 2026-08-14 11:30
Created by: Owner
Payload: exact frozen amounts and customer details
```

The idempotency identity should derive from:

```text
risk event + notice kind + channel + template version
```

Therefore, double-clicking Submit cannot create two notices.

A separate notice may still be valid when:

- A later risk event occurs.
- A different approved channel is intentionally used.
- A new notice stage is reached.
- An authorized retry occurs through the same notice/job.

## 9. Notify v2 creates the delivery job

Loans owns why the notice exists. Notify v2 owns how it is delivered.

```text
PawnLoanNotice
      │
      ▼
NotificationRecipient
      │
      ▼
NotificationEvent
      │
      ▼
NotificationJob
      │
      ├── Template version
      ├── Scheduled time
      ├── Channel
      ├── Status
      └── Provider evidence
```

The communication payload is already frozen. Notify v2 should render from that frozen payload rather than recalculating the loan.

## 10. Delivery behavior

### Email

Notify v2:

1. Renders the subject and body.
2. Stores the rendered artifact.
3. Sends through the configured email backend.
4. Records the attempt and provider reference.
5. Marks the job sent or failed.

A normal SMTP handoff proves that the application submitted the email. It does not necessarily prove that the borrower received or read it. Bounce/delivery webhooks would be a later improvement.

### SMS

Notify v2:

1. Renders the approved SMS template.
2. Checks message length and provider readiness.
3. Submits it to the configured SMS provider.
4. Stores the provider message ID.
5. Records provider delivery updates where supported.

Missing real credentials must cause `FAILED`. It must never silently use a stub and claim that the customer was contacted.

### WhatsApp

Notify v2:

1. Resolves an approved provider template.
2. Renders permitted template parameters.
3. Submits WhatsApp through Meta WhatsApp Cloud API. SMS remains unavailable
   until a separate provider is selected.
4. Records the provider message ID.
5. Accepts authenticated status callbacks.
6. Records sent, delivered, read, or failed evidence.

Production WhatsApp requires:

- Workspace-owned or explicitly approved sender identity.
- Approved WhatsApp template.
- Valid consent/opt-in.
- Signature-verified callbacks.
- Tenant-safe callback routing.
- Replay and duplicate protection.

## 11. Delivery results appear in Loans

The notice ledger should present delivery state without copying Notify v2’s provider records.

Example:

```text
Overdue notice
Channel: SMS
Created: 14 Aug 2026, 11:30
Status: SENT
Attempts: 1
Provider reference: SM123456
Source alert: Worsening DPD
```

Failure example:

```text
Status: FAILED
Reason: Recipient phone is invalid
Attempts: 1
Action: Correct Party contact and review retry
```

Retry must use the same notice and job. It should not create another borrower intent merely because delivery failed.

## 12. Sending does not resolve risk

This is a crucial distinction:

```text
Message sent ≠ Loan cured
Message delivered ≠ Loan cured
Borrower replied ≠ Loan cured
Payment posted and reassessed = Loan may be cured
```

The internal alert remains open after communication.

When payment is recorded and the next reassessment shows the loan is current:

```text
LoanRiskEvent: DELINQUENCY_CURED
LoanRiskAlert: RESOLVED
```

The communication history remains permanently linked as evidence of what staff did while the alert was open.

## Configurable workflows later

Once manual communication is proven, a workspace could configure:

```text
Alert category: DPD_30_59
Default notice: OVERDUE_NOTICE
Default channel: WHATSAPP
Fallback channel: SMS
Locale: Borrower preference
Approval: Required
Quiet hours: 20:00–08:00
Cooldown: 7 days
Escalation: DPD_60_89
```

A future workflow might operate like this:

```text
DPD crosses 30 days
        │
        ▼
Create internal alert
        │
        ▼
Prepare WhatsApp notice
        │
        ▼
Owner approves
        │
        ▼
Send after quiet hours
        │
   ┌────┴─────┐
   │          │
Delivered   Failed
   │          │
   │          ▼
   │      Offer SMS fallback
   │
   ▼
No repeat for 7 days
        │
        ▼
If DPD reaches 60:
create a new escalation alert and notice
```

Full automation should come later and remain opt-in:

```text
Material event
    → revalidate current loan state
    → verify consent
    → verify contact
    → verify template
    → verify provider
    → enforce quiet hours/cooldown
    → create idempotent notice
    → dispatch
```

If any check fails, the system should create or retain internal staff work rather than send an uncertain message.

The documented design is available at [pawn-risk-alert-borrower-communication.md](C:/Users/rajes/OneDrive/Desktop/rokkad/docs/flows/pawn-risk-alert-borrower-communication.md).
