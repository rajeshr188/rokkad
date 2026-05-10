# ADR: Migration and Cutover - <Capability/Module>

Date: <YYYY-MM-DD>
Status: <Proposed|Accepted|Superseded|Deprecated|Rejected>
Owners: <Platform + Domain Owners>

## Summary

<What is being migrated and why>

## Current State

1. Runtime path(s):
   - <files/systems>
2. Known risks:
   - <data integrity, coupling, outages>

## Target State

1. Runtime path(s):
   - <new architecture>
2. Invariants:
   - <must always hold true>

## Cutover Strategy

1. Phase 0: Infra readiness
2. Phase 1: Dual-write/shadow
3. Phase 2: Pilot tenants
4. Phase 3: Full cutover
5. Phase 4: Legacy removal

## Feature Flags

1. <FLAG_A>
2. <FLAG_B>
3. <FLAG_C>

## Backfill / Data Migration

1. Required migrations:
   - <schema>
2. Backfill process:
   - <job>
3. Verification query/report:
   - <how to prove parity>

## Verification Gates

Gate 1:
1. <metric threshold>
2. <error budget>

Gate 2:
1. <reconciliation check>
2. <latency target>

## Rollback Plan

1. Rollback trigger:
   - <objective condition>
2. Immediate actions:
   - <flags / traffic shift>
3. Data safety steps:
   - <consistency checks>

## Ownership and On-call

1. Execution owner:
   - <team>
2. Incident owner during cutover:
   - <team/person>

## Completion Criteria

1. Legacy runtime path disabled.
2. New path meets SLOs for two consecutive windows.
3. Guardrail tests merged and passing.

## Review Trigger

Revisit when:
1. Migration exceeds timeline by <X> days.
2. Unexpected consumer drift appears.
