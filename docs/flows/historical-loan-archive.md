---
status: implemented
owner: project
updated: 2026-09-13
tags: [loans, portability, archive, flow]
---

# Historical loan evidence

Open **Historical loan evidence** in Workspace settings, or follow the archive
link from **Import Loans**. Accepted evidence has its own searchable, paginated
list and never appears as a new operational loan.

1. An operator prepares one source-reported closed loan using the
   [closed-evidence format](../contracts/loan-closed-evidence-v1.md). Preserve missing
   values as unknown and retain raw source records. Do not fabricate payments,
   borrower mappings, custody or setup merely to fill the file.
2. The owner chooses **Upload historical evidence for review**. Uploading creates
   a staged batch only. At most 20 unfinished archive batches are allowed.
3. Review source identity, snapshot reference, reported facts, all supplied source
   records and findings. A reported closure may contradict a balance or date;
   acceptance records the claim without declaring it true.
4. Check the explicit retention confirmation and choose **Accept historical
   evidence**. Current permissions and the signed source/review binding are
   rechecked. The archive snapshot, audit entry and batch completion are atomic.
5. The accepted detail shows the local acceptance actor/time and exact source
   claims. **Export retained evidence** downloads a portable source document.
   Another Workspace can review/accept that document without reusing source actor
   IDs as local identities. Export requires data.view and data.export.

The owner can cancel an unfinished upload, clearing its staged source values.
Cancellation cannot erase already accepted evidence, including an identical
snapshot accepted through another batch. Finished batch metadata is retained.
Identical acceptance retries reuse the immutable record. Changed source evidence
creates another snapshot and does not overwrite or automatically supersede earlier
claims. **Browse source snapshots** searches the archive; check the displayed
source system and namespace when IDs are reused by different sources.

There is no repay, release, accrue, activate or borrower-creation action here.
Existing complete-history import and reviewed opening/restore retain their own
financial acceptance requirements. Importing actual customer records and widening
this profile to active loans are separate decisions.

## Offline source preparation

`preview_legacy_closed_archive` reads one supported source schema from a custom
PostgreSQL dump through the existing inert COPY extractor. It never connects to
an application database. Supply `--dump`, `--source-schema`, `--source-namespace`,
`--business-timezone`, `--review-date`, and a fresh `--output-dir`; optionally set
`--pg-restore` and the source-scoped `--owner-profile`.

Release-row existence supplies the CLOSED source claim, without asserting settled
debt or returned custody. The mutable legacy loan amount is retained as raw evidence,
not original principal. Missing payment/item rows remain unknown. Normalized dates
use the explicit timezone; raw timestamps remain intact. Net weights require the
existing scoped owner attestation; gross weights stay unknown. Invalid normalized
documents are held with their full evidence rather than silently repaired.

The private report contains all extracted source rows, a complete review index,
held documents, and individual schema-valid JSON candidates in `candidates.zip`.
The ZIP is a review container, not an upload format: extract a selected JSON file
for the existing single-document archive review flow. A `COMPLETE` marker is
written last; existing directories are never overwritten. Candidate output is
bounded to 256 MiB uncompressed, in addition to the extractor and contract limits.

The September 13 report from `backup_20260912_224652.sql`, schema `jcl`, reuses
namespace `6ca968d6-2647-4dbb-8e39-24f0c1a12ed6` and `jcl-owner/2` solely for the
net-weight attestation. It is at
`outputs/jcl-closed-archive-preview-20260913/review.html`: 26,353 schema-valid,
121 held for control characters in collateral descriptions, zero accepted.
Review exceptions and select a small destination-bound pilot before accepting
source evidence. Main database archive migrations remain unapplied; this offline
preparation does not require them.

Adapter revision `legacy-closed-archive-preview/2` replaces runs of CR, LF or tab
with one space in normalized collateral descriptions. It records the rule, source
item ID, exact before/after text, and retains the unchanged source row. Other
control characters and overlong descriptions still fail the existing archive
contract. This is a source adapter change, not a relaxed wire format.

`case-review.html` and `case-review.json` expose every description transformation
and timestamp finding. Timeline comparison uses the raw aware timestamps, so even
same-business-day release/payment-before-origination is visible; future dates use
the stated review date and timezone. Contradictions remain unchanged claims.
Up to three individual `pilot-*.json` files cover recorded payments, unknown payments
and normalized descriptions. Selection takes the first distinct schema-valid case
per category with no source ERROR or timeline finding. It is a small workflow
proposal, not a statistical sample, approval, or evidence of financial correctness.
The pilot has no destination binding and nothing is accepted by report generation.
