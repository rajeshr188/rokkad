---
status: prepared-pending-business-evidence
owner: project
updated: 2026-09-21
tags: [migration, loans, review, rehearsal]
---

# Three-Workspace loan review preparation

This follows the [verified Party rehearsal](linode-party-rehearsal-20260921.md).
It prepares evidence; it does not admit operational loans or accept closed history.
The source remains the September 21 custom archive, SHA-256
`f50e992a5813571e5d64316534cf073c08a96059780420be47bf7211eab163a6`, installation
namespace `6ca968d6-2647-4dbb-8e39-24f0c1a12ed6`.

## Results

| Workspace | Unreleased | Opening drafts | Collateral holds | With payments | Inactive borrowers | Closed evidence candidates |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| JCL | 2,545 | 2,544 | 1 | 11 | 190 | 26,474 |
| JSK | 1,484 | 1,480 | 4 | 2 | 0 | 3,811 |
| Lakshmi | 2,435 | 2,432 | 3 | 1 | 0 | 8,658 |
| Total | 6,464 | 6,456 | 8 | 14 | 190 | 38,943 |

All unreleased borrowers resolve through the canonical Party UUID in their own
rehearsal Workspace. This is an observed destination link, not certification that
an inactive borrower is operationally admissible. The eight collateral holds also
have source graph errors; categories overlap. All unreleased source loans remain
in `active-evidence.jsonl`, including those omitted from the draft opening set.

Opening drafts deliberately retain unknown balances, terms, cutover, custody and
setup. No JCL owner profile was applied to JSK or Lakshmi. Closed documents pass the
archive format with no format holds, while retaining unknown principal, reported
balances, missing payments/collateral and chronology findings. Schema validity is
not settlement certification. The corrected JCL date remains source-ledger evidence.

The owner subsequently confirmed "same rules as jcl" for JSK/Lakshmi interest and
maturity. The separate `linode-owner-terms/1` attestation preserves the anniversary
interest rule with the first month upfront, aggregate rounding, valid recorded
tenure and a three-calendar-month fallback for missing tenure. It does not extend
the older net-weight attestation or fill opening/custody approvals. Separate
`terms-review.html` and `terms-review.jsonl` files show months and 6,442 interest
illustrations as of September 21; 22 calculations are held. Missing tenure uses
the fallback for 193 JCL, 119 JSK and 318 Lakshmi loans. The calculation date is
not a cutover decision, and illustrations assume no unrecorded payments/concessions
and unchanged principal/rates.

The owner also confirmed "Yes, net weight in both" for JSK/Lakshmi. The separately
versioned `linode-owner/1` combines confirmed terms with net-weight interpretation,
scoped to the exact source installation and three versioned profiles. All 6,456
drafts were regenerated as `loan-opening-review/2` in `confirmed-opening/`; the
Workspace review links now point there. Original source previews are retained.
Gross weight and physical custody are not inferred from this confirmation.

The subsequent custody answer was "Yes, apart from flagged exceptions" for
unreleased loans held at their respective branches. Separate custody evidence
covers 6,254 unflagged loans (2,345 JCL, 1,478 JSK, 2,431 Lakshmi); the 210 flagged
loans remain outside that attestation. The question about unpaid fees/charges is
still pending. No opening financial admission follows from these confirmations.

The restricted `rokkad_runtime` role observed destination data under each explicit
Workspace context, after the existing owner/setup access check. Party, loan,
event, archive, licence-revision, series and product counts were unchanged before
and after. Loans, events, archives and setup records remain zero in this target.

## Reports and regeneration

Private outputs: `outputs/linode-loan-review-20260921/review.html`.
Each of `jcl/`, `jsk/`, and `lakshmi/` contains:

- `review.html`: all active loans, observed Party IDs, setup labels and review flags.
- `payment-review.html`: every payment-bearing active loan and recorded components.
- `active-evidence.jsonl`: complete active source graphs, hashes, issues and Party links.
- `setup-evidence.json`: source licences/series and unapproved destination mappings.
- `source-preview/`: original records, unapproved exclusions and opening drafts/gaps.
- `confirmed-opening/`: current v2 drafts with confirmed net-weight evidence;
  balances, terms approval, custody and destination setup remain unfilled.
- `closed-history/`: format-checked candidate ZIP, all source rows, index, exceptions
  and proposed pilot examples. The ZIP is a review container, not a bulk upload.

The root manifest hashes the evidence files. Local technical orchestration is
`.tmp/prepare_linode_loan_reviews.py`; verification is
`.tmp/verify_linode_loan_reviews.py`. The subsequent confirmed-term attachment is
`.tmp/apply_linode_terms_review.py`. Customer files remain ignored by Git.
The confirmed v2 drafts were attached by `.tmp/attach_confirmed_linode_openings.py`.

Verification accounts for all 45,407 loan IDs exactly once as active review or
closed candidate. Every active linked source graph matches extraction, all raw row
hashes reconcile (including correction provenance), and all 38,943 zipped archive
documents parse through the actual archive contract with unknown balances intact.
The evidence manifest and local report links passed checks. Tests: 29 owner-rule,
archive and profile tests; 14 opening-import tests under restricted RLS.
After the net-weight confirmation, 57 source preparation/owner-rule/staging/
reconciliation tests passed, alongside the 14 opening-import tests (71 distinct
focused tests). The owner-rule suite was rerun after tightening its explicit
profile requirement: all 15 passed.
The final combined run of all seven affected test modules passed 98 tests.
The final report manifest covers 107 files, including custody evidence, and all
local HTML links resolve.

The existing reusable offline commands prepare fresh source reports (replace
the example schema/profile and use a fresh output directory for each Workspace):

```powershell
.venv314\Scripts\python.exe manage.py preview_legacy_dump `
  --dump C:\Users\rajes\backup_20260921_095530.sql `
  --source-schema jsk --source-profile linode-jsk/1 `
  --source-namespace 6ca968d6-2647-4dbb-8e39-24f0c1a12ed6 `
  --prepare-openings --propose-skip-incomplete-collateral `
  --output-dir outputs\jsk-fresh-source-review

.venv314\Scripts\python.exe manage.py preview_legacy_closed_archive `
  --dump C:\Users\rajes\backup_20260921_095530.sql `
  --source-schema jsk --source-profile linode-jsk/1 `
  --source-namespace 6ca968d6-2647-4dbb-8e39-24f0c1a12ed6 `
  --business-timezone Asia/Kolkata --review-date 2026-09-21 `
  --output-dir outputs\jsk-fresh-closed-review
```

These commands do not read destination data or import business records. The
destination observations in this rehearsal report additionally come from guarded,
authorized, read-only queries against the isolated rehearsal database.

## Next admission work

The source-verified opening bridge now accepts the optional versioned Linode
profile in `source_evidence`, `stage`, `stage_many` and the operator command's
`--source-profile`. It re-extracts and verifies corrections, and stores the selected
profile in signed source evidence. Existing profile-less imports remain compatible.
Mismatching schemas and changed correction-source values fail before staging.

Explicit versioned staging now selects `linode-owner/1`, carrying the subsequently
confirmed net-weight evidence for JSK/Lakshmi as well as JCL. Synthetic JSK and
Lakshmi stage, preview, commit and completed retry pass through the full bridge
with canonical Party bindings. Legacy profile-less calls preserve `jcl-owner/2`.
Neither path permits source payment rows or inconsistent financial facts through
the unchanged-principal admission path.

The borrower compatibility gap is fixed: opening review v1/v2 keeps its raw
`contact_customer:<pk>` reference, while the writer resolves the corresponding
canonical Party UUID from the same namespace/schema if available. Old raw bindings
remain supported. Conflicting raw/canonical bindings fail closed before financial
writes, and another Workspace's binding remains invisible. The frozen review and
accepted financial origin format are unchanged.

Business evidence is also required: actual later collections, opening
principal/interest/fees and current physical custody. Shared interest and maturity
rules are now recorded, but they do not certify a particular balance. The production
commit's model calculates calendar-month interest and its payment save path
allocates against calculation time, so saved payment splits alone cannot certify
historical paid-through dates. These facts need reconciliation against receipts
or the owner's records; missing values must not become zero balances.

Prepare explicit destination setup and number reservations, then run representative
opening, collection and release rehearsals. Historical archive acceptance remains
separate from financial admission. Final go-live still requires a legacy write
freeze, fresh complete dump/media, reconciliation and business acceptance.
