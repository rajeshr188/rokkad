---
status: accepted
owner: notify-v2
updated: 2026-08-14
tags: [notify, notify-v2, retirement, migration]
related:
  - ../plans/legacy-notify-to-notify-v2-retirement.md
  - ../implementation/whatsapp-notifications-architecture-audit.md
---

# Legacy Notify retirement boundary

## Context

Notify v2 is the intended notification platform. The legacy `notify` app still
owns active Girvi reminder creation, notice groups, printed notices, auction
notice integration, Party notice counts, tenant seed data, historical records,
workspace routes, and authorization helpers used by Notify v2.

Deleting it now would break live behavior and could remove audit history.

## Decision

Treat `notify` as legacy but supported until its consumers are migrated and
reconciled. Build no new product workflow on it. New notification behavior goes
to Notify v2.

Retire it dependency-first. Decouple every consuming app from legacy imports
and data ownership. Then isolate `notify` as a read-only historical boundary.
Only after isolation and reconciliation may the runtime app be removed. An app
must not dual-write to both systems after its cutover.

Remove the runtime app only after:

- every production import and route has moved;
- no app outside the isolated compatibility boundary reads legacy models;
- Girvi reminder, auction, batch, print, and reporting parity passes;
- tenant seeding no longer creates legacy configuration;
- historical evidence remains readable from an archive or migrated model;
- every tenant passes count, identity, artifact, and delivery reconciliation;
- upgrade migrations have a safe path across supported deployments.

Database tables are removed only through a later explicit data-retention
decision. Removing URLs and runtime imports does not itself authorize deleting
historical rows.

## Consequences

The retirement is staged, tenant-safe, and reversible until final removal.
Notify v2 may temporarily read legacy evidence through a narrow adapter. The
project avoids a big-bang rewrite and does not preserve two writable systems.
