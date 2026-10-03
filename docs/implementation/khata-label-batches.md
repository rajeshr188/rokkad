---
status: implemented-local
owner: loans
updated: 2026-10-03
tags: [khata, labels, local-pilot, verification]
related: [../adr/2026-10-03-khata-selected-label-batches.md, ../flows/khata-labels-and-pilot-review.md]
---

# Khata selected label batches

Phase 8 removes the all-held selection barrier above 100 items. The label screen
offers a searchable 100-item picker, explicit checkboxes, photo links when available,
select/clear controls and a no-JavaScript **Print displayed batch** action. Search
by item number, UUID, description or storage reference. Each page/search starts a
fresh selection; browsing subsequent pages reads current custody, rather than
freezing a whole-account bundle. The mobile table scrolls inside its card and keeps
identities readable. The existing combined, all-item and single-item modes remain;
combined/all-item issues still require the complete holding and at most 100 items.

The service normalizes selected identities into ascending item-number order and
refuses duplicates, invalid numbers, foreign/account-mismatched/returned items and
more than 100 selections. Under the existing Workspace/account lock, new issues
revalidate every selected item. No partial batch or omitted text is saved. Pending
returns remain physically held and retain their distinct caption. Exact UUID
retries return the original saved issue before checking today's custody; later
receipts or handovers never alter its membership/order or retained PDF bytes.

Every selected item has one 100 x 60 mm page, complete identity/weight/purity/storage
facts, a 6 pt floor and the existing private item-UUID QR route. The renderer's
original three modes and request hashes remain compatible. `SELECTED` extends
`khata-label/1` within the immutable `KhataDocumentIssue` contract. Migration
`0042_khata_label_batches` extends only the label guard, preserving complete-holding
checks for `ALL`/`EACH` and enforcing canonical order. No new model, money/custody
command, background job or table is introduced. Full-checkout no-op merge 0050
joins the independent ordinary branch; that branch and merge are excluded from
the local Khata image.

## Verified local identity

- Candidate: `khata-local-20261003-09678674437c`.
- Image: `sha256:c737e7dcbfe3321e4e2a5f500d6cd871452074cc32d9c7a96b1143e6379266d0`.
- Source: `09678674437cde2a77c4554f8040617151385dee43abd5c0a6775ba6548c661b`.
- Archive: `4a958c3be2f9ca9d4d49c6d4a38feada3d585868bedf609c53db725ef355c463`.
- Actual image matches all **1,432 application/settings files**.
- Exactly **eight label-related application paths** are overlaid on the verified
  [series-status base](khata-series-status.md): seven direct worktree matches and
  the composed registry gate. All other application bytes remain the base bytes.
- **489 frozen Linux regressions pass in 289.451 seconds**, covering the
  existing financial/custody, ordinary/flexible, isolation and archive suites plus
  nine new batch tests. An earlier same-code candidate passed 21 focused label
  checks in 20.270 seconds; the final template refinement is included in the full
  frozen run. Frozen and full-checkout models have no migration drift.
- Dependencies, owner-runtime startup refusal, restricted runtime startup/static
  collection and current owner-only migrations pass. Pre-switch full database/
  private-media backups with hashes and both preceding stopped web containers
  are retained. No unrelated ordinary migrations were applied to this pilot.

Actual browser checks pass: **100 + 5** chunks from a 105-item holding, a separate
two-item selection, exact retry, complete all-item rejection above 100, identity/
storage search, previous/next batches, desktop/mobile, no-JavaScript printing,
viewer denial and private authenticated item scans. All 107 generated pages are
checked for exact dimensions, their selected UUID/order and text sizes of at least
6 pt. Representative first/middle/last pages and desktop/mobile screens are visually
inspected; no clipped or omitted label text is found. Chromium's PDF response-body
capture and hidden-input handling required harness fixes, with original request
identities retained instead of creating duplicate issues; no application fix was
needed for those harness errors.

The separate fictional acceptance draft is **QLABEL00001** (account
8). It records 105 simulated receipts and two simulated
pre-opening returns, leaving 103 held items. It remains unapproved, with zero
withdrawals/principal/interest and three saved label issues. All three PDF hashes
and memberships survive those returns; a newly issued stale selection is refused.
Every pre-existing account, financial/custody/policy/series/document row and original
media byte remains unchanged. Label QA does not change existing account economics.

Restricted-runtime readiness passes and the current native archive encodes all
fourteen tables, files and three selected issues correctly. Selected-batch exact
restore is covered by the regression suite. The inventory is unchanged, but the
guard fingerprint changes: old native archives require their matching image/schema,
then migration forward, or full database/private-media recovery. The mismatch gate
is not relaxed.

This checkpoint is local fictional acceptance. Production, remote CI, hosted
activation, named operator trials, off-device backup acceptance, physical printers,
camera hardware and paper QR scans remain separate gates. The later
[document-navigation checkpoint](khata-document-navigation.md) records the current
local runtime; the identities and counts above remain dated phase-eight evidence.
