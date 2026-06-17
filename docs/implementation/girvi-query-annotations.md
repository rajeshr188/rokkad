---
status: active
owner: project
updated: 2026-06-17
tags: [implementation, girvi, querysets]
related: [../domain/girvi.md, ../archive/girvi/manager__README_LOAN_ANNOTATIONS.md]
---

# Girvi Query Annotations

Girvi query annotations support dashboard, list, and report metrics without duplicating calculation logic in templates/views.

## Direction

- Keep annotation names stable and documented.
- Prefer selectors/queryset helpers for reusable read models.
- Keep presentation formatting in templates/forms, not query expressions.
- Use facades for cross-app consumers.

Archived manager notes are preserved in [archive/girvi](../archive/girvi/).
