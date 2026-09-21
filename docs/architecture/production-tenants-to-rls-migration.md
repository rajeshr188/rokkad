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
| Party CSV/JSONL/XLSX bundles, preview, approval and export | Baseline plus verified three-Workspace local rehearsal | Resolve retained review facts and rerun against final frozen source. |
| Strict complete-loan history | Committed baseline | Use only after source-contract proof; likely a subset. |
| Reviewed active-opening import and servicing | Committed baseline | Establish each Workspace's financial rules and opening evidence; add final-snapshot reconciliation and cutover evidence. |
| Closed-loan evidence archive | Committed baseline | Cover actual source variations and run a deployment rehearsal. |
| Source-dump preview | Three versioned source profiles and classified discovery snapshot | Build reviewed loan evidence and production orchestration from the proven runbook. |
| Export | Partial Party and specific Loans contracts | It is not a complete Workspace backup or full-database export. |
| Production operator workflow | Not ready | Build the Migration Center after adapters and runbook are proven. |

## Next recommended action

Discovery and the isolated Party rehearsal are complete; see the
[verified rehearsal record](../implementation/linode-party-rehearsal-20260921.md).
Prepare source-bound opening evidence for the 6,464 unreleased candidates, with
separate review of the 14 payment-bearing loans and all borrower/source errors.
Map licences, series, policy and custody per Workspace. Establish principal,
unpaid interest and fees from evidence before operational loan admission; previous
JCL interest assumptions do not automatically apply to JSK or Lakshmi.

Preserve the 38,943 released source loans through reviewed historical evidence.
Resolve Party review facts, obtain the media inventory and rehearse loan servicing
before scheduling the final write freeze and full-snapshot cutover. Classification
alone does not authorize a loan or archive write.

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
