# ADR: Deprecation and Retirement - <Component>

Date: <YYYY-MM-DD>
Status: <Proposed|Accepted|Superseded|Deprecated|Rejected>
Owners: <Team>

## Summary

<What is being deprecated and target replacement>

## Scope

Deprecated component:
- <module/app/service>

Replacement:
- <new module/app/service>

Out of scope:
- <explicit non-goals>

## Decision

1. No new feature work on deprecated component.
2. All new integrations must use replacement component.
3. Retirement deadline: <date>

## Compatibility Window

1. Start date: <date>
2. End date: <date>
3. Allowed temporary paths:
   - <list>

## Migration Plan

1. Freeze writes/new references.
2. Add compatibility adapter (if needed).
3. Migrate consumers and producers.
4. Remove runtime references.
5. Delete deprecated code.

## Enforcement

1. CI guardrail: block new imports to deprecated module.
2. PR checklist item: confirm no deprecated reference.
3. CODEOWNERS requirement for exceptions.

## Risks

1. Functional gaps in replacement
2. Hidden dependencies in tests/admin/scripts

Mitigations:
1. Gap list and owners
2. Dry-run cutover in non-prod tenant

## Success Metrics

1. Deprecated module runtime traffic = 0.
2. Replacement path SLOs met.
3. No new references over 2 sprints.

## Final Removal Checklist

1. Runtime imports removed
2. URLs/tasks/signals detached
3. Migrations/docs updated
4. Post-removal smoke tests passed

## Review Trigger

Revisit when:
1. Deadline risk > 2 sprints.
2. Critical functionality still depends on deprecated path.
