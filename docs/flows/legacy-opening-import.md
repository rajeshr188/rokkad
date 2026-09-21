---
status: active
owner: project
updated: 2026-09-12
tags: [loans, portability, migration, approval]
---

# Review and import one prepared legacy opening

For an explicitly authorized larger rehearsal, operators may call `stage_many`
with up to 20 reviewed `review`/`setup` pairs. It extracts the archive once for
that group, preserves every per-loan source check, and creates ordinary individual
review batches. Each batch still needs its signed preview and confirmed commit;
the existing limit of 20 unfinished batches applies. Hold failed records, preserve
completed source identities, and reconcile counts and balances after admission.
This helper does not supply missing financial facts or authorize a live migration.

For current valuations based on business metal prices, the operator can use the
ordinary Loans **Rate-based appraisal** command after import, with a reviewed
current quote, recorded net weight/purity, exact calculated value and current
effective date. It appends an appraisal rather than rewriting an old source value
or historical financial policy. The C00121 pilot demonstrates this composition;
automation across the remaining cohort is not yet wired into bulk import.

For new preparations, explicitly supply the readable destination loan number in
`setup.local_loan_number` (normally the source number). Review collisions and
future series ranges before staging. Older prepared inputs remain valid, including
their original generated-number semantics. Source identity is separate.

After commit, inspect the normal loan list/detail and collection quote, not just
the completed batch. Opening details guide full collection/release, show original
maturity/grace and explain which earlier history is unavailable. Prepare destination
monitoring separately; missing appraisal evidence remains visibly unknown. Rehearse
settlement, concession, receipt and reversal before bulk rollout.


This is the first `jcl` dump adapter, for a small reviewed active-loan rehearsal.
The existing complete-history upload stays separate. The owner does not need to
write JSON, recreate old receipts or learn the technical source format.

1. The migration operator prepares one v2 opening review from the bounded source
   preview, Party source identities and explicit destination setup. Record the
   agreed cutover, original maturity/tenure, balances, paid coverage, custody and
   dated appraisal evidence. For this owner's jcl source, preserve recorded maturity
   terms. The owner instructed three calendar months from the original loan date
   when maturity is missing. For source tenure 0, prepare setup tenure 3 and the
   matching maturity/obligations, retaining
   `owner-clarifications-2026-09-12:jcl-missing-maturity-three-months` in
   `terms.evidence_reference` (separate references with `; `). Calendar addition
   clamps to the destination month's last day. The bridge verifies the rule and
   freezes its basis alongside unchanged source facts. Invalid source values,
   conflicting known terms and the disputed R07743 loan remain held.
   Missing licence validity may now use the owner-only inactive legacy-reference
   setup with explicit `setup.legacy_license_evidence`. An old undated value uses
   the v2 UNVERIFIED valuation object, creating no appraisal/current LTV. Both gaps
   stay visible in browser review and export. See the
   [evidence-gap decision](../adr/2026-09-12-legacy-opening-unknown-evidence.md).
2. The operator runs `stage_legacy_opening` using the selected dump, owner actor,
   destination Workspace and prepared file. It verifies the exact source snapshot
   and selected loan, runs a rolled-back domain preview and saves only the staged
   review. It prints the Workspace browser review URL.
3. The owner opens **Import Loans → Review prepared legacy loan openings**. Review
   the source number, original dates, balances, interest coverage, every collateral
   item and its custody/appraisal references, plus destination setup.
4. **Validate destination and preview opening** resolves the current borrower and
   setup again. It retains no financial loan rows. Review the destination borrower,
   local historical number and item count. Approval expires after one hour.
5. Explicit confirmation imports exactly that opening atomically. The completed
   page links to the loan. A repeated confirmed request returns the existing result.
   Changing a reviewed source document requires cancellation and a new preparation.

The operator command accepts:

```text
python manage.py stage_legacy_opening --workspace-id <destination-id> --actor-id <owner-id> --dump <archive-path> --opening-file <operator-prepared-file> --pg-restore <pg_restore-path>
```

Run through the restricted runtime settings/role. Owner-only migration settings
are for applying Django schema migrations, not the import command. The prepared
file contains one bounded UTF-8 JSONL record with `profile: loan-opening-commit/1`,
`review` and `setup`; it is the exact input to the existing Loans command. The
operator prepares it from recorded evidence, rather than asking customers to fill
JSON. The staging command accepts no financial commit flag.

Source extraction is read-only: the dump is never restored into the app database.
Staging retains only the selected source graph plus review evidence. Archive and
exclusion hashes identify the snapshot and proposal; the one-loan approval is not
approval to import every retained loan. Customer, licence and series rows are
matched through explicit destination mappings and remain visible as source claims.

Unknown gross weight stays unknown; net weight and purity stay separate and Bronze
stays Bronze. Source payments or changes to principal require another supported
reconciliation path. Current custody is an explicit declaration, not a fabricated
history of vault movements. The original number is preserved in source evidence;
the local historical number consumes no live loan-number counter.

The bridge does not resolve missing business facts automatically. Before the actual
pilot, still complete the selected source/destination/cutover review and a real
reconciled rehearsal. No production import has been performed in this delivery. See the
[staging decision](../adr/2026-09-12-legacy-opening-staging.md).

For C00121, the resulting maturity is 10 January 2025, three months after
10 October 2024. This is the owner's migration instruction, not newly discovered
historical contract evidence. The date affects overdue reporting; it does not
alter anniversary interest or erase later debt. General offline candidate creation
still leaves unreviewed terms/balances empty; operators apply this scoped rule when
preparing the selected loan. Other source tenants and native origination gain no
automatic fallback.


## Download after import

Owners can use **Export loan data JSONL** on the loan detail. For an opening, this
downloads `loan-opening.jsonl`, preserving the reviewed origin, available source
verification and later supported servicing evidence. It records an export audit
without changing debt. Original history before cutover is explicitly unavailable;
recorded balances and unposted collection estimates are separate.

Opening exports can be restored through the dedicated operator path below. The
complete-history browser upload remains separate. See the
[file contract](../contracts/loan-opening-export-v1.md).

## Restore an opening export

The operator selects an existing destination Workspace, source-bound Party, licence
revision, series and compatible product version. The Workspace owner must have the
existing import/setup, export, release and administration permissions. Use the
restricted runtime database role and normal application settings.

Preview one file (replace the placeholders with the reviewed destination IDs):

```powershell
python manage.py restore_loan_opening --workspace-id <workspace> --actor-id <owner> --source <loan-opening.jsonl> --borrower-id <party> --revision-id <licence-revision> --series-id <series> --product-version-id <product-version>
```

The JSON result contains `committed=false`, the exact `sha256` and a summary of
state, source/local number, as-of date, balances, borrower, collateral and event
counts. Preview runs the full restore and reconciliation under rollback; it retains
no business rows or audit records. PostgreSQL identity sequences can advance during
preview, but native loan/release numbering counters do not.

After reviewing that concrete result, repeat the same command with:

```powershell
--commit --expected-sha256 <sha256-from-reviewed-preview>
```

Commit reparses the source, rechecks authorization and mappings under locks,
rebuilds and reconciles the supported graph, and records immutable provenance.
Original actor/time claims remain in the source snapshot; new local rows identify
the restoring operator. Same-input retry is a no-op even after newer servicing.
Changed files/mappings or an already accepted ordinary opening/history fail instead
of overwriting or appending debt. This command does not restore pre-cutover history,
merge snapshots, activate held raw-dump candidates or create missing destination
setup. Older same-format evidence-only exports remain readable.

The next MVP activity is the selected one-loan pilot review and rehearsal. Final
source, destination, cutover and unresolved business facts still require review;
no production import has occurred as part of implementing this command.
