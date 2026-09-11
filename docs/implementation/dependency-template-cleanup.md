---
status: active
owner: project
updated: 2026-09-09
tags: [dependencies, cleanup]
---

# Dependency and template cleanup (R13)

This bounded cleanup follows the [project review](../architecture/2026-09-09-project-review.md).
Reachability was inspected across application source, settings, templates, commands,
tests and fixtures, including template inheritance/includes, dynamic template names
and migration dependencies. Package metadata was checked for reverse dependencies.
This is not a claim that every remaining package or template is necessary.

| Removed | Evidence |
| --- | --- |
| django-viewflow 2.2.15 | Only app registration; no application imports, flow declarations, URLs or template consumers |
| django-activity-stream 2.0.0 | Not registered; only commented registry code in accounts/apps.py, also removed |
| django-extensions 3.2.3 | Not registered; no imports or extension-command usage in repository workflows |
| django-slick-reporting 1.3.1 | Registration/configuration and three unreachable templates only; no report views or URLs |
| Eleven templates/contact HTML files | References confined to the retired template set; Contact routes redirect to Party, which renders party templates |
| templates/pages/company_dashboard.html | No renderer; pages.views.company_dashboard redirects to the canonical Workspace dashboard |
| Two templates/slick_reporting HTML files | Internal inheritance only; no external renderer or template consumer |

No installed distribution declared a dependency on the four removed packages.
Generic basename matches such as form.html and base.html were distinguished from
actual template paths. The current dashboard renders company/workspace_dashboard.html.
The public contact page uses pages/contact.html and remains available.

Legacy URL adapters, Party contact permission aliases and historical migrations
remain intact. Removed templates are recoverable from Git history; they are not
copied into another runtime template directory. No database tables are dropped.

## Intentionally retained

- django-render-block: active Workspace preference and HTMX rendering helpers.
- django-filter, django-tables2, django-select2 and HTMX: current application users.
- django-redis/redis: optional configured cache backend, not a default requirement.
- Other pinned/transitive packages, including reporting export formats: no broad
  transitive pruning, upgrades or runtime/development split without separate evidence.

Validation is recorded in [Status](../STATUS.md). A clean image install and pip
check establish dependency consistency, not vulnerability or production acceptance.
The developer virtual environment is not uninstalled or rewritten by this cleanup.
