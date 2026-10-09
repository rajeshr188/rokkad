---
status: implemented-locally
owner: loans
updated: 2026-10-09
tags: [loans, portability, migration, inventory]
---

# Minimal position contract and retained-source classification

The owner accepts [ordinary position import](../adr/2026-10-09-loan-position-import-without-earlier-history.md)
and confirms RELEASED means completed loan, zero debt and all collateral returned
to the borrower in the retained old source. Follow the
[ordered plan](../plans/loan-position-import.md).

## IP-01: input contract

Implement Loans-owned loan-closed-position/1 with bounded parse/encode/coverage
review and a pure portability source adapter. Original principal, rates, tenure,
original date and actual closure date may remain unknown. No repayment timeline,
old approval/pricing, product calculation or monitoring policy is required by the
input. Source identity, exact borrower reference, zero-debt position date and
declared custody/basis are explicit. Supplied retained documents bind identity
and known facts, preserving raw data and unknown/zero distinctions.

The reviewed installation's release-row profile yields returned-to-borrower
custody. Retained owner-reported closed/zero records without a release row yield
unknown custody and leave unknown closure dates unchanged. Mutable raw amounts
are not promoted to original principal. Supplied receipt rows remain source data,
not a complete financial history or newly recorded cash.

Active positions continue to reuse reviewed openings without earlier receipts.
Position/continuation facts needed for future servicing remain required;
complete-history restore keeps its old meaning. See the
[closed-position contract](../contracts/loan-closed-position-v1.md).

This slice validates and prepares inputs; it creates no ordinary loans and does
not implement financial admission, owner batch commit or database restore.
Contract encode/parse equality is not ordinary-loan export/restore acceptance.

## IP-02: read-only production inventory and classifier rehearsal

Use an isolated, non-listening reader of the inspected live image, restricted
runtime environment and forced Workspace RLS. All application reads run in
read-only transactions with statement caps. Prototype modules are loaded only
into that ephemeral reader process. No live source, web image, database settings,
table, policy, loan, event, number sequence or financial data changes.

Private detailed manifests remain on the server under the existing deployment
folder's loan-position-import-20261009/ child. Only aggregated counts and
fingerprints are retained locally in .tmp/loan-position-import-20261009/;
customer records are not copied into the checkout. Temporary runtime credential
files are removed after each probe. Counts are dated observations.

| Workspace | Retained records | Closed-position candidates | Date-order exceptions | Candidate returned custody | Candidate unknown custody |
| --- | ---: | ---: | ---: | ---: | ---: |
| JCL | 26,664 | 26,649 | 15 | 26,459 | 190 |
| JSK | 3,840 | 3,836 | 4 | 3,836 | 0 |
| Lakshmi | 8,711 | 8,711 | 0 | 8,711 | 0 |
| Total | 39,215 | 39,196 | 19 | 39,006 | 190 |

All retained rows have exact candidate Party/source bindings and existing
LINODE-source-ID register matches in their own Workspace. No canonicalized loan
number duplicates, conflicts with existing ordinary numbers or already-admitted
origins are found. A separate source identity check finds no repeated source
families, row/document binding disagreement, or disagreement between raw and
canonical borrower bindings. IP-03/IP-04 must lock and revalidate these at actual
admission rather than rely on this dated read-only result.

Every document fingerprint matches its accepted fingerprint. Aggregate snapshot
fingerprints are unchanged between inventory and classifier rehearsal:

- JCL: b2faea58a469e973e15354adb985bfe09b3c235139f900ec2dc6609a06b96daa
- JSK: da9717ea9e2e011cfe688fa4f19f1af561129112399049fe661609f17aec9c6e
- Lakshmi: 978800b98e65547007cd49698c456ba6373f97718f9df5c4029647b7f4a3a757

The initial release-only prototype listed 190 JCL cases as unsupported. Inspection
finds the exact alternate raw status NO_RELEASE_ROW; OWNER_REPORTS_CLOSED, a
retained owner decision, explicitly reported zero balance, and unknown closure
date. The tested classifier supports that separate basis without inventing a
release date or physical return. The final counts above supersede the preliminary
39,006-candidate/209-exception result.

The 19 exceptions report closure before original loan date. Preserve both claims;
do not silently swap, erase or repair dates. Their position/date mapping needs
explicit review before admission. Missing receipts or structured items do not
exclude the remaining records. Normalized original principal is unknown in all
39,215; raw loan/item amounts remain retained source fields.

## Later owner confirmation during IP-03

The owner subsequently confirms returned collateral for the 190 JCL no-release-row
owner-closed/zero records. The read-only classifier is refreshed: the same 39,196
candidates now all have returned custody, and the same 19 date conflicts remain
held. Source fingerprints above are unchanged. Unknown closure dates remain
unknown. The initial table documents the earlier state of knowledge, before this
additional confirmation. See [IP-03](loan-position-import-ip03.md).

## Validation and next slice

34 focused SimpleTestCase checks pass across the new contract/adapter and existing
archive/source-preparation regressions. They verify missing terms, zero versus
unknown, source scope, exact parent loan references, source immutability, owner
decisions, custody distinction, dates, nonzero balances, wire roundtrip and
malformed/bounded inputs and the frozen published v1 schema. No database writes
occur in these tests. Admission
raw-DML/RLS, ordinary read/servicing refusal, transactional batch retry and database
export/restore acceptance remain IP-03/IP-04 and are not claimed complete.

IP-03 must narrowly accommodate absent original terms for evidenced ordinary
CLOSED positions while preserving native/draft/active invariants. Existing
terminal admission cannot import this cohort unchanged: it still requires item
principals/rates/tenure/rounding/product/monitoring. Dummy terms or an invented
settlement cannot bypass those constraints. Original documents/media and old
profile readers remain available throughout the adaptation.
