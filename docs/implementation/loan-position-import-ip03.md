---
status: implemented-locally
owner: loans
updated: 2026-10-09
tags: [loans, portability, closed-position, migration]
---

# IP-03: ordinary closed-position admission

Follow the [accepted decision](../adr/2026-10-09-loan-position-import-without-earlier-history.md)
and [ordered plan](../plans/loan-position-import.md). This slice is local implementation;
it does not convert production records or deploy migration 0065.

## Owner confirmation and source preparation

The owner additionally confirms the 190 JCL records with an earlier retained
owner-closed/zero decision and no release row had their collateral returned to
the borrower. The scoped adapter records OWNER_CLOSED_POSITION and the separate
owner-confirmation-2026-10-09:jcl-190-owner-closed-zero-all-collateral-returned-to-borrower
reference. Unknown closure dates remain unknown. The reviewed source installation,
JCL schema, exact loan/borrower identity, retained owner decision and explicit
zero closing balance remain prerequisites for this adapter branch. Arbitrary
external or other-schema owner claims do not acquire this return interpretation.

The refreshed read-only classification retains 39,196 candidates and 19
closure-before-original-date exceptions. Source document fingerprints remain
unchanged. Candidate custody is now returned for all 39,196, including those 190;
this changes prepared position facts, not the immutable source documents. Private
manifests remain on the server. IP-04 now freezes and rechecks the exact 190
identities/hashes, removing the schema-wide inference at the owner's direction.
Future missing release rows need separate review. See the
[IP-04 delivery](loan-position-import-ip04.md).

## Persistence and authority

Reuse PawnLoan, PawnLoanEvent, HistoricalLoanImport, HistoricalLoanEvidence and
HistoricalLoanAttachment; no new table or business state is introduced.
PawnLoan.is_imported_closed_position marks the narrow persistence basis, not a
new product. Principal, monthly rate, loan date, tenure and product reference can
be null only under the new guarded closed-position basis. Native, direct, paper
and active loans retain complete-term constraints and required form fields.

The owner-only admission service requires current Workspace context, membership,
commercial write access and data/create/import and release authority. It locks
the Workspace, checks an exact existing source Party binding and scoped series,
reviews all retained source-family snapshots, and claims the original number
using existing forward-only rules. It cannot match borrowers by name, create
dummy setup, overwrite an existing financial origin or reuse an ordinary number.
Legacy schema-local origin bindings keep their existing keys. New external
closed-position origins scope the source key by system as well as namespace;
two external systems can reuse a table-local ID without being merged. Existing
older unscoped financial origins are checked conservatively, without changing
their published profile meanings. Retained source families remain system-scoped.

Preview executes the real writer inside a rolled-back transaction. A one-hour,
actor/Workspace/date/document/mapping-bound review token authorizes confirmation.
Selected retained snapshot fingerprints and family membership are bound too.
Commit rechecks authority and source facts; identical reviewed retry returns the
existing loan. A different source position or mapping is a conflict.

Admission creates a CLOSED PawnLoan with the known original details, one
zero-valued MIGRATION_OPENING position event and immutable financial-origin
provenance. Its event date is the accepted position's as_of date, not an invented
closure or handover date. No approval, disbursal, receipt, accrual, schedule,
concession or physical-return event is manufactured. Unknown calculation terms
and original principal remain null rather than zero or today's defaults.

Migration 0065 retains old archive-admission branches and adds exact new
source/document/provenance/position guards. A deferred constraint applies only
to newly inserted closed-position loans; it requires the sole zero checkpoint
and origin before commit. Ordinary origins cannot be relabelled; closed-position
loans cannot be updated, reopened, receive operational agreements, collateral
rows or extra financial events. Existing immutable evidence and forced RLS
remain in force. Apply through settings.migration under the owner role only.

## Common reads and ordinary interface

Shared balances, servicing position, continuation, exposure, transaction coverage,
reports and rollout inventories understand loan-closed-position/1. At/after the
accepted position date, principal/interest/fees and exposure are zero. Earlier
financial balances are unavailable. There is no calculation policy, interest
projection or maturity deadline to invent. Physical return follows the accepted
custody fact independently; unknown handover is disclosed separately.

Earlier receipts, cash paid, principal collected and interest collected are
UNAVAILABLE. Zero transaction amounts in the event fold describe recorded Rokkad
activity, not lifetime collections. The checkpoint contributes no disbursal,
receipt, cash or income to ordinary financial reports. Closed risk assessment and
valuation are NOT_REQUIRED. Active loan risk monitoring remains unchanged.

The ordinary loan detail URL displays closed position, known/unknown original
terms, accepted basis, raw retained source groups and the existing authorized
source-media links. The ordinary Loans list displays Unknown for absent original
principal/date. Existing directory source-identity matching suppresses an admitted
archive card without deleting its evidence. Source records and amounts remain
labelled as source claims, not reconstructed financial actions. Native/direct/paper
detail and entry forms retain their current path.

One existing terminal-form defect found by regression is corrected: the inherited
include_old_series and source_license_from_setup presentation fields are removed
from the older terminal submission. Its published financial contract is unchanged.

## Portability and remaining work

Ordinary loan export selects the existing loan-closed-position/1 JSON contract
or the new [closed-position media bundle](../contracts/loan-closed-position-bundle-v1.md).
The download carries accepted position, original details, source identity,
unavailable-history declaration and the unchanged source document. When source
files exist, their exact bytes, filenames, MIME metadata and provenance travel
in a bounded checksum-verified ZIP. A missing/corrupt file blocks export rather
than silently omitting it.

File preview/admission reuses the same reviewed position writer. Destination
Party/series mappings must already exist; fresh local loan/event/archive/media
IDs are allocated. Source actors and fake financial events are not copied.
Changed content, unsupported media types, unexpected ZIP entries, duplicate
paths, hash mismatches and excessive expanded data are refused. Storage created
by a failed admission is cleaned up. Existing history/opening/servicing profiles
remain frozen and use their existing readers/writers.

IP-03 provides the admission/file services and ordinary reads/download. It does
not add a second staff entry form or an individual-review requirement for the
39,196 records. IP-04 supplies reviewed resumable batch orchestration and the
production migration/conversion rehearsal. IP-05 supplies the final directory
consolidation and measured search correction. The 19 contradictory dates remain
held; minimal closed-position correction/reopening is not enabled by this slice.

## Validation

Fresh PostgreSQL tests cover minimal/known-term positions, unknown versus returned
custody, preview rollback and forward-only numbering, signed review/source
changes, duplicate/source conflicts, current authority on retry, native null-term
refusal, restricted-role raw writes and cross-Workspace isolation. Ordinary detail,
list, export, common readers, inventories, source-media preservation, ZIP tampering,
fresh-Workspace restore and idempotent retry are exercised alongside the existing
native/paper/archive/terminal regression suites. All 150 tests pass on a fresh
PostgreSQL database, including restricted-role adversarial writes; the database
is destroyed afterward. The migration/model consistency check reports no changes.
Documentation and app-boundary results are recorded with the scoped commit.

After actual admission, do not reverse migration 0065 onto nullable closed records
or deploy a reader that assumes complete terms. Keep the compatible reader and
source evidence; stop/resume reviewed conversion rather than restoring a database
checkpoint over subsequent business activity.
