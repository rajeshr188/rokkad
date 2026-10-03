---
status: complete
owner: project
updated: 2026-09-30
tags: [fw-015, storage, cleanup, operator, recovery]
---

# Reviewed media cleanup: operator runbook

`manage.py cleanup_storage` provides a bounded offline maintenance workflow.
It does not add a delete button to Workspace or platform pages. Storage pricing,
quotas and billing remain deferred; no customer is charged by this workflow.

## Available release and evidence

As of the statutory release on 30 September, the operator is
`rokkad:storage-cleanup-20260930-b8fe1096e0f4`, based on
`rokkad:statutory-notices-20260930-76e120aeb6a3`. Both new statutory FileFields
are covered; read-only candidate discovery passed and no cleanup executed.
The following category-release details retain the earlier checkpoint.

The new server retains the operator image
`rokkad:storage-cleanup-20260930-5023e640932a`, rebased on the current production image
`rokkad:storage-category-20260930-625feb7250e4` with two additive command/service files.
The initial operator delivery did not replace the web container; the subsequent
category correction updated web and rebased these unchanged operator files.
There are no schema migrations. The rebased read-only candidate check passed
against inventory 4 with no candidates; original provider acceptance below remains
the evidence for the unchanged cleanup adapter.

Private build, source hashes and provider acceptance evidence are under
`/home/rokkad/deploy/cutover-20260924/storage-cleanup-20260930/`.
`run_cleanup.py` launches the operator image with the live runtime configuration,
restricted database role and a dedicated private evidence mount. Its base-image
check refuses a changed live release; rebuild/review this operator image whenever
the production models/reference registry change. Transfer env files are temporary
0600 files, removed after each invocation. Do not copy runtime env or checkpoints
into the repository, OneDrive or support messages.

Thirty new cleanup tests and nineteen storage/retention regressions passed; the
architecture-boundary check also passed (50 total). Tests cover all phases,
restricted role and authorization, inactive Workspace and historical/global
references, changed objects, corrupt/missing backups, digest tampering, bounds,
interrupted upload/delete/restore, audit/checkpoint failures, occupied keys and
deletion replay. A second PostgreSQL connection confirmed that reference writes
cannot obtain their lock during execution, and another storage job cannot acquire
the shared advisory lock.

Real R2 acceptance used two freshly generated synthetic objects in isolated
application/recovery prefixes. Conditional GET and create-only PUT both rejected
conflicting requests; backup readback, exact deletion and restoration of bytes and
metadata passed. Both synthetic objects were removed afterwards. These transport
checks used no customer content and made no business database writes. End-to-end
workflow failure tests use the isolated test database and deterministic test storage;
no production deletion was performed to test the workflow.

The installed launcher's initial read-only candidate query returned no candidates
in production inventory 3. This is an inventory observation, not permission to
broaden the scope. The separate rehearsal recovery archives remain untouched.

## Preparation and review

Run commands on the server as its authorized operator, using runtime settings,
never the migration owner. The actor must be an active platform administrator.
Use a dedicated existing directory with mode 0700, outside the application tree
and media directory; no symlink traversal. The launcher creates this directory
under its private `runs/` directory and mounts it at `/cleanup-private`.

Examples below use a unique run name `review-001` and the current platform operator
ID 9. IDs and digest are examples to replace with reviewed values.

```sh
cd /home/rokkad/deploy/cutover-20260924/storage-cleanup-20260930
python3 run_cleanup.py review-001 candidates --actor-id 9
```

This reports at most 50 candidate IDs, fingerprints and sizes. Use `--after-id` for
another page. Refresh the normal inventory first if it is older than 24 hours.
Resolve any missing references or unknown retention obligations before selection.

```sh
python3 run_cleanup.py review-001 plan --actor-id 9 \
  --inventory-id 123 --object-ids 456 457 \
  --reason 'Reviewed these exact detached files; no remaining retention obligation'
python3 run_cleanup.py review-001 inspect --actor-id 9 --private-details
```

`plan` writes signed private evidence but changes no objects. The private inspection
shows exact relative keys, sizes, timestamps, ETags, reason and recovery state.
Only use `--private-details` in a secure terminal; default output omits filenames.
The JSON values identify the reviewed plan; never treat the inventory list itself
as an approved deletion manifest. Bounds: 1–50 objects, 20 MiB per object and
64 MiB per batch. Recent files and files with unknown age are ineligible.

```sh
python3 run_cleanup.py review-001 prepare --actor-id 9
python3 run_cleanup.py review-001 inspect --actor-id 9 --private-details
```

Preparation rechecks references and source metadata, copies each exact object into
private R2 recovery storage, and verifies its full SHA256 readback. A signed recovery
manifest records original names and metadata. No originals are deleted. Approve
the digest printed **after preparation**, which includes the verified recovery
hashes. Retention is indefinite with no automatic expiry; storage is retained in
recovery even after loose originals are removed.

## Execute only during stopped-writers maintenance

Arrange a maintenance window before execution. Stop/drain all web upload paths,
workers, importers, scheduled scripts and any external object writers for this
deployment. Keep PostgreSQL running. A stopped web process alone is insufficient.
The command acknowledges this operational fact; it cannot discover every external
credential. The current launcher expects the web container to exist for configuration
inspection, so stop rather than remove that container during maintenance.

```sh
python3 run_cleanup.py review-001 execute --actor-id 9 \
  --approve-digest PREPARED_DIGEST \
  --writers-stopped rokkad-production-media/media/application/production/linode-rls/
```

The command acquires database reference-table locks without waiting. Existing
conflicting writers cause it to stop before deletion. New row writers block while
it runs; web/workers must already be stopped so this is not an online cleanup.
It rechecks all references, all recovery copies and all source metadata before
starting, and rechecks the exact source immediately before each deletion. A
changed source, new reference, missing recovery or unknown provider result stops
the batch. No wildcard or other deployment prefix is accepted.

The private `state.json` records each actor, intent, outcome and time independently
of the database transaction. Keep it and all recovery objects after any failure.
`inspect` reports progress. Once the cause is resolved and writers are stopped,
repeat `execute` with the **same directory and digest**. It reconciles a lost
response with actual source/recovery state; it does not blindly delete again.
Do not edit/re-sign a failed plan or recreate it to bypass a refusal.

## Restore and verify

Use the same stopped-writers window and approved manifest:

```sh
python3 run_cleanup.py review-001 restore --actor-id 9 \
  --approve-digest PREPARED_DIGEST \
  --writers-stopped rokkad-production-media/media/application/production/linode-rls/
```

Restoration checks recovery bytes, writes only absent original keys and verifies
the restored bytes. It preserves content type, disposition, encoding, language,
cache policy, expiry and custom metadata. An occupied key is never overwritten;
matching originals that were never deleted, or matching writes from an interrupted
restore, are reconciled. It restores files, not removed application attachment rows.
After restoration begins, that plan cannot execute deletion again. A later cleanup
requires new inventory/review. Recovery copies remain intact after restoration.

After completion, restart the paused writers and run the usual reconciliation.
Review missing-reference counts and scoped totals; the UI updates from that complete
inventory. Record loose bytes removed separately from bytes retained in recovery.
Do not install a bucket lifecycle rule to expire these packages.

For loss of the private server checkpoint, retain the independent R2 manifest and
copies, plus signing-key recovery from the application's private backups. Review
actual destination state before a separately controlled restore; do not guess an
execution journal or resume deletion from an old prepared manifest. This initial
command does not automate recovery from loss of its local journal.

## Limits and later work

Offline cleanup is implemented and available to authorized operators. Online
writer coordination, an interactive approval queue, scheduled cleanup and archive
expiry are not implemented. Pricing, quotas, metering for invoices and storage
billing need a separate commercial policy and explicit future selection. See
[FW-015](../plans/future-work.md#fw-015-safe-orphan-media-cleanup-and-workspace-storage-usage).
