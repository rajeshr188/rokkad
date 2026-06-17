---
status: accepted
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# ADR: Event Contract Acceptance - loan.disbursed and loan.released

Date: 2026-05-03
Status: Accepted
Owners: Girvi Team, DEA Team, Notify_v2 Team, Platform Architecture
Tags: event-contract, girvi, dea, notify_v2, outbox
Related:
- ../GIRVI_EVENT_DRIVEN_DEA_POSTING_SPEC.md
- ../DEPENDENCY_POLICY_MATRIX.md

## Summary

This ADR accepts version 1 contracts for loan.disbursed and loan.released as canonical cross-context events from Girvi to DEA (and secondary consumers such as notify_v2 projections).

## Context / Problem Statement

Girvi and DEA currently have synchronous and direct model-level coupling. To support reliable eventual consistency and controlled retries, domain facts must be emitted as stable, versioned events with explicit idempotency.

## Decision

1. Adopt event types:
   - loan.disbursed (v1)
   - loan.released (v1)
2. Use common envelope and strict payload requirements defined below.
3. DEA posting rules consume these events as source of truth.
4. Any breaking change requires schema_version increment and a superseding ADR.

## Contract Metadata

- Delivery guarantee: at-least-once
- Ordering: per aggregate best-effort; consumer must be idempotent
- Producer app: girvi
- Consumer(s): dea posting consumer (required), notify_v2/read models (optional)

## Common Envelope (Required)

1. event_id (uuid)
2. event_type
3. schema_version = 1
4. tenant_schema
5. occurred_at (date-time)
6. producer_app = girvi
7. aggregate_type (GivenLoan|TakenLoan)
8. aggregate_id
9. idempotency_key
10. payload

## Accepted Contract: loan.disbursed (v1)

Required payload fields:
1. loan_id
2. loan_pk
3. loan_kind (GivenLoan|TakenLoan)
4. series_id
5. customer_id
6. loan_date
7. disbursed_at
8. currency = INR
9. principal_amount (decimal string)
10. payment_method (CASH|BANK|CHEQUE|UPI|CARD|OTHER)
11. reference_number
12. dea_direction (PAYMENT|RECEIPT)
13. voucher_rule_key (GIVENLOAN_PAYMENT|TAKENLOAN_RECEIPT)

Idempotency key format:
- loan.disbursed:{tenant_schema}:{loan_kind}:{loan_pk}:v1

## Accepted Contract: loan.released (v1)

Required payload fields:
1. loan_id
2. loan_pk
3. loan_kind = GivenLoan
4. release_id
5. release_pk
6. release_date
7. currency = INR
8. principal_amount (decimal string)
9. interest_amount (decimal string)
10. total_amount (decimal string)
11. payment_method (CASH|BANK|CHEQUE|UPI|CARD|OTHER)
12. reference_number
13. voucher_rule_key = GIVENLOAN_RELEASE

Optional payload fields:
1. released_by_customer_id

Idempotency key format:
- loan.released:{tenant_schema}:{release_pk}:v1

## Consumer Responsibilities

DEA posting consumer must:
1. Validate envelope and payload schema.
2. Enforce idempotency using event_id and idempotency_key.
3. Resolve voucher rule via voucher_rule_key.
4. Persist posting outcome for replay/audit.

notify_v2/read-model consumers may:
1. Use accepted payload fields only.
2. Avoid introducing producer coupling assumptions not present in contract.

## Compatibility Rules

1. Backward-compatible additive fields allowed within schema_version 1.
2. Breaking field/type/semantic changes require schema_version 2 and superseding ADR.
3. Deprecated fields must be retained for one release window with migration notes.

## Observability and Operations

1. Metrics:
   - contract validation failure rate
   - consumer processing latency
   - duplicate event suppression count
2. Error handling:
   - retry with backoff
   - DLQ on exhausted attempts
   - replay tooling for recoverable failures

## Test Strategy

1. Producer contract tests for both events.
2. Consumer contract validation and idempotency tests.
3. End-to-end integration tests from Girvi action to DEA posting result.

## Rollout Notes

1. Begin with dual-write period while sync posting remains available behind flag.
2. Enable consumer for pilot tenants first.
3. Cut over by operation type after reconciliation parity.

## Review Trigger

Revisit when:
1. Schema evolution is required for loan product changes.
2. New mandatory consumer introduces additional contract requirements.

