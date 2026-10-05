---
status: active
owner: project
updated: 2026-10-05
tags: [implementation, loans, servicing, coverage]
---

# LD-06: remaining operations, coverage and risk

The owner authorized this slice and selected an explicit optional future Rokkad-only
capture choice after explanation. Delivery extends the existing canonical services;
it does not change agreed interest, original maturity, approval or financial origin.

## Delivered behavior

- Common servicing prerequisites cover renewal and auction as well as receipts/full
  release. Later money, finalized periods and collateral movements are inventoried
  together. Existing current renewal still approves its successor using current
  evidence; independent paper loans need no invented ancestry.
- Opening renewal preview is characterized against posted settlement and net cash;
  its existing catch-up calculation is retained.
- Current opening auctions use `opening-auctions/1`, checkpoint catch-up and exact
  full recovery. Existing statutory service/permission/publication and custody gates
  remain. Coupled reversal restores recovery, recognition, obligations and custody;
  the original opening remains immutable, and continuing interest resumes.
- Recorded receipt correction previews bind the common dated dependency inventory
  in addition to existing downstream state. A custody change after review rejects
  commit even when the accepted financial event list is unchanged.
- The existing per-loan transaction-review form offers PAPER_MIXED (default) or
  ROKKAD_ONLY. Signed review requires an active supported loan and complete facts
  checked through today for the latter. Original checked history remains separate
  from future capture. No bulk or origin-based automatic transition is introduced.
- A continuing review verifies the original event prefix and agreement/collateral
  hash. Supported current actions maintain coverage without another book check;
  paper facts/history corrections/changed contract/unsupported graphs require review.
  Native derived recognition can post an older eligible period without inventing a
  missing paper transaction. Monitoring uses the same existing financial readers.
- Current-position reminders retain checked and current fingerprints. Changed
  amounts reject at dispatch even if the capture mode is still complete. Fresh risk
  and message review can create a replacement intent for that position; same-position
  duplicates remain guarded. Consent, source risk, date and provider checks remain.
- Loan action presentation uses factual eligibility. Opening auction is visible when
  its prerequisites are satisfied; missing coverage displays a usable explanation.
  The recovery memo identifies the opening checkpoint basis without a fake approval.

## Boundary and compatibility

Existing bounded correction/settlement/renewal services retain their limits. This
slice does not enable arbitrary opening events, multi-item completed-paper opening
principal allocations, auction shortfall/write-off/surplus, capitalization graphs,
unknown ancestry or unavailable pre-cutover history. Ordinary direct lending and
paper/mixed capture keep their existing agreement and review behavior.

Per-loan old history/opening exporters explicitly hold auction graphs or retained
capture transitions until LD-07 can preserve them. Exact Workspace recovery retains
these models, fields and statutory file bytes; it remains an offline same-identity
operation. No published old wire is reinterpreted. Migration 0060 adds fields to the
existing forced-RLS review model and preserves raw-DML immutability/parent guards;
no new table or registry entry is needed. Notice uniqueness now includes the current
reviewed financial fingerprint. Downgrade refuses retained new evidence.

## Validation

The final affected regression passes **627 tests in 748.276s**, including all
**17 new LD-06 cases**. The focused follow-up passes **27 tests in 19.254s**.
Coverage includes actual signed review HTTP, stale preview/choice rejection,
current and paper receipts, correction invalidation, native derived recognition,
coverage rollover/current closure, reduced checkpoint auction/coupled reversal,
statutory/amount rollback, unchanged maturity, current appraisal freshness with
unknown original valuation, stale reminder dispatch/replacement, restricted-role
immutability/foreign-parent isolation and exact Workspace recovery/file retention.

An initial broad run exposed an underspecified existing readiness mock; it now
includes the actual coverage status field. Follow-up also found normalized decimal
spelling in an opening auction catch-up reversal: the writer now retains the exact
source values, consistent with the immutable pairing guard and existing receipt
reversal. The old pilot assertion is intentionally updated to expect the supported
opening renewal link; current successor approval remains required.

The consolidated migration applies in disposable QA. Django system checks and
`makemigrations --check --dry-run` pass with no model drift. All **562 Loans Python
files** parse, and scoped Git whitespace checks pass. Raw test logs are retained
locally under `.tmp/ld06/`; no whole-repository green result is claimed.

All schema exercise is confined to disposable container
`opening-checkpoint-ld04-qa-20261005`, database `test_rokkad_ld04_20261005`.
No application, candidate or production migration/conversion/deployment is performed.
The unrelated billing/platform/storage work remains separate. Whole-repository
baseline failures are not reclassified as fixed by this slice.
