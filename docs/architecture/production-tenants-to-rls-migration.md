---
status: proposed
owner: project
updated: 2026-09-21
tags: [architecture, migration, portability, django-tenants, rls]
related: [data-portability.md, loans-portability-target.md, ../plans/data-portability.md]
---

# Production migration: Django-tenants source to RLS target

## Decision

Import the three Linode production tenants into new RLS Workspaces through a
versioned, read-only source adapter. Do not restore the old database into the RLS
application database, run Django migrations against the old production database,
or try to convert tenant schemas into shared tables in place.

The old production commit, `4312573fa2dca9f8bea3abd1ab84aadb5bd1e1cd`, is an
ancestor of `rls-mvp`. Its deployment architecture is still different:
`django-tenants` stored operational rows in a PostgreSQL schema for each Company;
the current application stores Workspace-owned rows in shared tables protected by
forced PostgreSQL RLS. A conversion is safer and more auditable than a production
schema rewrite.

This design does not turn the existing import feature into a universal database
importer. It uses a narrow adapter for this known source version and reuses the
current portability contracts only where their destination meaning is sound.

## Scope and source identity

The target scope is three Workspaces, provisionally called JCL, JSK and Lakshmi
Pawn Brokers. Their actual source schema names, Company records, domains and row
counts are facts to discover from a fresh production snapshot. Names from earlier
local rehearsals must not be assumed to identify live Linode schemas.

Every imported record retains this stable source identity:

```
legacy:<installation-uuid>:<tenant-schema>:<source-table>:<source-primary-key>
```

The installation UUID is created once for the source installation and reused in
every snapshot manifest. It prevents collisions between old numeric IDs in different schemas and
makes replay idempotent. Old foreign keys, user IDs and schema-qualified primary
keys never become destination keys.

## What maps where

| Old tenant data | Current destination | Migration rule |
| --- | --- | --- |
| Customer, contact and address rows | Party, contact details, addresses, identifiers and source identities | Import as a reviewed Party bundle. Preserve each old identifier. Do not merge people because names or phones merely resemble each other. |
| Licence and series rows | Workspace setup and source-number provenance | Create or map valid current setup explicitly. Preserve old numbers and series as provenance; reserve migrated ranges. |
| Loan, loan item and terms | Operational loan only when current state is evidenced | Classify before import: complete history, reviewed active opening, historical archive, or hold. |
| Payments, releases and related facts | Immutable financial history or historical evidence | Use strict history only where evidence is complete. Do not invent balances, postings or interest. |
| Users and memberships | New Workspace access | Recreate/invite approved users and assign current roles. Do not copy passwords, sessions or old permissions. |
| Retired Girvi, DEA, Product and legacy Contact concepts | No direct model copy | Map only facts with a defined current destination; retain the remainder in encrypted source and migration evidence. |

For every active loan, a named owner signs off on original principal, principal
outstanding, interest and fees due, paid-through date, interest policy/tenure,
collateral/custody state and exceptions. An old mutable loan amount or a payment
total alone cannot safely establish those facts.

## Four destination paths

1. **Complete loan history.** Use `loan-history/1` only when the loan, items,
   payments, releases and accounting meaning are complete and internally
   consistent.
2. **Active loan at cutover.** Create a reviewed opening position with immutable
   evidence. All collections and releases afterwards use normal current workflows.
   Interest is never backfilled using an assumed rule.
3. **Closed or incomplete legacy loan.** Retain it in the historical evidence
   archive. It remains searchable and exportable as a source claim, not active
   debt, a Party link or a current accounting balance.
4. **Hold.** Leave a record outside operational data until its concrete issue is
   resolved: missing borrower, inconsistent dates, absent custody facts, unknown
   interest policy, or a payment-bearing balance that cannot be reconciled.

This is a one-time conversion from a database snapshot. Normal Party import is a
small user-owned exchange of CSV, JSONL or XLSX records. Loan contracts are
stricter because an incorrect conversion could create false debt, interest,
custody or accounting evidence.

## Required runbook

### 1. Release the importer

Review the uncommitted portability code, migrations, templates and tests; commit
it as an identifiable release; validate it from a clean checkout and clean
database. Record the application image, migration version and source-adapter
version in the run manifest. No run may depend on a developer's working tree.

### 2. Capture a read-only source snapshot

The owner confirmed on September 21 that production photographs and documents live
on the Linode server filesystem, not Cloudflare R2. Inventory the actual media root
and tenant/path layout there. Back up those files separately; the PostgreSQL dump
contains references, not the file bytes. The owner subsequently selected private
R2 for the destination. Read-only source inventory and direct preservation copy
are complete for the inventoried files; application attachments and final-snapshot
reconciliation remain pending. See [the media preservation record](../implementation/linode-media-preservation-20260921.md).
No R2 source-bucket copy is part of this migration.

On Linode, produce a PostgreSQL custom-format dump and separate media manifest
without writing to production. Record the old application commit, PostgreSQL
version, timestamp, checksums, schemas, table definitions, row counts and media
checksums. Use `pg_restore --list` and a disposable restore for inspection; never
restore the dump into the RLS database.

Take a final snapshot after an announced cutover freeze. An earlier snapshot is
only for discovery and rehearsal; the final snapshot is the import source of
record.

The source remains live while discovery and rehearsal run. Do not attempt an
unbounded row-by-row sync between the old application and the new one. Rehearse in
an isolated destination, then stop legacy business writes for the cutover window,
take a final complete archive and build the production destination from that one
source of record. If the final archive differs from the rehearsal archive, rerun
the reviewed adapters and reconciliation against the final archive; do not patch
the difference manually.

### 3. Discover and lock the source contract

Build a source inventory for each tenant schema. Compare actual tables, columns,
constraints and counts with the historical commit. Production drift gets an
explicit adapter version and fixture, never an ad-hoc edit to exported JSON.
Produce a report listing Party candidates, active/closed loan candidates,
payment/release facts and every hold reason.

Versioned `linode-jcl/1`, `linode-jsk/1` and `linode-lakshmi/1` profiles now match
the September 21 discovery archive. Their compatibility does not establish
financial opening facts or approval for operational admission.

### 4. Prepare the RLS destination

Create three Workspaces in a clean target database through ordinary owner-only
migrations and current configuration. Map each source schema to exactly one
Workspace in the signed manifest. Create licences, series and policies explicitly,
recreate approved workspace access, reserve legacy document-number ranges and run
the normal RLS isolation tests before loading business data. Provision the
restricted runtime role for the new database as well: an existing cluster-level
runtime login needs explicit grants on each newly created target database before
the runtime checks or import services can run.

### 5. Import Party and setup records first

Stage, preview and approve one Party bundle per Workspace. The preview must show
required-field errors, duplicate source IDs and proposed matches. Commit each
bundle atomically, retain its receipt and reconcile source-to-destination counts.
No loan is admitted until its borrower resolves to an imported Party or is held.

### 6. Reconcile loans with human gates

Generate proposed classifications from the final snapshot, then review by
Workspace. Operators may correct labels and source mappings, but cannot bulk
override money, balances, interest, borrower, collateral or custody facts. Active
loans need signed opening-position evidence; complete histories need the strict
contract; closed or incomplete records go to the evidence archive. Every exception
has a reason, owner and resolution status.

### 7. Verify and cut over

Reconcile counts, identities, document numbers, principal scope, opening interest
and fees, classifications and held records for each Workspace. Replay the same
snapshot and verify it creates no new records. Verify RLS isolation, representative
borrower, loan, search, collection and release journeys, source exports and archive
search. Owners sign the reconciliation report before go-live.

Keep the legacy Linode application and encrypted snapshot read-only for the agreed
acceptance period. Rollback means returning to the legacy application or rebuilding
a fresh target from the manifest; it never means deleting posted target records in
an attempt to reverse history.

## Current portability status

The portability baseline is committed in `a3e0e2b8` on `rls-mvp`; it is absent from
the old production commit. It is a reviewed release candidate rather than deployed
product capability.

| Capability | Current state | Needed for Linode migration |
| --- | --- | --- |
| Party CSV/JSONL/XLSX bundles, preview, approval and export | Verified three-Workspace rehearsal and clean-target replay | Preserve accepted decisions; prepare/review again against the final frozen source. |
| Strict complete-loan history | Committed baseline | Use only after source-contract proof; likely a subset. |
| Reviewed active-opening import and servicing | 6,273 openings reconciled; full settlement and coupled reversal rehearsed | Final-source preparation and cutover reconciliation; ordinary partial repayments remain guarded. |
| Closed-loan evidence archive | 39,133 records reconciled in accepted and clean-target rehearsals | Preserve final-source coverage and add authorized media attachments. |
| Source-dump preview | Versioned profiles and owner exceptions cover the accepted snapshot | Re-extract a fresh final snapshot; old approvals do not approve changed data. |
| Export | Partial Party and specific Loans contracts | It is not a complete Workspace backup or full-database export. |
| Production operator workflow | Snapshot-bound package/replay/verify command proven in a clean target | Complete media attachments, production access/setup and final frozen cutover. A Migration Center UI is not required. |
| Legacy media | 32,554 inventoried files/candidates preserved and hash-verified in private R2 | Attach verified originals through application services; resolve missing-file/candidate evidence and recheck the final snapshot. |

## Next recommended action

The three-Workspace discovery, admission, exception resolution and browser review
are complete for the September 21 snapshot. The owner accepted the presented
rehearsal. See the [final admission record](../implementation/linode-owner-decisions-20260921.md)
and [browser access guide](../flows/linode-rehearsal-access.md): 6,273 operational
loans, 39,133 closed evidence records and one cancelled source entry account for
all 45,407 source loan IDs, with no unresolved loan holds in that snapshot.

The snapshot-bound cutover package and clean-target replay/reconciliation are
complete for the accepted snapshot. Media preservation in private R2 is also
complete for the inventoried files. Next attach verified originals to the imported
Party, collateral and closed-history identities, preserving originals separately
from mutable application copies and retaining missing-file exceptions. Configure
production access and valid current lending setup, and verify the branch workflows
required at go-live. Ordinary partial repayment remains
unsupported for imported openings; review acceptance does not remove that guard.

Only after those readiness checks, schedule the legacy write freeze and obtain a
fresh complete database/media snapshot. Re-extract and reclassify that snapshot:
new customers, loans, payments or releases can change the prepared decisions and
totals. Reconcile and accept the final target before switching users. Keep the old
system read-only for recovery; after new-system writes, fallback requires explicit
reconciliation rather than simply reopening the old app. A new Migration Center
UI is not a prerequisite for this bounded initial conversion.

## Migration Center: first-time user experience

Migration should be an owner-only guided operation, not an ordinary file-import
screen.

1. **Choose a starting point.** Offer "Start with today's register", "Bring over
   an old Rokkad database" and "Bring a simple spreadsheet". A pawnbroker moving
   from physical books can record current open loans through a guided opening
   register without digitizing every historical closed loan.
2. **Show the scope plainly.** Identify source, snapshot date and Workspace, then
   show borrowers, active loans, closed history, records ready and records needing
   a decision.
3. **Review grouped issues.** Explain holds in business language. Allow safe bulk
   changes for labels and mappings only; show money, interest and collateral facts
   one record at a time with their evidence.
4. **Use visible checkpoints.** Show `Snapshot -> People -> Active loans -> Preserve
   history -> Reconcile -> Go live`, a saved report and a clear resume point. Users
   should never need raw JSON, schema names or database commands.
5. **Make the final switch explicit.** State cutover time, active-loan total,
   held-record total and responsible owner. Keep "Go live" unavailable until the
   reconciliation report is accepted.

For the initial Linode conversion, the technical team prepares the signed snapshot
and adapters. Workspace owners review business facts and authorize admissions.
