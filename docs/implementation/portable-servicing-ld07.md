---
status: active
owner: project
updated: 2026-10-05
tags: [implementation, loans, portability, documents]
---

# LD-07: portable servicing evidence and source documents

The owner authorized LD-07 after LD-06. The implementation extends the ordinary
Loans export and adds a bounded Loans-owned admission command. It adds no models,
migrations, separate loan domain or generic recovery framework. See the
[decision](../adr/2026-10-05-portable-servicing-evidence.md),
[wire contract](../contracts/loan-servicing-bundle-v1.md) and
[tracked plan](../plans/unified-loan-domain-correction.md).

## Delivered behavior

`Export loan records` chooses the new `loan-servicing-bundle/1` ZIP for broader
supported evidence, including retained bundles, paper receipts/closure batches,
recorded recognition, corrections, linked renewals/reversals, auctions, explicit
future-capture reviews, photographs and issued PDFs. Narrow compatible records
retain their earlier JSONL exports. Old profile meanings and readers stay fixed;
direct calls to old exporters refuse evidence they cannot preserve.

The bundle includes the complete bounded connected loan graph from a frozen
35-model row inventory, original accepted documents/archives, financial operations,
item allocations, accrual/obligation evidence, dated custody and original file
bytes. All renewal and shared release-batch members travel together. Opening
history starts at its actual checkpoint, without fabricated pre-cutover replay.
Incomplete historical-only archives remain archives; this export does not turn
an unsupported closed summary into a financially admitted loan.

Restoration requires explicit destination Party/licence revision/series/product
mapping for each connected loan. Exact source Party identities must already be
mapped. It validates original agreement semantics, event/operation arithmetic,
financial prefixes, recognized charges, reversals, schedules, exposure, custody,
source review fingerprints and file checksums. Destination financial positions
must match the retained source position. A checksum does not prove real-world
truth or permit internally inconsistent financial evidence.

The command creates fresh local IDs/public IDs and unique import numbers under
the restricted runtime role. Source-local numbers, actors, timestamps, source
reviews and exact original bytes stay in immutable accepted evidence. Only fresh
admission projections are constructed; existing accepted loans cannot be merged,
augmented or overwritten. Ordinary Python/SQL guards and forced RLS remain enabled.
Compensated older recorded contracts are validated against their original terms
while inserting their snapshots, then restored to the current corrected projection.

Local actors/times describe import. Genuine original approval time/actor are labelled
as source claims rather than as a new retrospective approval. Original issued PDFs
are downloadable as authenticated Workspace-scoped source copies from loan details,
with checksum verification and private caching. Issued source rows are not inserted
as newly issued destination documents. Later local printing uses the existing
document workflow and truthful source-agreement labels.

Source Rokkad-only capture remains a retained claim. Active/closed destination loans
receive a reconciled paper/mixed review through the source as-of date; staff may
later explicitly choose future Rokkad-only capture. Cancelled successors retain
their reversal history without receiving a new servicing review. Current risk is
recalculated locally using existing monitoring; source cached risk and queued
notifications are not transplanted. Stale/missing current valuation remains unknown.

## Operator route

ZIP restoration currently uses `restore_loan_servicing`, not the existing browser
JSONL upload. First prepare destination setup and import/map the source Party
identity. Write a JSON mapping keyed by each **source loan row ID**, for example:

```json
{"123":{"borrower_id":45,"revision_id":6,"series_id":7,"product_version_id":8}}
```

Run with normal restricted runtime credentials in the target environment:

```text
python manage.py restore_loan_servicing --workspace-id 2 --actor-id 3 --source loan-servicing.zip --mapping mapping.json
```

Preview reports source/local numbers, loan states, recorded/collection balances,
coverage and the exact review checksum. It performs the entire admission inside a
rollback transaction, checks deferred guards and removes provisional media. It may
consume sequence IDs, but does not consume live business numbering counters.
Review the result, then repeat the same command with:

```text
--commit --expected-sha256 <exact-preview-sha256>
```

The checksum binds source ZIP bytes, target Workspace, actor and mappings. Identical
committed retries return the accepted loan IDs; different mappings/changed source
bundles for an accepted source identity are held. This command cannot resolve a
conflict by silently replacing accepted financial history.

Bounds are 32 MiB compressed/expanded, 20 connected loans, 5,000 canonical rows,
1,000 events per loan, 200 files/issued copies and eight transfers of source-document
ancestry. Funding, storage, capitalization and unknown versions are explicitly held.
Use exact Workspace recovery for a supported same-identity offline restore, or full
database/media recovery for graphs exceeding those recovery bounds. A bundle is
not a complete Workspace backup or a general arbitrary-source loan importer.

## Verification and rollout

The affected regression passes **645 tests in 589.278s**, retaining LD-06's 627-case
set and 18 initial LD-07 cases. Final focused verification passes **53 tests in
88.501s**, including all **23 new LD-07 cases**. Django system checks, migration
history/model drift against the dedicated test DB, Loans Python parsing and scoped
whitespace checks pass. Final source files match their tested QA copies.

Tests cover source/destination restricted roles, full preview rollback, financial
tampering despite recomputed hashes, unknown profiles/enums, malformed ZIP/setup,
changed-source retries, genuine native approvals/photos, recorded item allocations,
receipt/contract/closed-settlement corrections, closed archive admission, shared
paper closure batches, opening checkpoint auctions/paired reversal, linked paper
and current native renewals, cancelled successors, source review/capture retention,
exact original PDF bytes, authenticated downloads and separately tested exact
same-identity Workspace recovery of retained source packets.

An added renewal-reversal case exposed a review insertion on a cancelled successor;
the admission now preserves cancellation without issuing that unsupported review.
No guard was weakened. Exact Workspace recovery's existing dynamic schema/guard
fingerprint remains appropriate because this slice makes no schema/guard change.

All database exercise is confined to disposable QA container
`opening-checkpoint-ld04-qa-20261005`, database `test_rokkad_ld04_20261005`.
Raw logs remain locally in `.tmp/ld07/`. No application/candidate/production
migration, data conversion or deployment is performed. Unrelated billing/platform/
storage changes remain separate. LD-08 source inventory, real staff acceptance,
staging/recovery verification and controlled rollout remain pending; neither this
slice nor prior synthetic tests establish production acceptance.
