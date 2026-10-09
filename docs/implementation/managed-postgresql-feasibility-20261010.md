---
status: reviewed-awaiting-provider-test
owner: operations
updated: 2026-10-10
tags: [postgresql, hosting, rls, recovery]
---

# Managed PostgreSQL feasibility baseline

The owner selects a managed PostgreSQL evaluation alongside independent R2 backup
work. No new paid cluster is provisioned and no live connection or schema changes.
Compatibility is not yet proven. This is a separate deployment evaluation, not a
loan-domain redesign or substitute for independent backups.

## Current measured requirements

Read-only production catalogue inspection finds PostgreSQL 16.15, approximately
1.24 GiB of production database storage, 143 forced-RLS tables, 167 custom triggers
and three stored generated columns. Only the built-in plpgsql extension is installed.
The server limit is 100 connections; a single instantaneous connection count is
not workload sizing or a reason to select the cheapest managed plan.

The runtime has no superuser, BYPASSRLS, role-creation or database-creation privilege.
The current migration/bootstrap role has all four. Separate these operational
needs: routine Django migrations need schema ownership and DDL, whereas a complete
cross-Workspace pg_dump/restore must be able to read/restore all protected rows.
Forced RLS must not be disabled merely to make managed backup permissions work.

Aiven documents that its administrative user can create databases/roles/extensions
and manage grants, but does not offer unrestricted superuser access. Akamai is
powered by Aiven; its actual exposed privileges must be tested rather than inferred
to match every direct Aiven feature. See [DBA capabilities](https://aiven.io/docs/products/postgresql/concepts/dba-tasks-pg)
and [Akamai managed clusters](https://techdocs.akamai.com/cloud-computing/docs/aiven-database-clusters).

## Required provider acceptance

| Boundary | Required result | Current evidence |
| --- | --- | --- |
| Version | Supported target version; full restore and SQL behavior compatible with current PostgreSQL 16 | Local version measured; provider restore untested |
| Runtime role | Restricted login, no ownership or elevated-role membership; exact startup checks pass | Existing role measured; provider provisioning untested |
| Owner operations | Schema ownership, migrations, functions/triggers, grants/default grants and isolated restore work | Existing scripts reviewed; provider privileges untested |
| Global backup | Complete cross-Workspace logical backup and restore without weakening forced RLS | Critical unresolved provider capability |
| Isolation | No-context, cross-Workspace DML and constraint boundaries fail correctly under runtime login | Existing native tests; provider run pending |
| Financial evidence | Immutable triggers, deferred constraints, row locking and idempotent posting retain behavior | Existing system rules; provider test pending |
| Connectivity | Verified TLS, allowlisted/private same-region connectivity; connections recover after maintenance/failover | Provider configuration and test pending |
| Pooling | Transaction-local Workspace context cannot leak across reused connections | Preserve current connection semantics first; pool test if selected |
| Recovery | Actual provider PITR and independent R2 restoration preserve all data and source/media references | Provider acceptance pending |
| Performance/cost | Representative queries and real peak connections guide plan/node count | No sizing commitment or performance claim |

The existing Linode browser inventory shows an active `postgres-jsk` cluster with
three nodes in Chennai and PostgreSQL v18.6. Its purpose and spare capacity are
not established. Do not repurpose it, add Rokkad data, change roles, expose credentials
or treat it as a disposable test environment. Version 18 would introduce a version
upgrade as well as a hosting migration, requiring explicit test acceptance.

Current Akamai overview documentation specifies 14-day backup retention and PITR.
Some API documentation still describes seven retained backups. Confirm actual
plan/console restore coverage before selecting a policy. Neither automatically
matches Rokkad's independent 24-hourly/30-UTC-daily recovery requirement.

## Recommended next step

Complete [BS-03/04](../plans/backup-storage-and-evidence-efficiency.md) first or in
parallel. Then select a dedicated temporary provider test environment and explicit
budget before provisioning. Start with fictional role/RLS/trigger/backup fixtures;
only then use an authorized isolated encrypted production-derived restore, with
outbound messaging and payments disabled. Execute native acceptance, source hashes,
all closed/held cohorts and representative performance checks under the restricted
role. Schedule a separately reviewed reversible cutover only after those pass.

Do not promise that database hosting fixes broad-search latency or repeated source
JSON. Those require their own measured query/storage work. Retain independently
recoverable encrypted backups after any managed migration.

References: [runtime provisioning](../../scripts/provision_runtime_role.py),
[migration settings](../../django_project/settings/migration.py),
[independent recovery decision](../adr/2026-10-10-independent-encrypted-database-backups.md),
[managed pricing](https://www.akamai.com/cloud/pricing/databases).
