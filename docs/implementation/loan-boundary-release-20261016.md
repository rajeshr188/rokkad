---
status: deployed
owner: project
updated: 2026-10-16
tags: [loans, monitoring, release, verification]
related: [../plans/loan-boundary-release-20261016.md, loan-boundary-ls06-20261016.md]
---

# Combined Loans release preparation

The owner requested coordinated release preparation and explicitly selected a
combined candidate containing the committed collateral/agreement corrections plus
LS-01 through LS-06. Production deployment remains separate.

## Exact candidate

- Source parent: `7681aac0` (committed corrections and deployed Party integration).
- Runtime delta: **99 files** (73 changed/26 new), including compatible financial/collateral readers,
  correction services/guards, portable V6/V7 readers, shared completed-payout
  review, V11 monitoring and the policy lock fix.
- Candidate source identity:
  `21391df87683feadf0fef3f16b0cde4b59c2060b8c3b7ae744fb38ca775f49ef`.
- Built image tag: `rokkad:loans-boundary-20261016-21391df87683`.
  Exact ID: `sha256:82b9e9065ad9639ecd90f70530b1c2175eeb7d46a51b73b112c09c78a7268b66`.
  All 99 runtime files verify. It is **deployed after the owner's subsequent authorization**.
- Exact base image:
  `sha256:9783ad750ce0850379f9b47b16f7a3bd1f589a6a787d75ded2d909640e304468`.
- File-level source/archive hashes and expected live baseline hashes are in the
  [source-only manifest](loan-boundary-release-20261016.manifest.json).

The snapshot is prepared from committed HEAD plus reviewed LS modifications/new
source. Unrelated WhatsApp setup notes are explicitly excluded. The outgoing
archive contains only the enumerated runtime delta; no customer records, source
documents, production settings, credentials, recovery key or environment files.
The complete local test snapshot includes fictional tests and remains ignored in
`.tmp/loan-boundary-release-20261016/source`. It is separate from the outgoing
99-file archive (1,290,240 bytes, approximately 1.23 MiB). No Git commit/push is
performed by preparation.

## Read-only production preflight

The scoped metadata check confirms both running readers match the exact expected
base image and **zero mismatches across all 99 baseline file expectations**. Both
use the restricted runtime, with no migration credentials in their environment.
Production still uses `LOAN_RISK_SNAPSHOT_V9`. Public login HTTPS responds; all six
known timers are active. Free capacity at the check is **10.556 GiB**. Remote-backup
and retention completion markers exist and were approximately 11/10 minutes old.
Marker recency is not a new restore/recovery test. No customer rows or credentials
are returned. Production services, policies and data remain unchanged.

## Local compatibility and migration plan

Frozen runtime hashes, import boundaries, Django system/model checks and V11
identity pass. The exact live Loans/portability migration ledger is simulated
against the candidate's graph locally, producing these ten pending steps:

1. `loans.0078_collateral_fact_corrections`
2. `loans.0079_agreement_financial_corrections`
3. `data_portability.0028_collateral_correction_profile`
4. `data_portability.0029_agreement_correction_profile`
5. `loans.0086_monitoring_policy_lock_mode`
6. `loans.0080_opening_checkpoint_corrections`
7. `loans.0081_agreement_notice_identity`
8. `loans.0083_merge_party_and_agreement_corrections`
9. `loans.0085_merge_party_guard_and_agreement`
10. `loans.0087_merge_monitoring_policy_lock`

The three joins have no operations. There is no pending Party, control-plane or
WhatsApp migration. This is a **local graph simulation**, not an owner migration
or production-copy rehearsal. At that local-only stage the live database is not migrated.

The isolated schema confirms that 0079's non-null accrual `agreement_revision`
has no database default. Consequently the old image cannot safely resume ordinary
accrual writes after upgrade. Correction evidence and V6/V7 exports also impose
compatible-reader requirements. Coordinate web, monitoring and scheduled readers;
retain a recovered compatible image and forward-fix with writes stopped as needed.
Do not promise an automatic rollback to the previous writer or restore over later
transactions. The [plan](../plans/loan-boundary-release-20261016.md) records the
static-asset, backup, preservation and cutover gates.

## Frozen-source verification

The dedicated fictional database is `test_rokkad_ls_release_20261016`. The runner
loads the frozen candidate, verifies the import root and uses isolated local media.
The selected 566-case regression covers common and earlier payout, native/paper/
opening agreement and collateral corrections, portable round trips, documents,
Party merge, monitoring time/inputs/presentation, book reviews, financial servicing,
closed positions and two targeted desktop/mobile browser checks.

The broad run finishes in **901.633 seconds**: **564 pass**, with two errors from
the same inherited first-appraisal fixture. That fixture globally replaces
`timezone.localdate`, including conversion of a supplied historical instant,
making a January 21 cutoff appear to be February 2. The new aware-cutoff guard
correctly refuses that inconsistent test clock. Freeze `timezone.now` instead;
retain actual historical date conversion. This changes only
[the test fixture](../../apps/tenant_apps/loans/tests/test_opening_restore.py),
not production validation, financial arithmetic or the outgoing archive.

Both complete affected classes pass the final **56-case follow-up in 89.556
seconds**, including both previously failing executions, opening/servicing
restore, old profiles, first/current appraisals, remaining interest and documents.
The runtime identity and all 99 hashes remain exact. The selections overlap and
are not added together; the entire 566-case selection is not rerun after this
test-only correction. No selected application failure remains unresolved.

**Fourteen desktop/phone states pass** at 1365/390 pixels. Representative phone
completed-payout review and desktop portfolio captures are visually inspected.
Copies and capture hashes are retained in the private ignored release folder.
Browser traffic is intercepted and all data is fictional. Source/archive/import,
Django/model and simulated migration checks pass; documentation/whitespace checks
pass. The exact isolated database is removed, absence checked and measurement-role
cleanup verified. Logs, the fixture-follow-up proof and immutable runtime artifact
are retained for review. Ordinary development and production data are unchanged.

## Server preparation authorization and progress

After the initial automatic-review rejection, the owner explicitly approves the
explained source-only transfer, separate server build, isolated database rehearsal
and encrypted-image recovery test by replying "ok proceed". The newly authorized
execution passes approval review. This does not authorize a production switch.

The source-only archive is staged and the separate image is built. The first build
attempt mistakes the local image ID for a registry reference; using the installed
base tag after verifying its exact ID fixes the helper without changing candidate
source. The isolated production dump restores successfully and all original table
fingerprints match. The initial baseline screen check lacks its static mount;
resume with the old static volume read-only. Candidate source remains unchanged.
The resumed migration/restricted-reader and bounded monitoring rehearsal passes.
Its rollback wrapper initially marks the Workspace context rollback-only before
that context's cleanup query. Remove that outer marker; each experiment already
has its own rolled-back savepoint. This is a rehearsal-helper fix, not an
application change. Candidate source/archive hashes remain unchanged throughout.

## Completed server acceptance

The full restore verifies **222 tables and 1,099,616 rows** against the dump.
After the ten expected migrations, **219 original business-table projections**
still match; only the three framework migration/content-type/permission tables
are excluded from that comparison. New required accrual revisions are one, with
no database default. No actual loan agreement is corrected by migration.

Restricted readers render **23 screen checks** and compare **14 real loan
samples** with the baseline reader. All sampled collection balances match across
four contract profiles: closed position, native event fold, original anniversary
and recorded anniversary. Direct and paper entry, current Loan health, imported/
opening and closed detail/source/list readers pass. Cross-Workspace DML affects
zero rows. This is server-side rendering, separate from the earlier fourteen
fictional desktop/phone browser states.

Rollback-only experiments exercise **two agreement corrections and two collateral
corrections**, covering direct and paper loans, original-event preservation and
idempotent retries. A subsequent full business-table comparison still matches.
The unchanged deployed Party-merge code is retained by the exact pinned base;
its earlier production-copy acceptance is reused, with Party merge and portable
round trips also covered in the frozen-source local regression. This rehearsal
does not create a new Party merge or import a portable customer package.

The bounded worker refreshes **ten loans per Workspace, thirty total**, under V11
with **zero errors**. The **216 source-table projections** still match afterward;
only the three derived risk snapshot/event/alert tables may change. All thirty
selected loans retain unavailable collateral coverage, with no invented value or
LTV. These are current calculations with incomplete evidence, not evidence cures
or complete-coverage claims. No Workspace monitoring policy is changed.

The exact candidate is preserved in the existing private backup bucket as a
**228,005,913-byte encrypted application image**. Verified remote download, local
decryption using the protected recovery key, and successful Docker loading pass.
The exact candidate image ID matches. The key never goes to the server; temporary
plaintext image copies are removed on both computers. Database/customer data do
not leave the server.

Candidate static assets and manifest verify in the separate volume
`rokkad-ls-static-20261016-21391df87683`; the existing static bytes are unchanged.
Private compose and four scheduled-reader configurations validate without being
installed. New mail overrides are checked to sort after existing overrides.
Resource limits, worker Workspace scope, access grants, credentials and disabled
WhatsApp activation are preserved. Protected configuration hashes remain exact.

The exact disposable database, dump and temporary settings/environment/image
files are removed; database absence is verified. Candidate image/static assets,
encrypted off-server recovery and private audit proofs remain. Final production
checks at preparation completion show the old image and V9, zero source mismatches on both readers,
restricted roles, HTTPS login, six active timers and **10.515 GiB free**.

The [aggregate acceptance record](loan-boundary-release-20261016.acceptance.json)
contains these preparation-phase proofs without customer rows or private
configuration. At that point no Git commit/push, live migration, financial
correction, policy change or production switch has occurred.

## Production deployment (16 October)

After completed preparation is reported and coordinated production deployment is
identified as the next separately authorized action, the owner replies "proceed".
That authorizes the production switch. The live baseline still matches, and a
fresh encrypted pre-backup passes remote-download and retention checks.

A host-managed deployment service pauses all six timers, drains their services,
stops web/monitoring and verifies zero remaining restricted-runtime connections.
Fourteen representative balances are captured read-only. A stopped-writer custom
dump is catalog/checksum checked, encrypted with deployment configuration and
uploaded to the existing private backup bucket's separate release prefix; remote
download and completion readback verify before any migration starts. The recovery
key stays off-server. The encrypted release checkpoint has no ordinary expiry.

Exactly the rehearsed ten owner-only migrations apply in **16.356 seconds**.
All fourteen sampled balances still match across the four contract profiles.
Restricted startup/model checks pass and owner-role web startup is correctly
refused. Existing access grants and disabled WhatsApp activation remain intact.
No loan correction, collection, payout or monitoring-policy change is performed.

The prepared web, continuous worker, separate static volume and four scheduled
readers are installed together. Runtime environments, process commands, resource
limits, mounts apart from the intended static volume, UID 10001 and protected
configuration hashes match. Scheduled command checks use `--help`, not delivery.
All six timers resume. The entire coordinated sequence is **213.788 seconds**;
the exact public outage duration is not independently measured.

Independent production checks verify **99 files on each of the two live readers**,
V11, restricted roles, zero pending migrations, four public HTTPS pages, zero new
reader error lines and the publicly served hashed candidate JavaScript. An
isolated restricted-role, read-only smoke renders **23 screens / 14 loan samples**
covering direct, paper, imported/opening and closed loans. The new worker makes
positive successful refreshes in **all three Workspaces**, with **zero observed
assessment errors**. It continues normal bounded catch-up; this does not cure
missing valuation evidence or certify paper-book completeness.

The new-image post-backup passes encrypted remote-download verification and the
established retention checks. Backup recovery acceptance and release metadata
point to the verified compatible image. After both backups and health checks pass,
only this release's redundant plaintext stopped-writer dump and temporary runtime
environment are removed. Encrypted release recovery and audit proofs remain.
Final login HTTPS, both live readers, protected configuration and all six timers
pass; **10.506 GiB** remains free.

See the [sanitized deployment proof](loan-boundary-release-20261016.deployment.json).
Application source/archive identity remains `21391df87683`; no additional
application change, Git commit or push is made during deployment. The old writer
remains unsafe after 0079: use compatible forward recovery, never automatically
restore a database over later legitimate transactions.
