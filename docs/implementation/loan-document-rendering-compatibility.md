---
status: active
owner: project
updated: 2026-08-13
tags: [loans, documents, compatibility, printing]
related:
  - ../adr/2026-08-13-loan-application-boundaries-and-monitoring.md
---

# Loan Document Rendering Compatibility

## Current path

Loans has two deliberately different rendering contracts.

### Current authoring

New layout authoring uses schema v3. A v3 layout describes logical document
surfaces and delegates paper size, copy arrangement, duplex/imposition, and
other physical packaging to an explicit immutable print-profile revision.
Series assignment may override the workspace assignment; otherwise a built-in
profile is used. A newly issued document records the resolved profile identity,
revision, hash, and resolution source with its immutable artifact.

### Compatibility rendering

Schema-v1/v2 layouts predate print profiles. Their definitions can embed
physical composition such as `copy_mode` and sheet packaging. Reinterpreting
those definitions as schema v3 can change pagination, copy placement, signature
position, or the paper presented to a printer.

The explicit `?print_profile=legacy` path is therefore an Owner/Admin recovery
control. It requests the embedded historical composition; it is never a silent
fallback. Ordinary rendering resolves the assigned current profile, while an
already stored official issue must return its exact stored artifact rather than
rerendering under current configuration.

## Why it is retained

The compatibility path may still be required by:

- an active schema-v1/v2 layout revision;
- an immutable issue whose reproduction depends on its historical composition;
- a physical printer workflow validated against embedded A5/A4 packaging;
- recovery of a document when current profile assignment is unavailable or
  known to be unsuitable.

This is rendering compatibility, not permission to edit issued evidence or to
silently downgrade new layouts.

## Removal gate

Removal is safe only after a tenant-wide diagnostic proves all of the following:

1. no active or assigned layout revision uses schema v1/v2;
2. every required historical artifact is stored and can be retrieved without
   rerendering;
3. no supported printer or document procedure uses embedded composition;
4. operators have accepted schema-v3 output for every required document kind;
5. recovery and audit tests no longer require the legacy selector.

Until that evidence exists, schema-v1/v2 reading and explicit legacy recovery
remain supported. New layouts must continue to use schema v3.
The official-issue application boundary is service-owned. It performs existing
issue reuse, layout and print-profile resolution, configurable rendering,
recovery-path auditing, and immutable issue persistence. HTTP views retain
workspace authorization, recovery permission checks, conflict responses, and
PDF response headers. Fixed rendering and the explicit legacy print profile
remain supported fallbacks under the removal gate below.

