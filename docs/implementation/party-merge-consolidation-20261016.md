---
status: deployed
owner: project
updated: 2026-10-16
tags: [party, loans, merge, repair, production]
related: [../adr/2026-10-16-party-merge-loan-consolidation.md]
---

# Party merge loan consolidation and historical repair

The old merge moved Party profile children and archived the duplicate, leaving
ordinary loans and Khata accounts attached to that archived identity. The Loans
tab filtered directly by borrower and therefore omitted those agreements from
the retained Party.

The retained detail-page Party now receives all current borrower links in the
same transaction as the profile merge. Each loan/account remains separate with
its original number, terms, financial actions, balances, custody and issued files.
The success message includes ordinary-loan and Khata counts. Existing Workspace,
Party edit, commercial/lifecycle, confirmation and identifier-conflict checks
remain authoritative. New merges reject archived inputs.

Ordinary agreements append immutable `BORROWER_CORRECTED` evidence marked as a
same-person Party merge. A borrower-only Django save preserves every other loan
field and runs existing monitoring invalidation. Historical approval/opening
identities resolve through the complete correction chain. A later approval may
start after an initial sequence of same-person merges; mistaken-borrower
corrections retain their stricter original-identity checks. Previously issued
document bytes are unchanged. New notices still require current identity/consent
and valid transaction review; old reminder intent is not transferred automatically.

Khata changes only its borrower field and appends a per-account actor AuditLog.
Loans 0082 narrowly extends the existing Khata and imported-closed-position
guards and retains immutable correction/merge audit. All financial/custody guards
remain. There is no new table, RLS registry entry or financial posting.

Loans 0084 protects new/changed borrower links with a Party key-share lock and a
merged-identity check. This closes the deferred-FK race between loan admission
and the merge's Party update locks. An admission committing first is transferred;
an admission waiting behind the merge must select the retained customer. The
guard covers ordinary loans and Khata and preserves existing financial updates
with an unchanged borrower. Two real PostgreSQL race tests cover both orders;
stale instance/direct SQL checks also verify rejection and unchanged Khata numbering.

## Historical repair

The explicit command defaults to a rolled-back preview:

```powershell
python manage.py repair_party_merge_accounts --workspace-id WORKSPACE_ID --actor-id ACTOR_ID
python manage.py repair_party_merge_accounts --workspace-id WORKSPACE_ID --actor-id ACTOR_ID --commit
```

Use restricted runtime settings, not migration credentials, for the repair.
The command requires the actor's existing Party edit permission in that explicit
Workspace. It checks reciprocal retained merge metadata and an archived source,
rejects missing/foreign/cyclic/chained destinations needing review, and moves only
remaining links. Repeating a completed repair creates no additional correction
or move. Names, phones and import source aliases never determine a destination.

Bounded cross-Workspace servicing bundles refuse merged histories until a
versioned merge-remapping contract exists. Exact database/Workspace recovery
retains the original Party identities and complete evidence. Ordinary loan Excel
reports are not this bounded servicing format.

## Validation and release scope

The final isolated candidate passes **166 tests** in 94.537 seconds. They cover
ordinary draft/approved/active/closed/cancelled loans, imported closed positions
under a restricted role, active Khata balances/custody/source operations,
correction-chain reads, monitoring invalidation, permission/Workspace boundaries,
rollback, idempotence, existing borrower-correction workflows, native recovery,
terminal/compact closed evidence, both admission race orders and the merge HTTP action. These counts overlap
earlier runs and are not added together. Import boundaries and scoped whitespace
checks pass; source verification includes the new modules.

The candidate is the verified deployed baseline
`b029d4a52771cb3355c4509ee6b7033f0e8c1186` plus ten scoped runtime files, with source
overlay SHA-256 `0bada518f1b3d7c6d8976eb363d673f737371df5508295616b843639d9d02724`.
The final image is `rokkad:party-merge-guard-20261016-0bada518f1b3`, image ID
`sha256:9783ad750ce0850379f9b47b16f7a3bd1f589a6a787d75ded2d909640e304468`.
This is an isolated source overlay, not a claim that the dirty checkout was
committed or that a full CI run occurred. The candidate excludes all unrelated
local financial/collateral corrections. Loans 0082 branches from deployed 0077
and 0084 depends on 0082. Local 0083/0085 no-ops join the pending agreement branch
and are excluded here.
Existing static assets and runtime configuration are reused.

Aggregate production inspection identifies one incomplete merge with one ordinary
loan, no Khata accounts and no chains. Customer/loan identifiers remain on the
private server. A private production copy restores **1,099,358 rows in 222 tables**.
The migration preserves original rows. Preview rolls back exactly; committed
rehearsal moves one loan, confirms a second attempt is a no-op, preserves the
affected agreement's fields except borrower and all financial/collateral evidence,
and renders the retained Party's loan history. Comparison of **214 preserved
table projections** allows only borrower changes, appended audit and derived
monitoring state in the excluded projections. Issued document rows stay exact.

The final monitoring save-path refinement is separately checked against restored
real agreements in a fully rolled-back merge, followed by complete row comparison.
The additive admission guard reuses this verified restore, preserves all **219
original business table projections**, and repeats the rolled-back merge over
eight real agreements with one monitoring snapshot invalidated inside the rollback.
The nine existing runtime file hashes are identical in the guard follow-up;
only migration 0084 is added.
Independent encrypted application-image download, local-key decryption, checksum
verification and exact image reload pass. The private key stays local, and
temporary plaintext application archives are removed.

## Production result

The initial consolidation/repair is deployed at **16 October 2026, 06:28:31 IST**
from `rokkad:party-merge-20261016-89e3f658522d`. Owner migration 0082 and the
restricted-role repair move exactly **one loan from one retained historical merge**.
The affected loan changes only its borrower; its financial source rows and balances
stay exact. The retained Party's Loans page renders. A second repair attempt moves zero.
Native/closed financial readers, ordinary Excel/Party previews, commercial/grace
and release contracts pass. No financial posting or operator message is created.

The additive guard is deployed at **06:48:21 IST** as the final image above, with
only owner migration 0084. It performs no further customer/account data change.
Both phases take fresh private checkpoints and coordinate compatible web,
monitoring and four scheduled readers. Full-table
comparisons run on the disposable copy, avoiding repeated million-row scans while
the live app is stopped. Live repair acceptance compares the affected aggregate
inside its transaction. No customer database is restored over production.
Measured write-pause/switch durations are 207.433 and 126.810 seconds.

Independent final health verification confirms ten scoped source files on both
readers, effective restricted database roles, no pending migrations, six active
timers, working public HTTPS and zero new reader error lines. A separate read-only
scan finds **zero remaining affected merges, loans or Khata accounts**, with no
invalid targets or chains. Production settings, environment and static assets
are preserved. All customer identifiers and detailed repair proofs stay private
on the server.

The first-phase encrypted pre/post backup and retention/download checks pass.
The verified first-phase post-backup is reused as the guard's pre-backup, alongside
its fresh write-pause checkpoint. Final encrypted post-backup
`production-20261016T011932Z.dump`, SHA-256
`0cceb02e25bf79af27ca966f028eb6d6cf380113874059170bc1a643064fe832`,
passes remote download and retention verification with no low-space warning.
The original initial pre-backup is `production-20261016T005025Z.dump` and the
verified first-phase post-backup is `production-20261016T005919Z.dump`.
Both exact application images have independent encrypted recovery verification.
The disposable database and local synthetic test databases are removed; temporary
task settings/environment files are removed. Checkpoints, detailed server-private
repair evidence and recovery images remain retained. Current production rows are
never restored or deleted by cleanup. The work is complete.
