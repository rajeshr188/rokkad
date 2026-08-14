---
status: future
owner: notify-v2
updated: 2026-08-14
tags: [notify, notify-v2, girvi, migration, retirement]
related:
  - ../adr/2026-08-14-legacy-notify-retirement-boundary.md
  - ../implementation/whatsapp-notifications-architecture-audit.md
---

# Legacy Notify to Notify v2 retirement

## Goal

Decouple every application from legacy `notify`, isolate it as read-only
history, and finally remove its runtime without losing Girvi behavior, printed
documents, delivery evidence, tenant history, or upgrade safety.

## Strategy

Use dependency inversion, not a big-bang replacement:

```text
consumer apps -> owned interfaces/selectors -> Notify v2
                                      |
                                      +-> temporary read-only legacy adapter
```

Consumer apps must not import legacy models or services directly. A temporary
adapter may read old evidence while migration is incomplete. It must never
create new legacy rows.

## Current blockers

- Girvi scheduled reminders use legacy `Notification` and `NoticeGroup`.
- Girvi notice creation, auction integration, and print flows use legacy
  services and models.
- Party/Girvi reporting counts legacy `NotificationItem` links.
- Tenant default seeding creates legacy notice configuration and templates.
- `/notify/` and workspace-slug routes expose legacy pages.
- Notify v2 imports authorization helpers from `notify.access`.
- Existing tenant schemas contain historical legacy notice evidence.

## Dependency inventory

| Consumer | Current legacy dependency | Target |
| --- | --- | --- |
| Notify v2 | `notify.access` authorization | Notify v2 or neutral tenant access |
| Girvi | reminder/auction producers, tasks, adapter, printing | Girvi-owned commands calling Notify v2 |
| Party | indirect Girvi notice history/counts | Notify v2 selector plus temporary history adapter |
| Orgs | workspace legacy notification wrappers | Notify v2 routes or explicit history routes |
| Tenant seeding | legacy configs/templates | Notify v2 defaults only |
| URL/settings | installed app and `/notify/` routes | remove after isolation gates |

Tests that import legacy models are evidence of the old contract, not runtime
consumers. Replace them as each owning boundary changes.

## Migration sequence

### 1. Establish the dependency gate

Add a repository check that lists production imports, URL includes, seed hooks,
tasks, signals, admin registration, and model/migration references. Classify
each as runtime, historical migration, test, or documentation. Do not treat
historical migrations as runtime coupling.

### 2. Separate shared authorization

Move notification access helpers to Notify v2 or a neutral tenant access
module. Preserve permissions and route behavior. Remove Notify v2 imports from
the legacy app.

### 3. Add owned consumer boundaries

Give each consumer a small interface it owns. Girvi owns commands for reminder
and auction intent. Party owns a notice-history selector. Orgs owns routing,
not notification behavior. Those boundaries call Notify v2 for new work and,
only where required, one read-only legacy history adapter.

### 4. Inventory and reconcile

Add a tenant-aware audit command. Report legacy groups, notifications, items,
templates, printed artifacts, status, recipients, and linked business objects.
Record unmappable and duplicate data. Make no writes in this step.

### 5. Migrate Girvi producers

Move single reminders, scheduled reminder batches, and auction notices to
explicit Notify v2 events, jobs, and immutable payloads. Use stable source and
dedupe identities. Do not dual-write after each producer cuts over.

### 6. Replace print and batch behavior

Reach parity for notice selection, grouped PDFs, templates, downloads, and
operator status. Notify v2 artifacts become authoritative for new work.

### 7. Replace reads and reports

Move Party notice totals, Girvi history, operational queues, and detail pages to
Notify v2 selectors. If old records are not migrated, expose them through one
read-only historical adapter with clear Legacy labels.

### 8. Decouple Orgs, seeds, and routes

Move workspace wrappers to Notify v2 or clearly labelled history pages. Remove
legacy seed creation. New tenants must operate without legacy rows. Existing
tenants retain history but cannot create new legacy work. Stop navigation to
legacy mutation screens.

### 9. Isolate and freeze legacy Notify

Enforce no new legacy writes. Keep only the minimum read-only history adapter
and required historical migrations. Remove legacy tasks, signals, mutable admin,
services, and cross-app imports. Observe and monitor for attempted writes.

### 10. Reconcile every tenant

For each tenant compare source links, recipients, notice types, counts,
documents, timestamps, and delivery status. Store the reconciliation result and
exceptions.

### 11. Remove runtime surfaces

Remove legacy navigation, `/notify/` routes, workspace compatibility wrappers,
signals, tasks, imports, admin mutation, and the app from current runtime
settings only after all production references are gone.

### 12. Preserve upgrade and history safety

Keep historical migrations needed by supported upgrade paths. Decide separately
whether legacy tables remain as read-only archive tables, are migrated into
Notify v2 evidence, or are exported before deletion. Never drop them merely
because runtime imports reached zero.

## Acceptance gates

- Repository search finds no production import of legacy models/services.
- The dependency gate rejects any new legacy runtime import.
- Legacy writes are zero outside migrations and approved archival tooling.
- Every consumer works with the legacy app isolated from normal runtime paths.
- New-tenant bootstrap and seed parity pass without `notify`.
- Girvi reminder, auction, print, batch, retry, and history tests pass on v2.
- Party and Girvi notice totals match the agreed historical policy.
- Every tenant reconciliation is clean or has an accepted exception record.
- Notify v2 contains the required source, recipient, template, payload,
  artifact, attempt, and provider evidence.
- No legacy mutation occurs during an observation period.
- Tenant migration replay, Django checks, route tests, and deployment rollback
  rehearsal pass.

## Explicit non-goals

- Rewriting unrelated Girvi lifecycle behavior.
- Adding automation, campaigns, conversations, or a new provider framework.
- Copying every obsolete legacy field into Notify v2.
- Dropping tables before retention and upgrade decisions are accepted.

## Decisions to confirm when work resumes

1. Must all historical notices be migrated into Notify v2, or may old records
   remain in a read-only legacy archive?
2. How long must rendered legacy PDFs and delivery evidence be retained?
3. After access decoupling, should the first consumer slice be Girvi scheduled
   reminders, Orgs routes, or Party history?
4. How long should the zero-legacy-write observation period run?
5. Who may approve tenant reconciliation exceptions and final table deletion?

## Restart point

Answer the five decisions above. Then implement only the dependency gate,
authorization decoupling, and read-only inventory command. Do not migrate
producers, freeze writes, or delete routes in that first slice.
