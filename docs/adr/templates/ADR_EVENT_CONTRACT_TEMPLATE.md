---
status: draft
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# ADR: Event Contract - <event.type>

Date: <YYYY-MM-DD>
Status: <Proposed|Accepted|Superseded|Deprecated|Rejected>
Owners: <Producer Team + DEA Team + Notify Team>
Producer: <app>
Consumers: <dea posting, notify_v2, projections>

## Summary

<What business fact this event represents>

## Event Metadata

- Event type: <event.type>
- Schema version: <integer>
- Delivery guarantee: at-least-once
- Ordering expectation: <per aggregate / none>
- Idempotency key format: <string pattern>

## Trigger Conditions

1. Emitted when:
   - <domain transition>
2. Not emitted when:
   - <guard cases>

## Envelope Schema

Required fields:
1. event_id (uuid)
2. event_type
3. schema_version
4. tenant_schema
5. occurred_at
6. producer_app
7. aggregate_type
8. aggregate_id
9. idempotency_key
10. payload

## Payload Schema

```json
{
  "<field>": "<type>",
  "<field>": "<type>"
}
```

## Consumer Responsibilities

1. DEA posting:
   - <rule key resolution>
2. notify_v2:
   - <notification behavior>
3. read models:
   - <projection updates>

## Validation and Compatibility Rules

1. Producer must emit required fields only.
2. Backward-compatible additions allowed.
3. Breaking changes require schema_version increment and migration ADR.

## Error Handling

1. Retry policy: <backoff/cap>
2. DLQ policy: <threshold>
3. Replay process: <command/runbook>

## Observability

1. Metrics: lag, success rate, failure rate.
2. Audit fields: actor_user_id, trace_id.

## Test Plan

1. Contract tests for payload shape.
2. Consumer idempotency tests.
3. End-to-end producer->outbox->consumer tests.

## Review Trigger

Revisit when:
1. Domain semantics change.
2. New consumer requires stricter contract guarantees.

