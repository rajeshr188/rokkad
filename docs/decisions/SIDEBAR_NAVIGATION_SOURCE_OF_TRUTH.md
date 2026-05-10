# Sidebar Navigation Source-of-Truth Decision

Date: 2026-05-01
Status: Accepted (Implemented)
Owners: UI Architecture, Tenant Framework

## Summary

The sidebar source of truth is the template implementation:

- templates/components/navigation/sidebar.html

The Python navigation config module is retained for future dynamic rollout only:

- django_project/navigation.py

## Problem Statement

The codebase had two navigation definitions:

1. Live sidebar links and gating in template code.
2. A separate Python NAVIGATION_STRUCTURE exposed by a context processor.

This creates drift risk:

- stale URL names
- mismatched permission gating
- uncertainty about which navigation actually drives UI behavior

## Decision

Adopt template sidebar as the only active source of truth for now.

Implementation actions:

1. Removed django_project.context_processors.navigation_config from template context processors.
2. Kept navigation_config() as a deprecated no-op compatibility shim.
3. Marked django_project/navigation.py as future dynamic-navigation config, not live source.

## Why This Decision

1. Current runtime reality
   The sidebar is rendered directly from template code today.
2. Lower operational risk
   One active source of truth is easier to keep correct.
3. Faster fixes
   URL and permission changes are made where users actually navigate.
4. Future flexibility
   navigation.py remains available for a deliberate dynamic migration later.

## Current Operating Model

- Navigation rendering: template-driven.
- Permission gating in sidebar: user_permissions context from canonical resolver.
- Workspace URL kwargs: passed directly in template using effective_workspace.

## Future Dynamic Navigation Plan (When Needed)

If dynamic navigation is required later, do a full migration (not partial):

1. Introduce a single nav resolver service
   Inputs: request, effective_workspace, effective_permissions.
2. Add explicit URL argument metadata per nav item
   Example: workspace_kwarg mapping and URL kwargs builder.
3. Generate sidebar from resolved nav structure only
   Remove duplicate hardcoded links from template.
4. Add automated validation
   - reverse() validation for all nav url_name entries
   - permission visibility tests per role
   - active-state tests per route
5. Remove deprecated compatibility shim
   Delete no-op navigation_config after migration is complete.

## Explicit Non-Goals (Current)

- Partial dynamic navigation where some links come from template and some from Python config.
- Re-introducing dual source-of-truth behavior.

## Review Trigger

Revisit this decision when:

- Product requires per-tenant configurable nav layout.
- Navigation personalization or feature flags need server-side composition.
- Template complexity makes maintenance cost higher than dynamic generation.
