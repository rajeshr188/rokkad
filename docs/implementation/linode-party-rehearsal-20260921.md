---
status: completed-with-holds
owner: project
updated: 2026-09-21
tags: [migration, portability, rehearsal, party]
---

# Linode Party rehearsal: 21 September 2026

## Scope and result

Completed the Party-only local rehearsal from the supplied production discovery
archive using ordinary staged import services under `rokkad_runtime`. No Linode
writes or production cutover occurred. The normal application database, including
earlier `jcl-13` rehearsals, is separate from this database.

Target: `rokkad_baseline_rehearsal_linode_20260921`, settings
`django_project.settings.baseline_rehearsal`, environment
`ROKKAD_REHEARSAL_DB_NAME=rokkad_baseline_rehearsal_linode_20260921`.
The rehearsal operator `migration-rehearsal-owner` has an unusable password.
These records are not automatically visible in the normally running application.

| Workspace ID / slug | Parties | Contacts | Addresses | Held |
| --- | ---: | ---: | ---: | ---: |
| 1 / rehearsal-jcl-20260921 | 5,882 | 1,898 | 3,997 | 0 |
| 2 / rehearsal-jsk-20260921 | 646 | 513 | 611 | 10 |
| 3 / rehearsal-lakshmi-20260921 | 2,102 | 1,085 | 2,104 | 0 |
| Total | 8,630 | 3,496 | 6,712 | 10 |

All 18,848 prepared rows are accounted for: 18,838 committed, ten held. At this
Party-only checkpoint there were zero operational loans or historical-loan
evidence records. Subsequent loan admission is tracked in the
[loan rehearsal record](linode-opening-rehearsal-20260921.md).

## Source and identity

Source archive: `C:\Users\rajes\backup_20260921_095530.sql` (PostgreSQL custom format).
SHA-256: `f50e992a5813571e5d64316534cf073c08a96059780420be47bf7211eab163a6`.
Installation namespace: `6ca968d6-2647-4dbb-8e39-24f0c1a12ed6`.
Profiles: `linode-jcl/1`, `linode-jsk/1`, `linode-lakshmi/1`.

The adapter emits deterministic UUID master IDs and uses those same values in
contact/address `party_external_id`. The original `contact_customer:<pk>` reference
remains in master source provenance. The earlier raw-key parent reference did not
resolve through canonical JSONL staging; the adapter and integration regression
test now cover actual stage, validate, commit, retry and Workspace boundaries.

Import chunks contain at most 1,000 rows. Each completed chunk is independently
committed. Obsolete and duplicate pending attempts were cancelled after matching
their replacements; committed provenance was retained. Completion was checked
against persisted rows, not inferred from an empty command response.

## Retained review facts

JSK source addresses `contact_address:14,15,16,17,30,31,57,58,59,60` remain held in
batch `795519e9-4d8e-428e-be5a-5111c96a03b4`. Entire duplicate groups were retained;
no survivor or merge was inferred. The other 611 JSK addresses were committed in
the eligible batches.

Preparation also retained 187 review items: 180 missing related-person names,
five unsupported relationship labels and two conflicting default flags. Incomplete
relations are omitted from canonical Party fields, with original facts preserved
in source evidence. Proposed first-default choices were used for rehearsal only.
These are unresolved production-review decisions, not silently certified facts.

## Verification

The reconciliation compared every completed raw row to its hashed prepared file,
then checked accepted source digests, current Party fields, child fields, parent
identities and local child digests. Completed and held source IDs form exactly the
prepared source set, without overlap or duplicate completed source IDs.

Every completed batch was retried through `commit_import`; all business counts
remained unchanged. This tests completed-batch retries, not incremental sync or
fresh-upload conflict behavior after local changes. Raw SQL under the restricted,
non-superuser/non-BYPASSRLS runtime role returned no other-Workspace Party rows and
no Party rows without Workspace context.

The targeted preparation, name-review and children test modules passed all 65
tests with `--settings django_project.settings.test --keepdb`.

Local private evidence is in `outputs/linode-party-rehearsal-20260921/`:

- `review.html`: readable results and pending loan work.
- `verification.json`: persisted counts and reconciliation outcomes.
- `manifest.json`: SHA-256 checksums for report and evidence files.
- Per-chunk receipts, held raw rows and original Party source evidence.
- Per-schema loan classifications and `loan-classification-summary.json`.
- `COMPLETE`: Party rehearsal completed with explicit holds; not production completion.

Prepared inputs remain in the three local
`.tmp/linode-{jcl,jsk,lakshmi}-party-preparation-20260921-v3/` directories.
Private source/customer evidence must not be committed to Git.

## Loan work and cutover still pending

| Source | Unreleased candidates | Released history candidates | Unreleased with payments | Unreleased with loan-level source errors |
| --- | ---: | ---: | ---: | ---: |
| jcl | 2,545 | 26,474 | 11 | 1 |
| jsk | 1,484 | 3,811 | 2 | 4 |
| lakshmipawnbroker | 2,435 | 8,658 | 1 | 3 |
| Total | 6,464 | 38,943 | 14 | 8 |

These are source classifications, not certified financial positions. Additional
borrower, setup and custody checks still apply; categories may overlap. The JCL
loan `R09911` date correction is applied through its existing versioned ledger,
without modifying the source archive.

Next prepare opening evidence with explicit borrower/setup mapping, principal,
unpaid interest, fees, policy and custody per Workspace. Reconcile the 14
payment-bearing candidates individually. Do not generalize the earlier JCL
interest premise to the other Workspaces or infer debt from mutable source amounts.
Released rows need reviewed archive acceptance; they are not operational loans.

Production remains live. Before go-live, resolve source review facts, inventory
media, prove servicing journeys, freeze legacy writes, take a fresh complete
archive and media snapshot, rebuild/reconcile the final target, and obtain business
acceptance. The discovery archive is not an incremental synchronization base.
