# ADR: Dependency Edge Change - <From App> -> <To App>

Date: <YYYY-MM-DD>
Status: <Proposed|Accepted|Superseded|Deprecated|Rejected>
Owners: <Architecture + Domain Owners>
Related Policy: ../DEPENDENCY_POLICY_MATRIX.md

## Edge Classification Change

- From: <A|E|L|X>
- To: <A|E|L|X>
- Runtime scope: <models/services/views/signals/tasks>

## Current Coupling Evidence

1. <file path + symbol>
2. <file path + symbol>

## Problem Statement

<Why current edge is risky or inconsistent with policy>

## Decision

<What exact coupling model is allowed after this change>

## Allowed Integration Surface

1. Allowed imports/calls:
   - <list>
2. Forbidden imports/calls:
   - <list>
3. Required contracts/facades/events:
   - <list>

## Migration Plan

1. Introduce adapter/facade/event contract.
2. Dual path behind feature flag (if runtime critical).
3. Remove forbidden direct imports.
4. Add CI guardrail test.

## Acceptance Criteria

1. No runtime forbidden imports remain for this edge.
2. Behavior parity validated in integration tests.
3. Policy matrix updated if classification changed.

## Risks and Mitigations

1. Risk: <e.g., hidden side effects>
   - Mitigation: <tests/observability>

## Rollback

- Conditions:
  - <measurable trigger>
- Action:
  - <flag rollback / revert path>

## Review Trigger

Revisit when:
1. <new domain requirement>
2. <policy changes>
