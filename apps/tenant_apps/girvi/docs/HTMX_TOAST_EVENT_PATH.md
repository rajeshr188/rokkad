# HTMX Toast/Event Path for Flash Messages

## Purpose

When actions are performed through HTMX partial requests, Django `messages` are often not visible because the messages block is outside the swapped region. This document defines a reusable pattern to show user feedback (success/warning/error/info) without forcing full page reloads.

## Problem Summary

In this project:

- Global Django messages are rendered in base layout.
- Most HTMX requests swap only workspace content (`#content`) or smaller fragments.
- Therefore, message containers in the outer layout are not re-rendered during partial swaps.

Result: server sets `messages.error(...)`, but user sees no feedback for HTMX requests.

## Design Goal

Create a single cross-app mechanism that:

1. Works for HTMX and non-HTMX requests.
2. Keeps existing Django messages behavior for full page loads.
3. Supports simple server-side usage from any view.
4. Avoids copy/paste JS in app-specific templates.

## Recommended Pattern

### 1. Standard event contract

Use one event name for frontend notifications:

- Event: `app:toast`
- Payload fields:
  - `message` (string, required)
  - `level` (string: `success`, `warning`, `error`, `info`)
  - `timeout` (number, optional)

### 2. Server response strategy

For actions that currently use Django messages:

- Non-HTMX request:
  - keep current behavior (`messages.*` + redirect/render)
- HTMX request:
  - return status `204` or lightweight response
  - set `HX-Trigger` header with `app:toast` payload

This ensures the UI receives feedback even when only a fragment is swapped.

### 3. Frontend listener strategy

Add one global listener in base layout JS:

- Listen for `app:toast` on `document.body`
- Create/append toast element into global toast container
- Show toast via Bootstrap Toast API
- Map Django-like levels to Bootstrap classes:
  - `error` -> `danger`
  - `success` -> `success`
  - `warning` -> `warning`
  - default -> `info`

### 4. Keep toast template level mapping consistent

Ensure the reusable toast template also maps `error` to `danger`, so server-originated and event-originated toasts look the same.

## Suggested Helper (server side)

Introduce a small helper usable from views:

- Inputs:
  - request
  - message
  - level
  - redirect_url (optional)
  - extra triggers (optional)
- Behavior:
  - HTMX: returns response with `HX-Trigger`
  - Non-HTMX: uses Django messages and normal redirect

This prevents per-view branching duplication.

## Example Use Cases

- `loan_renew` not implemented yet:
  - HTMX: trigger warning toast, stay in current context
  - Non-HTMX: Django warning message + redirect
- Transition commands (`approve`, `undo_release`, etc.)
- Bulk actions (`merge`, `delete`, `notify`)

## Integration Notes for This Codebase

Current relevant files:

- `templates/layouts/base.html` (messages block + global scripts)
- `templates/toasts.html` (toast container)
- `apps/tenant_apps/girvi/views/loan.py` (`loan_renew` and transition actions)

The pattern should be implemented centrally in base layout and reused across apps, not only Girvi.

## Rollout Plan

1. Add global `app:toast` listener in base layout script.
2. Normalize level mapping in toast rendering.
3. Add a lightweight response helper for HTMX toast triggers.
4. Migrate one endpoint first (`loan_renew`) as reference implementation.
5. Gradually adopt in other HTMX actions.

## Risks and Mitigations

- Risk: mixed toast styles between template and JS-generated toasts.
  - Mitigation: one shared level->class mapping.

- Risk: duplicate messages (both Django message and toast for same request).
  - Mitigation: HTMX path should use trigger only; non-HTMX path uses Django messages only.

- Risk: event name drift across apps.
  - Mitigation: keep `app:toast` as standard contract in docs.

## Acceptance Criteria

- HTMX action can display warning/success/error without full page reload.
- Non-HTMX behavior remains unchanged.
- No app-specific duplication of toast JS.
- `loan_renew` can be used as a reference endpoint for this pattern.
