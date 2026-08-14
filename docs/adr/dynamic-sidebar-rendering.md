---
status: accepted
owner: project
updated: 2026-06-17
tags: [adr]
related: []
---

# Dynamic Sidebar Rendering Decision

Date: 2026-04-30
Status: Deferred (recommended for planned migration)
Owner: Workspace team

## Summary

Should we switch to dynamic sidebar rendering?

- Long-term: Yes. A dynamic sidebar is better for maintainability because one configuration controls labels, visibility, and routing.
- Right now: Not immediately. The dynamic navigation configuration is partially out of sync with URLs currently used by production templates.

## Current Source of Truth

For immediate fixes, keep the active sidebar template as the source of truth:

- templates/components/navigation/sidebar.html
- Included from templates/layouts/workspace.html

## Why Migration Is Deferred

The dynamic config in django_project/navigation.py has route-name mismatches versus active production templates. Enabling dynamic rendering without alignment risks NoReverseMatch and broken menu links.

## Known Mismatches (must fix before migration)

1. Sales
- Dynamic config: sales:invoice_list
- Active sidebar: sales:sales_invoice_list

2. Purchase
- Dynamic config: purchase:invoice_list
- Active sidebar: purchase:purchase_invoice_list

3. Contact
- Dynamic config: contact:contact_list
- Active sidebar: contact_customer_list

## Recommendation

1. Keep the current sidebar template for immediate production changes.
2. Plan a safe migration in phases.

## Safe Migration Plan

### Phase 1: Alignment

- Align all route names in django_project/navigation.py with real URL names in production templates and URLConf.
- Align permission keys between dynamic config and active sidebar checks.
- Verify that each configured url_name can reverse in tenant/workspace context.

### Phase 2: Template Wiring

- Wire templates/layouts/workspace.html to render the dynamic navigation component.
- Keep a short-lived fallback switch to the current sidebar template for rollback safety.

### Phase 3: Regression Tests

Add tests to prevent future drift:

- Route resolution tests for every configured url_name in dynamic nav.
- Permission visibility tests for owner/admin/member and selected permission sets.
- Snapshot/assertion test that expected primary menu entries are present for common roles.

## Exit Criteria

Migration is complete when all of the following are true:

- No route mismatch remains between dynamic config and active routes.
- Workspace layout renders dynamic navigation by default.
- Automated tests cover URL reversals and role/permission-based visibility.
- QA signoff confirms parity (or intentional improvements) with existing menu behavior.

## Notes

- This decision intentionally prioritizes production stability over immediate architectural cleanup.
- Once Phase 1 is complete, migration risk drops significantly.

