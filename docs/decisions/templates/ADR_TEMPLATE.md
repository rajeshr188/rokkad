# ADR: <Title>

Date: <YYYY-MM-DD>
Status: <Proposed|Accepted|Superseded|Deprecated|Rejected>
Owners: <Team/People>
Tags: <tenant-arch, dea, girvi, notify_v2, security, migration>
Supersedes: <optional file>
Superseded by: <optional file>

## Summary

<One paragraph describing the decision and expected outcome.>

## Context / Problem Statement

<What problem are we solving? What constraints matter?>

## Decision

<The exact decision. Keep this normative and testable.>

## Decision Details

1. Scope:
   - <apps/modules affected>
2. Boundaries:
   - <allowed / forbidden coupling rules>
3. Data and contracts:
   - <schema/version/idempotency if relevant>
4. Operational model:
   - <sync vs async, queue/worker model>

## Rationale

1. <why this is better than alternatives>
2. <risk tradeoffs accepted>

## Consequences

### Positive

1. <benefit>

### Negative / Costs

1. <cost>
2. <migration burden>

## Rollout / Migration Plan

1. <phase 1>
2. <phase 2>
3. <phase 3>

Rollback criteria:
- <clear measurable rollback trigger>

## Guardrails and Observability

1. Feature flags:
   - <flags>
2. Metrics:
   - <p95 latency, error rate, drift>
3. Alerts:
   - <alert thresholds>

## Test Strategy

1. Unit:
   - <scope>
2. Integration:
   - <scope>
3. Reconciliation/regression:
   - <scope>

## Alternatives Considered

1. <alternative A> - rejected because...
2. <alternative B> - rejected because...

## Open Questions

1. <question>

## Review Trigger

Revisit when:
1. <condition>
2. <condition>
