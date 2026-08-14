---
status: active
owner: project
updated: 2026-06-17
tags: [implementation, workspace, context]
related: [../domain/workspace-auth.md, ../archive/root/CONTEXT_PROCESSOR_USAGE_GAP_ANALYSIS.md]
---

# Workspace Context

Workspace context must be reliable in middleware, templates, navigation, permission checks, and setup flows.

## Direction

- Avoid duplicating workspace lookup logic across context processors.
- Keep context processors lightweight.
- Prefer explicit services/selectors for workspace state used by multiple views.

Source analysis: [CONTEXT_PROCESSOR_USAGE_GAP_ANALYSIS](../archive/root/CONTEXT_PROCESSOR_USAGE_GAP_ANALYSIS.md).
