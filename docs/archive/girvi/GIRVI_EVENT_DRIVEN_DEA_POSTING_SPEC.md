---
status: archived
owner: project
updated: 2026-06-17
tags: [archive]
related: []
---

# Girvi Event-Driven DEA Posting Spec

Date: 2026-05-03
Related plan: [TOP10_RISKY_EDGES_PHASED_REFACTOR_PLAN.md](TOP10_RISKY_EDGES_PHASED_REFACTOR_PLAN.md)
Related policy: [DEPENDENCY_POLICY_MATRIX.md](DEPENDENCY_POLICY_MATRIX.md)

## 1) Concrete Before and After Design

## 1.1 Before (Current Runtime Pattern)

Current state in code:
- GivenLoan and TakenLoan inherit from BusinessDoc in apps/tenant_apps/girvi/models/loan_refactored.py.
- Girvi payment and release services call DEA posting synchronously in apps/tenant_apps/girvi/service_modules/payment.py.
- PaymentVoucher remains a DEA model that is created directly from Girvi lifecycle methods.

Current coupling shape:
1. Girvi domain model knows DEA base type (BusinessDoc).
2. Girvi service creates PaymentVoucher and immediately calls DEA posting engine.
3. Request path can include business mutation plus accounting posting in one synchronous flow.

Simplified class map (before):
- girvi.BaseLoan -> dea.BusinessDoc
- girvi.GivenLoan -> girvi.BaseLoan
- girvi.TakenLoan -> girvi.BaseLoan
- girvi Release/Payment services -> dea.PaymentVoucher
- girvi Release/Payment services -> dea posting engine/service

Flow (before):
1. User action changes loan state (approve/disburse/payment/release).
2. Girvi service writes domain state.
3. Same flow creates PaymentVoucher.
4. Same flow posts voucher to ledger.
5. If posting fails, request may fail or require partial-state handling.

## 1.2 After (Target Event-Driven Pattern)

Target state:
- Girvi domain models stop depending on DEA posting internals.
- Girvi writes domain state and outbox event atomically.
- DEA consumer reads event, creates/updates PaymentVoucher and postings asynchronously.
- Idempotency key and event_id guarantee safe retries.

Target coupling shape:
1. Girvi -> Outbox publisher (same DB transaction as domain write).
2. DEA consumer -> event contracts -> posting rules.
3. DEA models do not import Girvi models for posting decisions.

Simplified class map (after):
- girvi.BaseLoan (pure domain, no DEA posting inheritance requirement)
- girvi.GivenLoan
- girvi.TakenLoan
- platform.EventOutbox (new platform/shared app)
- dea.DeaEventConsumer (new)
- dea.PostingRuleResolver (existing/new adapter)
- dea.PaymentVoucher (created by consumer, not by Girvi request path)

Flow (after):
1. User action changes loan state.
2. Girvi application service writes domain state and outbox event in one transaction.
3. API/UI returns success with posting_status = Pending.
4. DEA consumer processes event and posts voucher/journal.
5. DEA emits posting.completed or posting.failed for observability and notify_v2.

## 1.3 What "Replace BusinessDoc Inheritance Coupling" Means in Practice

It means removing accounting behavior dependency from Girvi domain inheritance and request path.

Practical implementation intent:
1. Stop relying on BaseLoan -> BusinessDoc for posting side effects and implicit accounting semantics.
2. Keep Girvi loan models focused on lifecycle and domain invariants only.
3. Move accounting integration to event emission and DEA async consumer.
4. Optionally retain a temporary compatibility mixin/adapter while migrating, but no new feature should use direct synchronous posting.

Important note:
- This does not require deleting PaymentVoucher.
- It changes who creates/posts it: DEA consumer instead of Girvi synchronous request path.

## 2) Exact Event Schemas

Schema version: 1
Encoding: JSON
Envelope is common for all events.

## 2.1 Common Envelope (all events)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "rokkad.events.envelope.v1",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "event_id": {"type": "string", "format": "uuid"},
    "event_type": {"type": "string"},
    "schema_version": {"type": "integer", "const": 1},
    "tenant_schema": {"type": "string", "minLength": 1},
    "occurred_at": {"type": "string", "format": "date-time"},
    "producer_app": {"type": "string", "const": "girvi"},
    "aggregate_type": {"type": "string", "enum": ["GivenLoan", "TakenLoan"]},
    "aggregate_id": {"type": "integer", "minimum": 1},
    "idempotency_key": {"type": "string", "minLength": 1},
    "trace_id": {"type": ["string", "null"]},
    "actor_user_id": {"type": ["integer", "null"], "minimum": 1},
    "payload": {"type": "object"}
  },
  "required": [
    "event_id",
    "event_type",
    "schema_version",
    "tenant_schema",
    "occurred_at",
    "producer_app",
    "aggregate_type",
    "aggregate_id",
    "idempotency_key",
    "payload"
  ]
}
```

## 2.2 Event: loan.disbursed

Business meaning:
- Cash disbursal event for a loan becoming Disbursed.
- GivenLoan is cash out; TakenLoan is cash in.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "rokkad.events.loan.disbursed.v1",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "loan_id": {"type": "string", "minLength": 1},
    "loan_pk": {"type": "integer", "minimum": 1},
    "loan_kind": {"type": "string", "enum": ["GivenLoan", "TakenLoan"]},
    "series_id": {"type": "integer", "minimum": 1},
    "customer_id": {"type": "integer", "minimum": 1},
    "loan_date": {"type": "string", "format": "date-time"},
    "disbursed_at": {"type": "string", "format": "date-time"},
    "currency": {"type": "string", "const": "INR"},
    "principal_amount": {"type": "string", "pattern": "^-?\\d+(\\.\\d{1,2})?$"},
    "interest_rate_snapshot": {"type": ["string", "null"]},
    "payment_method": {"type": "string", "enum": ["CASH", "BANK", "CHEQUE", "UPI", "CARD", "OTHER"]},
    "reference_number": {"type": "string"},
    "dea_direction": {"type": "string", "enum": ["PAYMENT", "RECEIPT"]},
    "voucher_rule_key": {"type": "string", "enum": ["GIVENLOAN_PAYMENT", "TAKENLOAN_RECEIPT"]}
  },
  "required": [
    "loan_id",
    "loan_pk",
    "loan_kind",
    "series_id",
    "customer_id",
    "loan_date",
    "disbursed_at",
    "currency",
    "principal_amount",
    "payment_method",
    "reference_number",
    "dea_direction",
    "voucher_rule_key"
  ]
}
```

Recommended idempotency_key format:
- loan.disbursed:{tenant_schema}:{loan_kind}:{loan_pk}:v1

## 2.3 Event: loan.payment.received

Business meaning:
- A repayment/receipt event against a loan.
- Supports both partial and final payments.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "rokkad.events.loan.payment.received.v1",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "loan_id": {"type": "string", "minLength": 1},
    "loan_pk": {"type": "integer", "minimum": 1},
    "loan_kind": {"type": "string", "enum": ["GivenLoan", "TakenLoan"]},
    "payment_id": {"type": "string", "minLength": 1},
    "payment_date": {"type": "string", "format": "date-time"},
    "currency": {"type": "string", "const": "INR"},
    "total_amount": {"type": "string", "pattern": "^-?\\d+(\\.\\d{1,2})?$"},
    "principal_amount": {"type": ["string", "null"], "pattern": "^-?\\d+(\\.\\d{1,2})?$"},
    "interest_amount": {"type": ["string", "null"], "pattern": "^-?\\d+(\\.\\d{1,2})?$"},
    "fee_amount": {"type": ["string", "null"], "pattern": "^-?\\d+(\\.\\d{1,2})?$"},
    "is_final_payment": {"type": "boolean"},
    "payment_method": {"type": "string", "enum": ["CASH", "BANK", "CHEQUE", "UPI", "CARD", "OTHER"]},
    "reference_number": {"type": "string"},
    "dea_direction": {"type": "string", "enum": ["RECEIPT", "PAYMENT"]},
    "voucher_rule_key": {
      "type": "string",
      "enum": ["GIVENLOAN_RECEIPT", "TAKENLOAN_PAYMENT", "GIVENLOAN_PAYMENT", "TAKENLOAN_RECEIPT"]
    }
  },
  "required": [
    "loan_id",
    "loan_pk",
    "loan_kind",
    "payment_id",
    "payment_date",
    "currency",
    "total_amount",
    "is_final_payment",
    "payment_method",
    "reference_number",
    "dea_direction",
    "voucher_rule_key"
  ]
}
```

Recommended idempotency_key format:
- loan.payment.received:{tenant_schema}:{payment_id}:v1

## 2.4 Event: loan.released

Business meaning:
- Collateral released and closure cash receipt posted for GivenLoan.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "rokkad.events.loan.released.v1",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "loan_id": {"type": "string", "minLength": 1},
    "loan_pk": {"type": "integer", "minimum": 1},
    "loan_kind": {"type": "string", "const": "GivenLoan"},
    "release_id": {"type": "string", "minLength": 1},
    "release_pk": {"type": "integer", "minimum": 1},
    "release_date": {"type": "string", "format": "date-time"},
    "currency": {"type": "string", "const": "INR"},
    "principal_amount": {"type": "string", "pattern": "^-?\\d+(\\.\\d{1,2})?$"},
    "interest_amount": {"type": "string", "pattern": "^-?\\d+(\\.\\d{1,2})?$"},
    "total_amount": {"type": "string", "pattern": "^-?\\d+(\\.\\d{1,2})?$"},
    "payment_method": {"type": "string", "enum": ["CASH", "BANK", "CHEQUE", "UPI", "CARD", "OTHER"]},
    "reference_number": {"type": "string"},
    "released_by_customer_id": {"type": ["integer", "null"], "minimum": 1},
    "voucher_rule_key": {"type": "string", "const": "GIVENLOAN_RELEASE"}
  },
  "required": [
    "loan_id",
    "loan_pk",
    "loan_kind",
    "release_id",
    "release_pk",
    "release_date",
    "currency",
    "principal_amount",
    "interest_amount",
    "total_amount",
    "payment_method",
    "reference_number",
    "voucher_rule_key"
  ]
}
```

Recommended idempotency_key format:
- loan.released:{tenant_schema}:{release_pk}:v1

## 3) Minimal Migration Sequence (No Big-Bang)

## Phase A: Infrastructure First (No Behavior Change)

1. Add outbox table and indexes.
2. Add event publisher helper with same-transaction write support.
3. Add DEA consumer worker with idempotency + retry + DLQ.
4. Add metrics and admin visibility for event lag and failures.

Exit criteria:
- Production-safe infra exists and is dark (feature flags off).

## Phase B: Dual-Write from Girvi (Still Keep Current Sync)

1. In disbursal/payment/release actions, emit outbox events in same transaction.
2. Keep existing synchronous posting path unchanged.
3. DEA consumer runs in shadow mode and logs what it would post.

Exit criteria:
- Event payloads validated for 2-4 weeks.
- No schema/version issues.

## Phase C: DEA Consumer Active with Idempotent No-Op Safeguard

1. Enable DEA consumer posting for small tenant cohort.
2. Keep sync path on, but make consumer detect already-posted marker and no-op.
3. Compare posted amounts and voucher fingerprints daily.

Exit criteria:
- Reconciliation drift == 0 on pilot tenants.
- No duplicate postings.

## Phase D: Cutover by Operation Type

1. Turn off synchronous posting for loan.disbursed only.
2. Monitor, then turn off synchronous posting for loan.payment.received.
3. Finally cut over loan.released.

Exit criteria:
- All three Girvi events post through async path only.

## Phase E: Remove Inheritance Coupling and Legacy Sync Calls

1. Remove/neutralize Girvi direct posting service calls in request path.
2. Remove BusinessDoc-dependent posting assumptions from Girvi domain model path.
3. Keep compatibility adapter only if required for old reads.

Exit criteria:
- Girvi runtime path no longer depends on DEA posting execution in-process.

## Phase F: Hardening

1. Add CI checks for forbidden runtime imports (Girvi->DEA model posting internals).
2. Add contract tests for all three event schemas.
3. Add replay runbook and incident SOP.

Exit criteria:
- Policy matrix edge is E (event-only) and enforced by CI.

## 4) Cutover Flags (Recommended)

1. ENABLE_GIRVI_OUTBOX_EMIT
2. ENABLE_DEA_EVENT_CONSUMER
3. ENABLE_DEA_CONSUMER_PILOT_TENANTS
4. ENABLE_SYNC_POSTING_FALLBACK
5. ENABLE_GIRVI_SYNC_POSTING (turn off in stages)

## 5) Operational Guardrails

1. Idempotency uniqueness:
- unique(event_id)
- unique(tenant_schema, idempotency_key)

2. Retry policy:
- exponential backoff with cap
- DLQ after N attempts

3. Observability:
- event lag p95
- consumer success/failure rate
- per-event-type processing time
- reconciliation drift dashboard

## 6) Mapping to Existing Code Anchors

Current code points impacted:
1. apps/tenant_apps/girvi/models/loan_refactored.py
2. apps/tenant_apps/girvi/service_modules/payment.py
3. apps/tenant_apps/girvi/models/release.py
4. apps/tenant_apps/dea/models/payment.py

Target behavior:
- Keep loan domain logic where it is.
- Move posting execution ownership to DEA consumer.
- Preserve business correctness with transactional event emission and idempotent async posting.

