---
status: active
owner: loans
updated: 2026-08-14
tags: [loans, risk, alerts, notices, notify-v2, email, sms, whatsapp]
related:
  - ../adr/2026-08-13-loan-application-boundaries-and-monitoring.md
  - ../adr/2026-08-09-loans-operational-notice-intents.md
  - ../implementation/pawn-loan-e7.1-notices.md
  - ../implementation/whatsapp-notifications-architecture-audit.md
---

# PawnLoan Risk Alert to Borrower Communication

## Decision status

The manual, staff-approved email and WhatsApp workflow is implemented. Workspace
policy now supplies a preferred initial channel, quiet hours, a repeat-notice
cooldown, and an internal escalation threshold. Configurable automatic
multi-channel workflows remain a later phase and are not approved here.

## Purpose and boundaries

`LoanRiskEvent` is immutable evidence of a material risk change.
`LoanRiskAlert` is internal open/resolved staff work. `PawnLoanNotice` is the
immutable borrower-communication intent. Notify v2 owns rendering, delivery
jobs, attempts, artifacts, and provider references.

An alert must never send a borrower message by itself:

```text
RiskSnapshot refresh
  -> LoanRiskEvent
  -> LoanRiskAlert (internal work)
  -> staff reviews eligibility and exact content
  -> PawnLoanNotice (borrower intent)
  -> Notify v2 event/job
  -> provider delivery evidence
```

Sending a notice does not resolve the risk alert. Risk recovery resolves the
alert; communication is evidence of an attempted contact, not evidence that the
loan risk was cured.

## Detailed end-to-end illustration

The workflow is a controlled bridge between an internal risk warning and an
external customer message. A risk alert suggests that communication may be
needed; a confirmed borrower notice authorizes what will actually be sent.

```text
Scheduled risk reassessment
          |
          v
Current LoanRiskSnapshot
          |
          | material change detected
          v
Immutable LoanRiskEvent
          |
          v
Open LoanRiskAlert
          |
          | staff reviews the situation
          v
Communication eligibility check
          |
     +----+-----+
     |          |
  Blocked     Eligible
     |          |
     v          v
Show reason   Preview exact message
                |
                v
          Staff confirmation
                |
                v
       Immutable PawnLoanNotice
                |
                v
       Notify v2 event and job
                |
          +-----+-----+
          |           |
       Delivered     Failed
          |           |
          v           v
      Evidence     Review/retry
```

### Example: delinquency worsens

Assume `PL-00020` was 18 days overdue yesterday and is 31 days overdue today.
Daily reassessment refreshes recorded exposure, contractual obligations, DPD,
collateral value/LTV, maturity proximity, and severity. The persisted result may
be:

```text
Loan: PL-00020
DPD: 31
DPD bucket: DPD_30_59
Severity: HIGH
Snapshot status: CURRENT
```

Crossing from `DPD_1_29` to `DPD_30_59` creates immutable evidence:

```text
LoanRiskEvent
Type: DPD_BUCKET_CHANGED
Old: DPD_1_29
New: DPD_30_59
Assessment date: 2026-08-14
```

That event opens one internal `DPD_WORSENING` alert for the loan. It does not
contact the borrower. Staff first checks for a recently received/unallocated
payment, schedule error, dispute, or approved exceptional arrangement.

### Revalidation when staff acts

The server must not rely only on the historical alert. Before showing or
confirming communication it rechecks:

- the alert remains Open and belongs to the active workspace;
- the PawnLoan remains Active;
- the latest snapshot is Current and still supports the notice category;
- the risk event belongs to the same loan;
- the borrower remains an active Party with an eligible contact.

If the borrower paid after the alert was created, confirmation fails closed and
no notice/job is written. Staff refreshes the risk assessment instead.

### Channel availability

Only usable channels are shown. For example:

| Channel | Contact | Consent | Provider | Result |
| --- | --- | --- | --- | --- |
| Email | Available | Allowed | Configured | Available |
| SMS | Available | Allowed | Configured | Available |
| WhatsApp | Available | Missing | Configured | Blocked |

A channel is blocked for missing/invalid contact, opt-out, missing category
consent, unavailable provider, unavailable approved template, unhealthy
integration, or a notice category that is not permitted on that channel. Staff
cannot bypass these checks through the form.

### Exact preview and confirmation

The form shows notice category, channel, language, recipient snapshot, schedule,
source alert/event, financial as-of date, and resolved template/version. For
example:

```text
Notice: Overdue notice
Channel: SMS
Locale: hi
Recipient: +919876543210
Template: Pawn loan overdue SMS v3
Send: Immediately
Risk event: DPD bucket changed to DPD_30_59
Financial as of: 2026-08-14
```

The exact rendered content is previewed before confirmation, together with
principal, interest, fees, total due, template identity, consent decision, and
provider readiness. V1 does not permit arbitrary collection free text.

The operator confirms the borrower, channel, amounts, template, and schedule.
Loans then creates an immutable `PawnLoanNotice` containing frozen recipient and
financial payloads and explicit source alert/risk-event/template identities.
The idempotency identity is derived from risk event, notice kind, channel, and
template version, so a double submission cannot create two intents.

### Notify v2 delivery

Loans owns why the notice exists. Notify v2 owns rendering and delivery:

```text
PawnLoanNotice
      |
      v
NotificationRecipient
      |
      v
NotificationEvent
      |
      v
NotificationJob
      |
      +-- template version
      +-- scheduled time
      +-- channel
      +-- status
      +-- artifacts and attempt logs
      +-- provider reference
```

Notify renders only from the frozen payload; it does not recalculate the loan.
Email records submission through the configured backend. SMS records the real
provider message ID. WhatsApp uses an approved provider template and records
authenticated status callbacks. Missing real credentials must fail the job; a
stub must never count as borrower contact outside development/tests.

Loans reads the linked job state for its notice ledger. A failed delivery is
retried through the same notice/job rather than creating a second intent.

### Communication is not risk resolution

The alert stays open after a message is sent, delivered, or read:

```text
Message sent       != loan cured
Message delivered  != loan cured
Borrower replied   != loan cured
Payment posted and reassessed may cure the loan
```

When payment evidence and reassessment produce `DELINQUENCY_CURED`, the risk
alert resolves. The risk event, notice, rendered artifact, attempts, and provider
evidence remain linked as permanent history.

### Workspace manual policy

An Owner/Admin may configure:

```text
Alert category: DPD_30_59
Default notice: OVERDUE_NOTICE
Default channel: WHATSAPP
Quiet hours: 20:00-08:00
Cooldown: 7 days
Escalation guidance: 60 DPD
```

The preferred channel chooses the initial manual preview but never falls back or
sends automatically. Quiet hours and cooldown block both preview and final
confirmation. Reaching the escalation threshold only tells the operator to
follow the workspace's internal procedure. The exact policy is fingerprinted
with the preview and frozen as notice evidence.

## Eligible and ineligible alerts

The first slice may offer **Create borrower notice** for:

- worsening DPD, mapped to an overdue notice;
- approaching/past maturity, mapped initially to a repayment reminder;
- confirmed LTV breach only after the operator reviews current appraisal and
  valuation-rate provenance.

Assessment failure, missing setup, valuation calculation failure, accounting
variance, and other internal diagnostics are never borrower-message triggers.

## Manual approved workflow (first implementation)

1. Staff opens an eligible alert from the Risk Portfolio.
2. The server rechecks that the alert is open, its PawnLoan is active, and the
   current snapshot still supports the communication category.
3. Staff selects one available channel and reviews the Party contact snapshot.
4. The system enforces channel consent/opt-out and provider readiness.
5. Staff previews the exact subject/body, template identity/version, financial
   as-of date, and schedule.
6. Staff confirms the immutable notice. Loans creates one `PawnLoanNotice`
   linked to the alert/risk event and uses an event-derived idempotency key.
7. Notify v2 creates the event/job and dispatches now or at the approved time.
8. The Loan notice ledger shows queued, sent, failed, and provider evidence.
9. A failed delivery may be retried through the existing controlled retry path.

### Operational and audit surface

The Risk Portfolio labels eligible DPD and maturity alerts as either **Email
ready** or **Email blocked** and shows the concrete blocker. The Operations
Console reports whether the configured email backend and sender are acceptable
for real borrower delivery; console, dummy, in-memory, and file backends remain
blocked. The customer notice ledger joins the immutable Loans intent to its
source risk alert/event, selected template/version, consent decision snapshot,
rendered Notify artifact, attempts, failure, and provider reference. This is one
connected audit trail, not duplicated delivery state in Loans.

The same manual action now supports WhatsApp when—and only when—the Party has
explicit WhatsApp consent, a phone number, all Cloud and callback settings are
present, and the active Notify template carries an approved Meta template name.
Email and WhatsApp have separate event/template/channel dedupe identities. The
operator chooses one channel, previews its exact rendered content and (for
WhatsApp) the structured Cloud template name/language/components, then confirms
the fingerprint. No fallback to the other channel occurs.

Owner/Admin can review **WhatsApp risk pilot acceptance** from the Loans
Operations Console. It joins each manual risk notice to its Notify job and
ordered authenticated Meta receipts, showing submission/provider identity,
latest `sent/delivered/read/failed` state, callback timing, duplicate replay
count, unknown callbacks, and unresolved delivery. Acceptance requires real
provider readiness, at least one pilot notice, no unknown receipts, and every
pilot notice reaching authenticated `delivered` or `read` evidence.

```powershell
python manage.py tenant_command check_pawn_risk_whatsapp_pilot --schema=TENANT_SCHEMA --fail-on-blocker --format=json
```

The manual workflow does not allow arbitrary free-text messages, automatic
sending, multi-step escalation, channel fallback, or bulk alert conversion.

Confirmation carries a deterministic fingerprint of the alert/event, recipient,
template version, frozen financial payload, and rendered subject/body. The POST
recalculates it under the alert lock and rejects a changed preview. Notify then
renders from that same frozen payload. The risk-email pilot reconciliation gate
compares each sent artifact with the confirmed preview and fails closed on
missing consent/preview/artifact evidence.

## Notify v2 capability assessment

### Ready foundations

- Tenant-schema isolation is already used by Notify v2.
- Email, SMS, and WhatsApp channel vocabulary exists.
- Versioned templates, event types, policies, recipients, jobs, rendered
  artifacts, provider IDs, failures, and attempt logs exist.
- Email uses Django mail. WhatsApp uses Meta WhatsApp Cloud API submission and
  status callbacks exclusively. SMS has no selected provider and fails closed.
- Loans already owns immutable `PawnLoanNotice` intent and adapts it into Notify
  v2 jobs. Scheduled selection, retry, and delivery-state reads already exist.
- Party-backed recipient snapshots and exact financial payload snapshots exist.

### Blocking gaps before borrower risk messaging

1. **Consent is not enforced.** `NotificationRecipient.consent_flags` is generic
   JSON and current dispatch does not check it. There is no typed channel/category
   consent or opt-out decision at the Loans notice boundary.
2. **No simulated borrower delivery.** WhatsApp Cloud API configuration is
   mandatory and provider errors fail the job. SMS remains unavailable until a
   separate provider decision is accepted; neither channel can become Sent via
   a development stub.
3. **Policy is descriptive, not authoritative.** Cooldown and schedule rules are
   stored but are not enforced by the ordinary Loans notice dispatch path.
4. **Event dedupe is not database-enforced.** `NotificationEvent.dedupe_key` is
   indexed but not unique. Loans request keys prevent ordinary duplicate notice
   intent, but risk-event/template/channel identity still needs an explicit
   constraint at the Loans boundary.
5. **Template selection is not a controlled approval boundary.** The Loans
   adapter creates default v1 templates and jobs; it does not yet require an
   operator-approved active template identity or preserve that chosen identity
   on `PawnLoanNotice`.
6. **WhatsApp callback security and routing are incomplete.** Cloud webhook
   challenge verification exists, but provider signature verification, raw
   webhook dedupe/replay evidence, and robust tenant routing are not complete.
7. **Execution is synchronous.** Immediate dispatch runs after request commit;
   scheduled dispatch is a management command, not a durable worker queue.
   This is acceptable for a small controlled pilot, not high-volume automation.
8. **Email provider evidence is limited.** Django `send_mail` records handoff as
   sent but supplies no delivery/bounce webhook evidence in the current path.

## Required readiness gate

Before implementing the alert action, complete these KISS prerequisites:

- Add a server-side channel eligibility function that checks Party contact,
  typed service-notice consent/opt-out, and configured provider readiness.
- Disable digital stub-as-sent behavior outside tests/development; missing real
  credentials must produce `FAILED`.
- Link `PawnLoanNotice` explicitly to its source `LoanRiskAlert`/`LoanRiskEvent`
  and enforce one event/template/channel intent through a database constraint.
- Resolve and preview an explicit active template/version before confirmation;
  snapshot its identity and rendered content as evidence.
- Restrict v1 to manual staff approval. Use email first where the configured
  backend is real; enable SMS/WhatsApp per workspace only after provider and
  consent readiness passes.

WhatsApp production enablement additionally requires signature-verified,
replay-safe, tenant-routable callbacks and a real approved provider template.

Those technical callback controls are now implemented in Notify v2. Each POST
must have a valid Meta HMAC, match the configured phone-number ID, arrive on a
tenant route, and creates one deduplicated receipt before updating a uniquely
identified WhatsApp job. WhatsApp dispatch is template-only. Operational
enablement remains blocked until real Cloud credentials/templates and the
`check_whatsapp_cloud_readiness` reconciliation exercise pass for the workspace.

## Later configurable workflow

After the manual workflow has operator acceptance and delivery reconciliation,
workspace configuration may define eligible alert category, default channel,
locale/template, approval requirement, quiet hours, cooldown, and escalation.
Automatic sending remains opt-in per category and must revalidate loan state,
consent, contact, template, provider, dedupe, and alert currency immediately
before creating the notice.

## Acceptance evidence

- Ineligible/internal alerts never expose borrower communication.
- Stale or resolved alerts fail closed at confirmation.
- Missing consent/contact/provider/template produces an actionable blocker and
  no notice/job.
- Repeated submission creates one linked notice and one job per channel.
- Preview content and delivered artifact are identical and retain template
  version, risk event, financial as-of date, actor, and recipient snapshots.
- Provider failure is visible and retryable without creating another intent.
- Sending does not resolve risk; a recovery transition does.
- Cross-workspace alert, Party, template, notice, and job identifiers fail closed.

## Recommended implementation order

1. Notify v2/Loans readiness gate: consent decision, fail-closed provider check,
   explicit template resolution, source linkage, and dedupe.
2. Manual approved notice from DPD and maturity alerts, email-first.
3. SMS/WhatsApp controlled pilot with real credentials and reconciliation.
4. Workspace defaults and quiet-hour/cooldown enforcement. **Complete.**
5. Optional approved-category automation only after measured operator acceptance.
